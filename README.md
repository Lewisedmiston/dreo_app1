# Dreo Kitchen Ops

Mobile-first Streamlit workspace that replaces paper pads for nightly counts, vendor ordering, and catalog ETL. The app runs against a simple CSV “data lake” rooted at `data/` and exposes every artifact for download inside the UI.

## Features

- **Home dashboard** with instant metrics (active SKUs, last inventory snapshot, open order lines) and shortcuts to core flows.
- **Inventory counts** sourced from normalized ingredient data with sticky summaries, shared workspace drafts, and timezone-aware snapshots in `data/inventory_counts/`.
- **Ordering workspace** with vendor filters, par/suggested math, sticky cart totals, and vendor-aware CSV/XLSX exports saved in `data/orders/`.
- **Catalog uploader** powered by JSON presets that validates required fields, logs missing data to the exception queue, dedupes by vendor + item number, and persists to `data/catalogs/<vendor>.csv`.
- **Ingredient master** data editor that normalizes pack/cost fields, recalculates unit cost dynamically, and stays in sync with vendor catalogs.
- **Export center** that produces a consolidated workbook plus ad-hoc ingredient, inventory, order, and vendor catalog downloads with row counts.

## Project layout

```
Home.py                 # Dashboard entry point
common/db.py            # File-backed data helpers, locking, caching
common/utils.py         # Page setup helpers, normalization utilities
pages/                  # Streamlit multipage app (inventory, ordering, upload, etc.)
data/                   # Runtime CSV store (catalogs/, inventory_counts/, orders/, exceptions/)
presets/                # JSON mapping files for vendor uploads
```

## Running locally

### Requirements

- Python 3.11+
- `pip install -r requirements.txt`
- `streamlit` CLI available on the `PATH`

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# optional: override the data directory or timezone
export DREO_DATA_DIR="/path/to/data"
export TZ="America/New_York"

streamlit run Home.py --server.port=3000 --server.address=0.0.0.0
```

Data files (catalogs, ingredient master, order exports, inventory snapshots, exception log) are written into the directory referenced by `DREO_DATA_DIR` (defaults to `./data`). Commit the directory structure but keep the generated CSVs out of version control.

Run tests with:

```bash
pytest
```

## Running on Replit

1. Click the **Run** button (or execute the provided workflow). The command mirrors the local experience:
   ```bash
   streamlit run Home.py --server.port=3000 --server.address=0.0.0.0
   ```
2. Replit automatically exposes port 3000; open the webview to interact with the app.
3. Persistent data lives under `/home/runner/workspace/data/` with sub-folders for `catalogs/`, `inventory_counts/`, and `orders/`. You can download the latest artifacts from the in-app **⬇️ Export** page.

## Acceptance criteria reference

- Upload a preset-backed vendor file with valid price/date columns → import completes with created/updated counts, invalid rows are logged to the exception queue, and nothing is silently defaulted.
- Record a walk-in inventory count → save draft, submit, and confirm a timezone-aware CSV appears under `data/inventory_counts/`.
- Build a Sysco order → export to CSV/XLSX, files land in `data/orders/` and are immediately downloadable in-app.
- Cold start stays snappy (cached reads, minimal reruns) and the UI uses large tap targets, sticky summary bars, and inline toasts for error handling.
