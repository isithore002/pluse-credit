"""
gemini_client.py - Google Gemini Flash 1.5 integration
All 3 prompts as defined in CLAUDE.md (exact, do not rewrite)
"""

import os
import json
import re
import google.generativeai as genai
from typing import Dict, List
import time


class GeminiClient:
    """Interface to Gemini Flash 1.5 for score explanations"""

    def __init__(self, api_key: str = None):
        if api_key is None:
            api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError("GEMINI_API_KEY not set in environment")

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-1.5-flash")
        self.rate_limit_delay = 4  # 15 RPM = 4 seconds between calls
        self._available = True
        self._unavailable_reason = ""

    @property
    def is_available(self) -> bool:
        return self._available

    def _mark_unavailable(self, reason: str) -> None:
        if self._available:
            self._available = False
            self._unavailable_reason = reason
            print(f"Gemini disabled for this process: {reason}")

    def _format_shap_for_prompt(self, shap_values: List[Dict]) -> str:
        """Format SHAP values for Gemini prompt"""
        formatted = []
        for idx, feature in enumerate(shap_values[:3], start=1):
            formatted.append(
                f"  {idx}. {feature['feature']}: value={feature['value']:.2f}, impact={feature['impact']:+.2f}"
            )

        return "\n".join(formatted) if formatted else "No significant features"

    def _extract_json_from_response(self, text: str) -> Dict:
        """Extract JSON object from Gemini response"""
        # Try to find JSON block
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Fallback: return response as-is
        return {"raw_response": text}

    def generate_explanation(
        self,
        pulse_score: int,
        shap_values: List[Dict],
        archetype: str,
        weakest_dimension: str,
        weakest_score: float,
    ) -> str:
        """
        Prompt 1: Plain-English explanation
        Score + SHAP top 3 → 2 sentences
        """
        prompt = f"""You are a financial advisor explaining a credit score to a first-time borrower in India.

Score: {pulse_score}/850
Top factors (SHAP): {self._format_shap_for_prompt(shap_values)}
User archetype: {archetype}
Weakest dimension: {weakest_dimension} (score: {weakest_score:.0f}/100)

Write EXACTLY 2 sentences in simple English (no jargon).
Sentence 1: What is working in their favor with a specific example from their data.
Sentence 2: What is holding them back and why it matters to a lender.

Return JSON: {{"explanation": "..."}}"""

        try:
            if not self._available:
                return f"Default: Score {pulse_score} indicates {archetype} with strong {weakest_dimension}."

            response = self.model.generate_content(prompt)
            time.sleep(self.rate_limit_delay)

            result = self._extract_json_from_response(response.text)
            return result.get("explanation", response.text)

        except Exception as e:
            self._mark_unavailable(f"explanation call failed: {e}")
            return f"Default: Score {pulse_score} indicates {archetype} with strong {weakest_dimension}."

    def generate_actions(
        self,
        pulse_score: int,
        archetype: str,
        dimensions_sorted: Dict[str, float],
    ) -> List[Dict]:
        """
        Prompt 2: Action roadmap
        3 specific, actionable improvements with score deltas
        """
        dimensions_json = json.dumps(dimensions_sorted, indent=2)
        dims_sorted = sorted(dimensions_sorted.items(), key=lambda x: x[1])
        dims_sorted_text = ", ".join([f"{k}: {v:.0f}" for k, v in dims_sorted])

        prompt = f"""You are a credit coach for a {archetype} in India with PulseCredit score {pulse_score}/850.

Weakest dimensions ranked: {dims_sorted_text}
Current dimension scores:
{dimensions_json}

Generate exactly 3 specific, actionable improvements.
Each must: name the exact behavior, state the timeframe, predict the score increase.
Be hyper-specific — not "pay regularly" but "make at least one UPI payment every 3 days".

Return JSON: {{"actions": [{{"action": "...", "delta": 18, "priority": 1}}, ...]}}"""

        try:
            if not self._available:
                return self._generate_default_actions(dims_sorted[0][0], archetype)

            response = self.model.generate_content(prompt)
            time.sleep(self.rate_limit_delay)

            result = self._extract_json_from_response(response.text)
            actions = result.get("actions", [])

            # Ensure exactly 3 actions
            if len(actions) < 3:
                actions = self._generate_default_actions(weakest_dim=dims_sorted[0][0], archetype=archetype)

            return actions[:3]

        except Exception as e:
            self._mark_unavailable(f"actions call failed: {e}")
            return self._generate_default_actions(dims_sorted[0][0], archetype)

    def generate_lender_memo(
        self,
        pulse_score: int,
        band: str,
        confidence_low: int,
        confidence_high: int,
        archetype: str,
        shap_values: List[Dict],
        dimensions: Dict[str, float],
    ) -> str:
        """
        Prompt 3: Lender credit memo
        150-word structured narrative for NBFCs
        """
        # Format positive and negative SHAP values
        positive_shap = []
        negative_shap = []

        for feature in shap_values[:3]:
            impact = feature.get("impact", 0)
            if impact > 0:
                positive_shap.append(f"  - {feature['feature']}: +{impact:.0f}")
            else:
                negative_shap.append(f"  - {feature['feature']}: {impact:.0f}")

        positive_str = "\n".join(positive_shap) if positive_shap else "  - Consistent payment patterns"
        negative_str = "\n".join(negative_shap) if negative_shap else "  - Limited history"

        dimensions_json = json.dumps(dimensions, indent=2)

        prompt = f"""You are writing a credit memo for an NBFC loan officer reviewing a first-time borrower.

PulseCredit Score: {pulse_score}/850 ({band})
Confidence interval: {confidence_low}–{confidence_high}
Archetype: {archetype}
Top strengths (SHAP):
{positive_str}
Top risks (SHAP):
{negative_str}
Dimension breakdown:
{dimensions_json}

Write a 150-word structured memo with exactly these sections:
**Profile Summary** | **Positive Signals** | **Risk Indicators** | **Recommendation**

Recommendation must be one of: "Approve up to ₹{{amount}}" / "Approve with monitoring" / "Decline — reassess in 90 days"

Return JSON: {{"lender_memo": "..."}}"""

        try:
            if not self._available:
                return self._generate_default_memo(pulse_score, band, archetype)

            response = self.model.generate_content(prompt)
            time.sleep(self.rate_limit_delay)

            result = self._extract_json_from_response(response.text)
            return result.get("lender_memo", response.text)

        except Exception as e:
            self._mark_unavailable(f"memo call failed: {e}")
            return self._generate_default_memo(pulse_score, band, archetype)

    def _generate_default_actions(self, weakest_dim: str, archetype: str) -> List[Dict]:
        """Default actions when Gemini fails"""
        defaults = {
            "rhythm": [
                {
                    "action": "Make at least one UPI payment every 3 days",
                    "delta": 18,
                    "priority": 1,
                },
                {
                    "action": "Keep monthly spend within 20% of last month",
                    "delta": 14,
                    "priority": 2,
                },
                {"action": "Ask 3 contacts to send you ₹1 each", "delta": 11, "priority": 3},
            ],
            "velocity": [
                {
                    "action": "Avoid spending more than ₹500 in a single transaction",
                    "delta": 20,
                    "priority": 1,
                },
                {"action": "Plan large purchases on fixed dates", "delta": 15, "priority": 2},
                {
                    "action": "Maintain consistent monthly spend bucket",
                    "delta": 12,
                    "priority": 3,
                },
            ],
        }

        return defaults.get(weakest_dim, defaults["rhythm"])

    def _generate_default_memo(self, pulse_score: int, band: str, archetype: str) -> str:
        """Default memo when Gemini fails"""
        recommendation = "Approve with monitoring"
        if pulse_score >= 700:
            recommendation = "Approve up to ₹50,000"
        elif pulse_score < 600:
            recommendation = "Decline — reassess in 90 days"

        return f"""**Profile Summary** Profile identified as {archetype} type with consistent behavioral markers. **Positive Signals** Regular transaction frequency and identifiable spending patterns. **Risk Indicators** Limited credit history, emerging financial profile. **Recommendation** {recommendation}."""


# Quick test
if __name__ == "__main__":
    import os

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[WARN] GEMINI_API_KEY not set. Skipping test.")
    else:
        client = GeminiClient(api_key)

        # Test explanation
        shap_values = [
            {"feature": "rhythm_cov", "value": 0.15, "impact": 25},
            {"feature": "merchant_hhi", "value": 0.52, "impact": 12},
            {"feature": "velocity_zscore", "value": 0.3, "impact": -8},
        ]

        explanation = client.generate_explanation(
            pulse_score=612,
            shap_values=shap_values,
            archetype="student",
            weakest_dimension="velocity",
            weakest_score=48,
        )
        print(f"Explanation: {explanation}\n")

        # Test actions
        dimensions = {"rhythm": 72, "merchant": 65, "social": 55, "calendar": 80, "velocity": 48, "nlp": 60}
        actions = client.generate_actions(pulse_score=612, archetype="student", dimensions_sorted=dimensions)
        print(f"Actions: {json.dumps(actions, indent=2)}\n")

        # Test memo
        memo = client.generate_lender_memo(
            pulse_score=612,
            band="fair",
            confidence_low=582,
            confidence_high=642,
            archetype="student",
            shap_values=shap_values,
            dimensions=dimensions,
        )
        print(f"Memo: {memo}")
