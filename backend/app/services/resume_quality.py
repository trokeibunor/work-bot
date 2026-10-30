"""Preserve professional depth while tailoring wording and emphasis."""
import logging
import re
import unicodedata

logger = logging.getLogger(__name__)

RESUME_DEPTH_RULES = '''Optimize for relevance and clarity without simplifying the candidate's career.
Preserve EVERY employer as a separate dated entry with the actual role title and full employment period.
Never merge earlier roles into "Prior Experience" or remove them because they are older.
Preserve the substantive achievement detail, metrics, scale, architectural decisions, leadership, ownership, and progression in the approved profile AND master CV.
Reorder bullets and improve wording to emphasize relevant experience; do not replace detailed evidence with generic summaries.
Retain all substantive achievements for each role, including earlier leadership experience. Preserve education, projects, and skills.
Do not impose a one-page limit or shorten the CV to fit. Use multiple pages as needed.
Do not invent seniority, dates, years of experience, responsibilities, technologies, or results.
A shorter CV is permitted only when the candidate explicitly requests a shorter version.'''


def normalize(value):
    return re.sub(r'[^a-z0-9]+',' ',unicodedata.normalize('NFKD',value).casefold()).strip()


def coverage_issues(resume, context):
    text=normalize(resume)
    issues=[]
    experiences=context.data.get('experience',[])
    for entry in experiences:
        for field in ('company','role','period'):
            value=entry.get(field,'').strip()
            if value and normalize(value) not in text:
                issues.append(f'Missing {field}: {value}')
        for highlight in entry.get('highlights',[]):
            for metric in re.findall(r'\d[\d,]*(?:\.\d+)?\s*%?',highlight):
                if normalize(metric) not in text:
                    issues.append(f'Missing achievement metric for {entry.get("company")}: {metric}')
    expected=sum(len([h for h in e.get('highlights',[]) if h.strip()]) for e in experiences)
    actual=len(re.findall(r'^\s*[-*•]\s+\S',resume,re.MULTILINE))
    if actual<expected:
        issues.append(f'Achievement detail reduced: {actual} bullets for {expected} approved employment achievements.')
    return issues


def preserve_resume_depth(resume, context):
    issues=coverage_issues(resume,context)
    if not issues:
        return resume
    logger.warning('Generated resume failed depth checks; retaining complete source CV: %s', '; '.join(issues))
    if not coverage_issues(context.resume,context):
        return context.resume
    # Preserve the source document and supply all structured history if the source itself is condensed.
    from app.services.candidate_profile import render_resume
    return context.resume.rstrip()+'\n\n## Complete Professional Record\n\n'+render_resume(context.data).split('\n',1)[1]
