# JATE UI proposal — review prototype

Open `index.html` directly, or serve this directory with `python3 -m http.server 3100 --bind 127.0.0.1 --directory docs/ui-redesign` from the project root.

This is phase 1: a self-contained, interactive visual proposal. All jobs and counts are representative sample data. It makes no API requests and does not change real jobs. The live frontend is unchanged.

## Direction

A focused application workspace with a compact navigation rail, a role-first queue, adjacent job context, and a document-centered preparation view. Desktop queue → desktop preparation → mobile list/detail/preparation are views of the same prototype.

- Canvas: graphite `#17191D`.
- Surfaces: charcoal `#1D2025`, raised `#25292F`.
- Text: white `#F1F3F5`, secondary `#AFB5C0`.
- Action: blue `#4568DF`, with lighter blue for selection and focus.
- Documents: paper `#FAFAF8` with ink `#252A32`.
- Typography: native system sans for the workspace; Georgia on the cover-letter sheet to distinguish the actual document. Role titles carry the hierarchy; metadata remains secondary. No external font download is required.
- Layout: 208px navigation, compact toolbar, split list/detail. Application preparation shifts space to the document and keeps role requirements alongside it.
- Spacing: 4/8/12/16/24/32px. Radius: 6px controls, 10px panels. Borders indicate separations rather than enclosing every paragraph.

The first concept was reviewed against the old interface: removed the introductory banner, moved the goal from the header to the rail, avoided repeated job action buttons, and made the selected role the main visual anchor. The dark queue/light document contrast is intentional and limited to the writing workspace.

## Try

Select jobs; search; filter for remote roles or founder-led companies; change queue status; open Prepare application; switch document sections; edit the sample cover letter; copy answers; ignore/undo or mark a sample application as applied; open Add jobs; switch to Mobile preview. Escape closes overlays. All changes are local to the preview and reset on reload.

## Review decisions

Assess the split queue, neutral palette, light document sheet, readable density, and mobile full-screen review. After review, phase 2 would apply the shared styling and shell to Nuxt, followed by real queue/detail integration and supporting screens. Data extraction and additional application stages remain separate backend scope.

## Validation

JavaScript syntax and browser interaction checks passed: selecting jobs, remote filtering, empty-search recovery, document editing, document tabs, ignore/Undo, and modal Escape/focus restoration. Queue and workspace fit a 390px viewport without horizontal page overflow. Automated axe audits reported zero violations on the desktop queue, desktop workspace, and embedded mobile view; some selected-row contrast checks require manual review because of the selection indicator. Screenshots were visually reviewed.
