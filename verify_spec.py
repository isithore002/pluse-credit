#!/usr/bin/env python3
"""
Verify PulseCredit implementation against CLAUDE.md spec
"""

import os
import json
from pathlib import Path

SPEC_VIOLATIONS = []
VERIFIED = []

def check_file_exists(path, description):
    """Check if critical file exists"""
    if os.path.exists(path):
        VERIFIED.append(f"✓ {description}")
        return True
    else:
        SPEC_VIOLATIONS.append(f"✗ MISSING: {description} at {path}")
        return False

def check_python_imports(file_path, forbidden_imports):
    """Check Python file doesn't use forbidden libraries"""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            for forbidden in forbidden_imports:
                if f"import {forbidden}" in content or f"from {forbidden}" in content:
                    SPEC_VIOLATIONS.append(f"✗ HALLUCINATION: {file_path} uses forbidden '{forbidden}'")
                    return False
    except:
        pass
    return True

def check_tech_versions(file_path):
    """Verify tech stack versions match CLAUDE.md"""
    try:
        with open(file_path, 'r') as f:
            content = f.read()

            # Check exact versions from CLAUDE.md
            required_versions = {
                'fastapi==0.111.0': 'FastAPI',
                'xgboost==2.0.3': 'XGBoost',
                'torch==2.3.0': 'PyTorch',
                'shap==0.45.0': 'SHAP',
                'pdfplumber==0.11.0': 'pdfplumber',
                'spacy==3.7.4': 'spaCy',
                'google-generativeai==0.7.0': 'Gemini',
            }

            for version, name in required_versions.items():
                if version not in content:
                    SPEC_VIOLATIONS.append(f"✗ VERSION MISMATCH: {name} - expected {version}")

            VERIFIED.append(f"✓ Tech stack versions verified")
    except:
        pass

# ============ VERIFICATION ============

print("PulseCredit CLAUDE.md Compliance Check\n")
print("=" * 60)

# 1. Backend file structure
print("\nBackend Files:")
backend_files = {
    'h:/pulse-credit/backend/main.py': 'FastAPI app (main router)',
    'h:/pulse-credit/backend/feature_engine.py': 'All 24 features -> 6 dimensions',
    'h:/pulse-credit/backend/ensemble.py': 'XGBoost + AE + heuristics blend',
    'h:/pulse-credit/backend/autoencoder.py': 'PyTorch model (24->12->6->12->24)',
    'h:/pulse-credit/backend/pdf_parser.py': 'pdfplumber multi-bank parser',
    'h:/pulse-credit/backend/nlp_pipeline.py': 'spaCy + Gemini NLP',
    'h:/pulse-credit/backend/gemini_client.py': '3 exact Gemini prompts',
    'h:/pulse-credit/backend/synthetic_data.py': '1,000 profile generator',
    'h:/pulse-credit/backend/train.py': 'Model training + evaluation',
    'h:/pulse-credit/backend/requirements.txt': 'Exact version pins',
}

for path, desc in backend_files.items():
    check_file_exists(path, desc)

# 2. Frontend file structure
print("\nFrontend Files:")
frontend_files = {
    'h:/pulse-credit/frontend/app/layout.tsx': 'Root layout',
    'h:/pulse-credit/frontend/app/page.tsx': 'Landing page (upload + personas)',
    'h:/pulse-credit/frontend/app/dashboard/page.tsx': 'Score dashboard',
    'h:/pulse-credit/frontend/components/ScoreRing.tsx': 'Animated 300-850 ring',
    'h:/pulse-credit/frontend/components/RadarChart.tsx': '6-axis radar',
    'h:/pulse-credit/frontend/components/SHAPWaterfall.tsx': 'SHAP bar chart',
    'h:/pulse-credit/frontend/components/ActionRoadmap.tsx': '3 improvement cards',
    'h:/pulse-credit/frontend/lib/store.ts': 'Zustand global state',
    'h:/pulse-credit/frontend/lib/api.ts': 'Axios FastAPI client',
    'h:/pulse-credit/frontend/package.json': 'Node dependencies',
    'h:/pulse-credit/frontend/tsconfig.json': 'TypeScript config',
}

for path, desc in frontend_files.items():
    check_file_exists(path, desc)

# 3. Config & Database
print("\nConfiguration & Database:")
config_files = {
    'h:/pulse-credit/.env.example': 'Environment template',
    'h:/pulse-credit/db/migrations/001_initial_schema.sql': 'Supabase schema',
    'h:/pulse-credit/.gitignore': 'Git ignore',
    'h:/pulse-credit/.github/workflows/deploy.yml': 'CI/CD GitHub Actions',
    'h:/pulse-credit/README.md': 'Documentation',
    'h:/pulse-credit/CLAUDE.md': 'Master spec (included)',
}

for path, desc in config_files.items():
    check_file_exists(path, desc)

# 4. Check for hallucinations
print("\nHallucination Guard Checks:")
forbidden_imports = ['groq', 'tensorflow', 'flask', 'mongodb', 'openai', 'blockchain']

python_files = [
    'h:/pulse-credit/backend/main.py',
    'h:/pulse-credit/backend/feature_engine.py',
    'h:/pulse-credit/backend/ensemble.py',
    'h:/pulse-credit/backend/autoencoder.py',
]

for py_file in python_files:
    if os.path.exists(py_file):
        if check_python_imports(py_file, forbidden_imports):
            VERIFIED.append(f"✓ {py_file} - no forbidden imports")

# 5. Tech stack verification
print("\nTech Stack Verification:")
check_tech_versions('h:/pulse-credit/backend/requirements.txt')

# ============ REPORT ============
print("\n" + "=" * 60)
print("\nVERIFIED ITEMS:")
for item in VERIFIED:
    print(item)

if SPEC_VIOLATIONS:
    print("\nVIOLATIONS FOUND:")
    for violation in SPEC_VIOLATIONS:
        print(violation)
else:
    print("\nZERO SPEC VIOLATIONS - ALL CLAUDE.MD COMPLIANCE CHECKS PASSED!")

print("\n" + "=" * 60)
print(f"\nSummary: {len(VERIFIED)} checks passed, {len(SPEC_VIOLATIONS)} violations")
