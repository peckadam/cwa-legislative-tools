PYTHON ?= python3
ROOT := $(CURDIR)
RAW := $(ROOT)/data/raw
PROC := $(ROOT)/data/processed
CFG := $(ROOT)/etl/config/columns_template.json

.PHONY: etl-refresh-official etl-backup etl-restore etl-demo-raw etl-legislator-parse etl-report etl-wda etl-overlaps etl-contacts etl-validate etl-manifest etl-all etl-demo-all etl-refresh-all local-board-meetings-dry-run local-board-meetings-live-smoke test

ARCHIVE ?=

etl-refresh-official:
	"$(ROOT)/etl/scripts/refresh_official_sources.sh"

etl-backup:
	"$(ROOT)/etl/scripts/backup_processed.sh" "$(PROC)" "$(ROOT)/data/backups"

etl-restore:
	@if [ -z "$(ARCHIVE)" ]; then echo "Set ARCHIVE=<path-to-backup-tar.gz>"; exit 1; fi
	"$(ROOT)/etl/scripts/restore_processed.sh" "$(ARCHIVE)" "$(PROC)"

etl-demo-raw:
	$(PYTHON) "$(ROOT)/etl/scripts/generate_demo_raw.py" \
	  --raw-root "$(RAW)"

etl-legislator-parse:
	$(PYTHON) "$(ROOT)/etl/scripts/fetch_legislator_contacts.py" \
	  --assembly-dir "$(RAW)/contacts/assembly_pages" \
	  --senate-page "$(RAW)/contacts/senate_members.html" \
	  --out-legislator "$(RAW)/contacts/legislator.csv" \
	  --out-office "$(RAW)/contacts/legislator_office.csv"

etl-wda:
	$(PYTHON) "$(ROOT)/etl/scripts/build_wda.py" \
	  --counties "$(RAW)/geography/counties.geojson" \
	  --cities "$(RAW)/geography/cities.geojson" \
	  --rules "$(RAW)/definitions/wda_rules.csv" \
	  --columns "$(CFG)" \
	  --out-wda "$(PROC)/wda.geojson" \
	  --out-audit "$(PROC)/wda_assignment_audit.csv" \
	  --geometry-version 2026.02.12

etl-overlaps:
	$(PYTHON) "$(ROOT)/etl/scripts/compute_overlaps.py" \
	  --wda "$(PROC)/wda.geojson" \
	  --assembly "$(RAW)/geography/assembly.geojson" \
	  --senate "$(RAW)/geography/senate.geojson" \
	  --blocks "$(RAW)/geography/census_blocks_2020.geojson" \
	  --columns "$(CFG)" \
	  --out-assembly "$(PROC)/assembly.geojson" \
	  --out-senate "$(PROC)/senate.geojson" \
	  --out-wda-ad "$(PROC)/wda_ad_overlap.csv" \
	  --out-wda-sd "$(PROC)/wda_sd_overlap.csv" \
	  --threshold-pct 1.0

etl-contacts:
	$(PYTHON) "$(ROOT)/etl/scripts/normalize_contacts.py" \
	  --wdb "$(RAW)/contacts/wdb_contact.csv" \
	  --legislator "$(RAW)/contacts/legislator.csv" \
	  --legislator-office "$(RAW)/contacts/legislator_office.csv" \
	  --columns "$(CFG)" \
	  --out-wdb "$(PROC)/wdb_contact.csv" \
	  --out-legislator "$(PROC)/legislator.csv" \
	  --out-legislator-office "$(PROC)/legislator_office.csv"

etl-validate:
	$(PYTHON) "$(ROOT)/etl/scripts/validate_outputs.py" \
	  --wda "$(PROC)/wda.geojson" \
	  --assembly "$(PROC)/assembly.geojson" \
	  --senate "$(PROC)/senate.geojson" \
	  --wda-ad "$(PROC)/wda_ad_overlap.csv" \
	  --wda-sd "$(PROC)/wda_sd_overlap.csv"

etl-manifest:
	$(PYTHON) "$(ROOT)/etl/scripts/write_manifest.py" \
	  --processed-dir "$(PROC)" \
	  --out "$(PROC)/manifest.json"

etl-report:
	$(PYTHON) "$(ROOT)/etl/scripts/generate_qa_report.py" \
	  --processed-dir "$(PROC)" \
	  --out "$(PROC)/qa_report.md"

etl-all: etl-wda etl-overlaps etl-contacts etl-validate etl-manifest etl-report

etl-refresh-all: etl-refresh-official etl-all

etl-demo-all: etl-demo-raw etl-wda etl-overlaps etl-contacts
	$(PYTHON) "$(ROOT)/etl/scripts/validate_outputs.py" \
	  --wda "$(PROC)/wda.geojson" \
	  --assembly "$(PROC)/assembly.geojson" \
	  --senate "$(PROC)/senate.geojson" \
	  --wda-ad "$(PROC)/wda_ad_overlap.csv" \
	  --wda-sd "$(PROC)/wda_sd_overlap.csv" \
	  --expected-wda 3 --expected-assembly 2 --expected-senate 2
	$(PYTHON) "$(ROOT)/etl/scripts/write_manifest.py" \
	  --processed-dir "$(PROC)" \
	  --out "$(PROC)/manifest.json"

local-board-meetings-dry-run:
	$(PYTHON) -m etl.local_board_meetings.runner

local-board-meetings-live-smoke:
	$(PYTHON) -m etl.local_board_meetings.runner --live --limit 3

test:
	$(PYTHON) -m unittest discover -s tests
