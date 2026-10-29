# Approved UI redesign — implementation

The approved design prototype is now implemented in the Nuxt app, using the existing backend.

## Screens

- Compact desktop navigation and mobile bottom navigation, with live application counts and daily progress.
- Role-first Opportunities list and adjacent selected-job preview. Mobile uses full-screen list/detail navigation.
- Search, source/founder filters, advanced score/date filters, sorting, list density, and server-side pagination. The existing API does not expose a strict remote-only filter, so the live UI supports searching locations instead of inventing a remote classification.
- URL-preserved queue state and selected role. Missing source fields are displayed as unspecified, rather than assuming remote eligibility or inventing a title.
- Document-centered application workspace with readable cover letter/resume previews, editing, regeneration instructions, real PDF downloads, short/long screening answers, contacts and outreach drafts, custom questions, and the complete source description.
- Applications uses existing submitted records, dates, and materials. No new pipeline stages or backend migrations.
- Automation contains career-page, community, and tailoring actions. Counts reflect stored job states; no invented task-completion percentage.
- Shared Add jobs dialog retains file, URL, text, deduplication, and tailoring options.

## Reliability

Status changes only advance after successful saves. Ignore supports Undo. Unsaved document edits are protected when navigating, and status changes are blocked until edits are saved or cancelled. Document saves refresh silently so the current tab and editor are retained. Requests for changing filters/roles cancel stale requests. Markdown is rendered as Vue text nodes, never raw HTML from generated documents or listings.

## Checks

- Production Nuxt build and Docker image build.
- Browser fixture checks: selected-job preview, absent location, cover-letter and resume saving, regeneration request fields, short/long answers, outreach, custom questions, failed Apply, successful Apply & next, ignore/Undo, application history, mobile list/detail/workspace, role-details dialog, Add jobs focus and Escape.
- 390px mobile queue and workspace checked for horizontal page overflow.
- Automated axe audits of queue, workspace, and Automation: zero reported violations in the checked states. Selected-row pseudo-element and document-region observations were addressed after the initial audit.
- Real local data checked read-only after frontend recreation. Mutation workflows use fixtures so existing application records are not changed during QA.

Backend, worker, database, and volumes do not need recreation for this UI release. Only the frontend image/container is updated.

## Deployed verification

The frontend container was rebuilt and recreated locally on port 3000. Both frontend and backend reported healthy. Read-only review used the existing job database, application history, and generated documents. Desktop (1440px), phone (375px and 390px), and tablet (768px) layouts were reviewed. Final desktop queue and application-workspace axe audits reported zero violations and zero incomplete checks; Applications and Automation also reported zero violations. The Add jobs dialog reported zero violations with one manually reviewed contrast check. There were no browser runtime errors in the deployed review.

The real data exposed longer navigation counts and a cramped tablet document; both were adjusted. Tablet job context now opens in the role-details dialog, preserving document width. Mutation checks used controlled fixtures, and no real job statuses or documents were edited during QA.
