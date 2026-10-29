# Job workflow updates

The Add Jobs dialog now uses File / Links / Text controls, defaults to Links, validates every nonempty URL line, deduplicates links, and disables invalid submissions. It retains a visible action footer on short screens, uses 44px controls, associates field labels, and prevents dismissal or editing while an import runs. Saving without preparation now creates `new` jobs, visible under Saved for later, rather than stranded `queued_for_llm` records. A failed broker dispatch leaves a job available for retry.

Organization type is a stored generated PostgreSQL column, derived from explicit nonprofit/NGO/charity terms in the company name or description. Existing records are classified when the backend initializes; new records and description edits update automatically. The filter deliberately says **Likely NGO / nonprofit**, with a description of the evidence and an Unknown option. These are keyword signals, not verified legal classifications. It filters the existing queue; discovery sources have not been expanded. The query is preserved when moving through the application workspace. Database initialization is serialized across API workers and fails visibly if it cannot apply the schema addition.

Bulk operations accept 1–100 explicit job IDs and deduplicate them. Selection is restricted to the current page and clears when filters or pagination change. A confirmation shows eligibility and explains each action. Results report updated counts and per-job skip reasons.

- Ignore: NEW and READY_TO_APPLY only, with previous statuses returned for Undo.
- Undo: restores prior NEW / READY_TO_APPLY status only while the job remains archived.
- Prepare: NEW only; reserves jobs as queued before publishing Celery tasks. Broker failures release their reservation for retry.
- Mark applied: READY_TO_APPLY only; saves the application timestamp. The confirmation explicitly asks the user to confirm submission already happened elsewhere. No employer forms or messages are submitted.

Preparing, submitted, rejected, and interview jobs are not bulk ignored. Already prepared jobs are not regenerated in bulk. This avoids overwriting existing application work and racing an active tailoring task.

Validation: production Nuxt/Docker builds; five batch unit tests; existing four PDF tests; an opt-in PostgreSQL/ASGI integration test covering filter validation, generated classification updates, ignore/undo/apply/prepare, and fixture cleanup via transaction rollback. AI dispatch is mocked. Browser review covered desktop, narrow mobile, landscape, invalid URLs, page selection, confirmation dialogs, and automated accessibility checks. No real applications were sent by testing.

Run backend checks in Docker with the app and tests mounted. Set RUN_DB_TESTS=1 for the integration test against an initialized local database.
