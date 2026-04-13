"""
nlp_pipeline.py - NLP intent scoring with spaCy + Gemini Flash 1.5

This module computes a 0-100 NLP behavior score from transaction remarks.
"""

import json
import os
from typing import Dict, List, Optional

import google.generativeai as genai
import spacy


class NLPIntentScorer:
    """Scores transaction intent quality using spaCy signals + Gemini classification."""

    def __init__(self, api_key: Optional[str] = None):
        self.nlp = self._load_spacy_model()
        self.model = None

        if api_key is None:
            api_key = os.getenv("GEMINI_API_KEY")

        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-1.5-flash")

    def _load_spacy_model(self):
        """Load spaCy model with fallback to blank English pipeline."""
        try:
            return spacy.load("en_core_web_sm")
        except Exception:
            return spacy.blank("en")

    def _spacy_signal(self, text: str) -> float:
        """Compute a deterministic text-quality signal in 0-1 range."""
        if not text or not text.strip():
            return 0.2

        doc = self.nlp(text.strip())
        token_count = len([t for t in doc if not t.is_space])
        has_digit = any(t.like_num for t in doc)
        has_entity = len(getattr(doc, "ents", [])) > 0

        score = 0.35
        if token_count >= 2:
            score += 0.2
        if token_count >= 4:
            score += 0.15
        if has_digit:
            score += 0.15
        if has_entity:
            score += 0.15

        return max(0.0, min(1.0, score))

    def _gemini_intent_score(self, remark: str) -> float:
        """Ask Gemini for an intent quality score in 0-1 range."""
        if not self.model:
            return 0.5

        prompt = f"""You are classifying UPI payment remarks for credit behavior modeling.

Remark: {remark}

Return JSON only with this shape:
{{"intent_score": 0.0, "label": "clear|moderate|ambiguous"}}

Rules:
- 1.0 means clear purpose and context.
- 0.5 means partially clear.
- 0.0 means ambiguous or meaningless.
"""

        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1:
                return 0.5

            payload = json.loads(text[start : end + 1])
            score = float(payload.get("intent_score", 0.5))
            return max(0.0, min(1.0, score))
        except Exception:
            return 0.5

    def score_remarks(self, remarks: List[str]) -> Dict[str, float]:
        """Return NLP score and components for a list of transaction remarks."""
        cleaned = [r.strip() for r in remarks if isinstance(r, str) and r.strip()]
        if not cleaned:
            return {
                "nlp_score": 40.0,
                "spacy_component": 0.4,
                "gemini_component": 0.4,
                "sample_count": 0,
            }

        sample = cleaned[:30]
        spacy_scores = [self._spacy_signal(r) for r in sample]
        gemini_scores = [self._gemini_intent_score(r) for r in sample[:10]]

        spacy_component = sum(spacy_scores) / len(spacy_scores)
        gemini_component = sum(gemini_scores) / len(gemini_scores) if gemini_scores else 0.5

        # Weighted blend: deterministic local NLP + remote semantic classifier.
        final_0_1 = (0.65 * spacy_component) + (0.35 * gemini_component)
        nlp_score = round(final_0_1 * 100, 2)

        return {
            "nlp_score": nlp_score,
            "spacy_component": round(spacy_component, 4),
            "gemini_component": round(gemini_component, 4),
            "sample_count": len(sample),
        }


if __name__ == "__main__":
    scorer = NLPIntentScorer()
    result = scorer.score_remarks(
        [
            "Rent April",
            "Canteen bill 50",
            "Swiggy order #3921",
            "UPI",
            "Transfer",
        ]
    )
    print(result)