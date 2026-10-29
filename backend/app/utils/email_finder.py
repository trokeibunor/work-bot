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
    job_title: str,
    candidate: Optional[Dict[str, Any]] = None
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
    candidate = candidate or {}
    name = candidate.get('name') or 'Candidate'
    contact = candidate.get('contact') or {}
    subject = f"Regarding {job_title} — {name}"
    body = (f"Hi {company_name} Hiring Team,\n\nI am interested in the {job_title} position and would welcome the opportunity to discuss my experience.\n\n"
            f"Best regards,\n{name}\n" + ' | '.join(v for v in [contact.get('email'),contact.get('phone'),contact.get('portfolio')] if v))

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
