# UI and Docker optimization

The queue now separates errors from empty results, keeps filters in its URL, presents jobs as cards on mobile, and offers Undo after ignoring a job. Escape returns from an application to the queue. The Add jobs dialog uses the browser's modal focus handling and restores focus when closed. Application and editor requests check for errors before advancing or reporting success.

## Storage changes

- The Python image builds dependencies in a separate stage; compilers and development headers stay out of production.
- API, worker, and Beat reference `jate-backend:latest`, built by the backend service. For a worker-only deployment, build the backend first with `docker compose build backend`.
- Frontend dependencies use `npm ci`; the existing standalone production output is retained.
- All Compose services rotate container logs at 10 MB, retaining three files each. Existing containers need recreation to adopt this configuration.
- Celery results expire after one hour. Persistent job records and application materials remain in PostgreSQL.
- Tailoring and editing store markdown and invalidate the PDF cache. Downloads render documents on demand into per-job directories so roles at the same company cannot overwrite each other's files. Existing PDFs are left in place; shared legacy PDFs are regenerated in job-specific directories when downloaded.

## Apply and measure

```sh
docker system df -v
docker compose build backend frontend
docker compose up -d --no-build --force-recreate
docker system df -v
```

Add `--profile proxy` to the `up` command if you use the bundled Nginx proxy. Normal `up --build` also builds the shared backend image.

Compare unique image size, build cache, container writable layers, logs, and named volumes separately. Build stages can remain in build cache even though they are absent from runtime images. Smaller images do not automatically remove old images or shrink Docker Desktop's virtual disk.

Do not remove `jate_pgdata`, `jate_redisdata`, or `jate_pdf_storage` as routine cleanup. Audit unused images and builder cache before pruning. No volume deletion or automatic pruning is included in these changes.

## Verification

Frontend: `cd frontend && npm run build`.

Backend PDF regression tests (with backend requirements installed):

```sh
cd backend
python -m unittest discover -s tests -v
```

These cover valid PDF generation, cache reuse, isolation of jobs at the same company, migration from shared legacy filenames, and cache invalidation after editing without eagerly rendering a document.

## Review results

- Production Nuxt build passed.
- Production and development Compose configurations validated.
- Four backend PDF regression tests passed in a temporary host environment (Python 3.9 with compatible ReportLab 4.5.1; the container targets Python 3.12).
- Browser checks used controlled API fixtures: desktop and 390px mobile layouts, failed status saves, ignore/Undo, preserved queue filters, dialog focus wrapping, and Escape/focus restoration.
- The local Docker daemon did not respond to disk-usage requests. Runtime images were not rebuilt or deployed, and no disk-reclamation amount is claimed. Existing images, caches, logs, PDFs, and named volumes were not deleted.

Final axe accessibility audits reported zero violations on the queue, application detail, and Add jobs dialog with the sample data. The audit left contrast checks for short count badges and some modal text for manual review; these reports are not a full accessibility certification. Browser screenshots and reports were kept in `/tmp/workbot-*`, outside the source tree.
