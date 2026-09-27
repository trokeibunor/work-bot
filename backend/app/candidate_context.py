"""
Candidate Profile Context: Emmanuel Okeibunor
Ground-truth knowledge base for LLM scoring, cover letter generation,
and screening question responses.
"""

from typing import Dict, Any, List

CANDIDATE_PROFILE: Dict[str, Any] = {
    "name": "Emmanuel Okeibunor",
    "location": "Lagos, Nigeria (Open to global remote or full relocation to Europe/North America/African tech hubs; holds valid work readiness)",
    "contact": {
        "email": "okeibunoremma@gmail.com",
        "phone": "+234 9015379412",
        "portfolio": "https://okeibunoremma.work",
        "linkedin": "https://linkedin.com/in/okeibunoremma",
        "github": "https://github.com/okeibunoremma"
    },
    "core_stack": [
        "Vue.js", "Nuxt (3/4)", "React", "TypeScript", "Tailwind CSS",
        "Python (FastAPI, Django)", "Golang", "Java (Spring Boot)", "Node.js",
        "PostgreSQL", "Docker", "Linux VPS (Contabo/Coolify)", "GCP"
    ],
    "key_experiences": [
        {
            "company": "Sycamore",
            "role": "Fintech Software/Frontend Engineer",
            "period": "Feb 2025 – Present",
            "highlights": [
                "Led frontend engineering for fraud detection & risk-management platform (84%+ fraud reduction); built configurable rules engine for non-technical teams.",
                "Scaled Nuxt.js customer apps to 400,000+ active users and 5,000+ daily logins.",
                "Architected Foreign Investments, Premium Yield, and Commercial Paper products (+32% adoption).",
                "Built B2B Merchant Dashboard & Core Banking tooling.",
                "Championed LLM/AI-assisted engineering workflows across the engineering organization."
            ]
        },
        {
            "company": "ALN Riders",
            "role": "Project Lead Engineer",
            "period": "Mar 2025 – Present",
            "highlights": [
                "Led end-to-end logistics platform (alnriders.com) using Nuxt 4 and Golang concurrent backend APIs.",
                "Collaborated on Flutter iOS app deployment.",
                "Managed Contabo cloud infrastructure, surpassing 1M+ transaction value and 500+ active customers."
            ]
        },
        {
            "company": "E-nergie",
            "role": "Creator & Lead Architect",
            "period": "Recent Project",
            "highlights": [
                "Built https://demo.e-nergie.co, a home appliance energy optimization and monitoring platform using a heuristic Non-Intrusive Load Management (NILM) system in Python and FastAPI."
            ]
        },
        {
            "company": "Numinix & Pertinence Group",
            "role": "Software Engineer / Lead Frontend Developer",
            "period": "Prior Experience",
            "highlights": [
                "Architected custom CI/CD pipelines at Numinix (Vancouver remote).",
                "Lead Frontend Developer at Pertinence Group (Oneapp serving 15,000+ users, RBAC security, Repository pattern API layer, 35% productivity boost)."
            ]
        }
    ],
    "education": {
        "degree": "B.Eng. Petroleum Engineering (Second-Class Upper)",
        "institution": "University of Benin"
    }
}

CANDIDATE_SYSTEM_PROMPT = """
You are representing the candidate: Emmanuel Okeibunor.
Ground-Truth Candidate Profile:
- Name: Emmanuel Okeibunor
- Location: Lagos, Nigeria (Open to global remote or full relocation to Europe/North America/African tech hubs; holds valid work readiness).
- Contact: okeibunoremma@gmail.com | +234 9015379412 | Portfolio: https://okeibunoremma.work
- Core Stack: Vue.js, Nuxt (3/4), React, TypeScript, Tailwind CSS, Python (FastAPI, Django), Golang, Java (Spring Boot), Node.js, PostgreSQL, Docker, Linux VPS (Contabo/Coolify), GCP.
- Key Experience 1 (Sycamore - Fintech Software Engineer, Feb 2025–Present): Led frontend engineering for fraud detection & risk-management platform (84%+ fraud reduction); built configurable rules engine for non-technical teams. Scaled Nuxt.js customer apps to 400,000+ active users and 5,000+ daily logins. Architected Foreign Investments, Premium Yield, and Commercial Paper products (+32% adoption). Built B2B Merchant Dashboard & Core Banking tooling. Championed LLM/AI-assisted engineering workflows.
- Key Experience 2 (ALN Riders - Project Lead Engineer, Mar 2025–Present): Led end-to-end logistics platform (alnriders.com) using Nuxt 4 and Golang concurrent backend APIs. Collaborated on Flutter iOS app deployment. Managed Contabo cloud infrastructure, surpassing 1M+ transaction value and 500+ active customers.
- Key Experience 3 (E-nergie - Recent Project): Built https://demo.e-nergie.co, a home appliance energy optimization and monitoring platform using a heuristic Non-Intrusive Load Management (NILM) system in Python and FastAPI.
- Key Experience 4 (Numinix & Pertinence Group): Architected custom CI/CD pipelines at Numinix (Vancouver remote). Lead Frontend Developer at Pertinence Group (Oneapp serving 15,000+ users, RBAC security, Repository pattern API layer, 35% productivity boost).
- Education: B.Eng. Petroleum Engineering (Second-Class Upper), University of Benin.
"""


def get_candidate_summary_text() -> str:
    """Returns candidate context formatted for LLM system prompt injection."""
    return CANDIDATE_SYSTEM_PROMPT.strip()
