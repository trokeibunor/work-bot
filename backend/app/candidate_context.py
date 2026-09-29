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
                "Managed Contabo cloud infrastructure, surpassing NGN2M+ transaction value and 500+ active customers."
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

CANDIDATE_BASE_RESUME = """# Emmanuel Okeibunor
09015379412 | okeibunoremma@gmail.com | Lagos, Nigeria | https://okeibunoremma.work

## Professional Summary
Software Engineer with 5+ years of experience scaling modern web applications, concurrent backends, and robust CI/CD pipelines.

## Work Experience
**Sycamore | Lagos**
*Software Engineer | 02/2025 - Present*
- **Fraud Detection & Risk Mitigation:** Led frontend engineering for Sycamore’s fraud detection and risk-management platform, contributing to an 84%+ reduction in fraudulent activity. Built a configurable rules engine that enabled non-technical teams to create and update fraud rules without engineering intervention.
- **Product Expansion & Growth:** Architected and delivered Foreign Investments, Premium Yield, and Commercial Paper investment products, contributing to a 32% increase in platform adoption.
- **B2B Platform & Merchant Infrastructure:** Designed and developed the Merchant & Business Dashboard, providing secure API access to external partners and enabling B2B integrations.
- **FinTech Performance & Scale:** Optimized Sycamore’s customer-facing applications using Nuxt.js, supporting 400,000+ active users and 5,000+ daily logins while maintaining a reliable and performant user experience.
- **Core Banking & Platform Engineering:** Played a key role in the development of Sycamore’s internal Core Banking platform, contributing to frontend architecture, system integration, and the delivery of internal financial operations tooling.
- **AI & Engineering Productivity:** Championed the practical adoption of LLMs and AI-assisted development workflows across engineering processes.

**ALN Riders | Nigeria**
*Project Lead Engineer | 03/2025 - Present*
- **Led the end-to-end development** of the ALN Riders logistics platform, building the customer-facing web application and administrative dashboard with Nuxt 4, focusing on performance, scalability, and maintainability.
- **Contributed to the system architecture and backend infrastructure** using Golang, designing scalable APIs capable of handling concurrent logistics operations and high-volume requests.
- **Managed cloud infrastructure and production deployments** on Contabo, implementing server management and monitoring practices to maintain platform stability.
- **Led the team through significant business growth,** surpassing ₦1 million in cumulative transaction value and reaching 500+ active customers.

**Numinix Web Technologies | Vancouver, British Columbia**
*Full Stack Web Developer | 11/2024 - 03/2025*
- Architected custom CI/CD pipelines to automate deployments across multiple production environments, reducing manual errors and improving release efficiency.
- Managed production applications for 5+ clients, delivering feature development, critical bug fixes, performance optimization, and ongoing system maintenance.
- Optimized databases and application queries for high-traffic e-commerce platforms.

**Pertinence group | Lagos, Nigeria**
*Lead Frontend Developer | 03/2023 - 10/2024*
- **Architectural Leadership:** Spearheaded the design and development of multiple high-performance, enterprise-grade web applications using Nuxt.js and Nuxt 3 frameworks.
- **Modular Data Strategy:** Engineered a robust API consumption layer using the Repository Pattern.
- **Oneapp:** Managed a system serving 15,000+ active users with up to 500 daily logins. Developed a custom management tool that automated realtor workflows, resulting in a 35% boost in productivity.

## Skills
JavaScript Frameworks (Vue, React, Angular, Nuxt, Next), TypeScript, Python, Golang, PHP, Java, Google Cloud Platform, Artificial Intelligence, Data Analysis.

## Education
**University of Benin**
*B.Eng. Petroleum Engineering*
- Graduated with a Second-class upper division.
"""


def get_candidate_summary_text() -> str:
    """Returns candidate context formatted for LLM system prompt injection."""
    return CANDIDATE_SYSTEM_PROMPT.strip()
