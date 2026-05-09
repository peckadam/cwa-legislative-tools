# California WDA-Legislative Mapping Tool (Phase 3 Core)

This repository now includes a functional Phase 3 core application built with Streamlit.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Data loading behavior

The app checks `data/processed/` for production data files:

- `wda.geojson`
- `assembly.geojson`
- `senate.geojson`
- `wda_ad_overlap.csv`
- `wda_sd_overlap.csv`
- `wdb_contact.csv`
- `legislator.csv`
- `legislator_office.csv`
- optional: `legislator_staff.csv`

If these files are not present, it runs in demo mode automatically.

## Core features implemented

- Interactive California map with toggleable WDA, Assembly, and Senate layers.
- Search by WDA, Assembly district, Senate district, and legislator name.
- Relationship display for WDA <-> legislative overlaps using `is_display_eligible` (`>=1%`).
- Tabular overlap views and card-style summaries.
- Inline WDB Executive Director contacts and legislator office contacts.
- Phase 4 export and notification features:
  - Multi-legislator deduplicated WDB Executive Director email list generation.
  - CSV export for relationship rows and contact lists.
  - Draft notification email generator with editable topic and downloadable text output.

## Notes for production

- Replace demo mode by exporting processed outputs from the Phase 2 ETL pipeline into `data/processed/`.
- For best performance at full statewide scale, precompute overlap tables and keep geometry simplified for web rendering.

## ETL pipeline

The repository now includes a full ETL scaffold under `etl/` that produces the app's required processed files.

```bash
make etl-all
```

See `etl/README.md` for raw input file expectations, rule configuration, and validation details.

For a local smoke test with generated demo raw inputs:

```bash
make etl-demo-all
```

For a full official refresh + rebuild:

```bash
make etl-refresh-all
```

Recommended production-safe refresh:

```bash
make etl-backup
make etl-refresh-all
```

## Phase 5 documentation

- Deployment guide: `docs/deployment.md`
- User guide: `docs/user-guide.md`
- Administrative runbook: `docs/admin-guide.md`
- Release checklist: `docs/release-checklist.md`
- Branch protection recommendations: `docs/branch-protection.md`

## CI

GitHub Actions workflow:

- `.github/workflows/ci.yml`

## Local Board Meeting Monitor

This repo includes a daily automation for California local workforce development board and executive committee meeting schedules, agenda PDFs, and a generated online calendar/ICS feed published from `docs/`. Microsoft Graph OneDrive/Outlook sync remains optional.

See `docs/local-board-meeting-monitor.md`.

## Contribution Templates

- Pull request template: `.github/pull_request_template.md`
- Issue templates:
  - `.github/ISSUE_TEMPLATE/bug_report.md`
  - `.github/ISSUE_TEMPLATE/data_update_request.md`
