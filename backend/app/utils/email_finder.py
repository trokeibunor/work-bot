import re
import urllib.parse
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse

# Noise / asset domains to exclude
EXCLUDE_EMAIL_DOMAINS = {
    "sentry.io", "github.com", "w3.org", "schema.org", "example.com",
    "domain.com", "email.com", "company.com", "greenhouse.io", "lever.co", "ashbyhq.com"
}


def extract_domain_from_url(url: str, company_name: str = "") -> str:
    """Extracts a clean company domain from job source_url or company name."""
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        
        # If the domain is an ATS domain (e.g. boards.greenhouse.io, jobs.lever.co), try to infer from company name
        ats_domains = ["greenhouse.io", "lever.co", "ashbyhq.com", "workable.com", "reddit.com"]
        if any(ats in netloc for ats in ats_domains):
            clean_company = re.sub(r'[^a-zA-Z0-9]', '', company_name).lower()
            if clean_company:
                return f"{clean_company}.com"
            return netloc

        # If subdomains exist (e.g. careers.datadoghq.com -> datadoghq.com)
        parts = netloc.split(".")
        if len(parts) >= 2:
            return ".".join(parts[-2:])
        return netloc
    except Exception:
        clean_company = re.sub(r'[^a-zA-Z0-9]', '', company_name).lower()
        return f"{clean_company}.com" if clean_company else "company.com"


def extract_hiring_contacts(
    description_raw: str,
    company_name: str,
    source_url: str,
    job_title: str
) -> Dict[str, Any]:
    """
    Extracts explicit hiring emails from job descriptions and generates
    high-probability company inboxes and a pre-composed follow-up email.
    """
    # 1. Regex find all email addresses
    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    found_emails = re.findall(email_pattern, description_raw or "")
    
    verified_direct_emails: List[str] = []
    seen = set()
    for email in found_emails:
        clean_email = email.lower().strip(".,;:()")
        if clean_email in seen:
            continue
        domain = clean_email.split("@")[-1] if "@" in clean_email else ""
        if domain not in EXCLUDE_EMAIL_DOMAINS and "." in domain:
            seen.add(clean_email)
            verified_direct_emails.append(clean_email)

    # 2. Derive company domain and fallback inboxes
    company_domain = extract_domain_from_url(source_url, company_name)
    derived_inboxes = [
        f"careers@{company_domain}",
        f"recruiting@{company_domain}",
        f"jobs@{company_domain}"
    ]

    # Primary contact to target
    primary_email = verified_direct_emails[0] if verified_direct_emails else derived_inboxes[0]
    is_direct = len(verified_direct_emails) > 0

    # 3. Follow-up subject & polite body
    subject = f"Application Follow-up: Emmanuel Okeibunor – {job_title}"
    body = (
        f"Hi {company_name} Hiring Team,\n\n"
        f"I recently submitted my application for the {job_title} position. Given my background building resilient fintech systems at Sycamore (scaling customer platforms to 400,000+ users with an 84%+ fraud reduction) and concurrent Golang backend services at ALN Riders, I wanted to reach out directly to express my strong enthusiasm for {company_name}'s mission.\n\n"
        f"I have prepared tailored materials and would welcome the opportunity to connect regarding how my engineering background aligns with your roadmap.\n\n"
        f"Portfolio: https://okeibunoremma.work\n"
        f"LinkedIn: https://linkedin.com/in/okeibunoremma\n\n"
        f"Best regards,\n"
        f"Emmanuel Okeibunor\n"
        f"okeibunoremma@gmail.com | +234 9015379412"
    )

    # 4. Generate mailto URL with URL encoding
    mailto_url = f"mailto:{primary_email}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"

    return {
        "primary_email": primary_email,
        "is_direct_listing_email": is_direct,
        "direct_emails": verified_direct_emails,
        "derived_inboxes": derived_inboxes,
        "company_domain": company_domain,
        "subject": subject,
        "body": body,
        "mailto_url": mailto_url
    }
