# Dreo Kitchen Ops

Mobile-first Streamlit workspace that replaces paper pads for nightly counts, vendor ordering, and catalog ETL.

## Features

- **Home dashboard** with instant metrics (active SKUs, last inventory snapshot, open order lines) and shortcuts to core flows.
- **Inventory counts** sourced from the latest catalogs/ingredient master with touch-friendly +/- controls, draft persistence, and timestamped snapshots in `data/inventory_counts/`.
- **Ordering workspace** with vendor filters, par/suggested math, sticky cart totals, and CSV/XLSX exports saved in `data/orders/`.
- **Catalog uploader** powered by JSON presets (ships with PFG, Sysco, Produce examples) that dedupes by vendor + item number, writes to `data/catalogs/<vendor>.csv`, and feeds the dynamic vendor pickers across the app.
- **Ingredient master** data editor that calculates cost-per-count and stays in sync with vendor links.
- **Export center** to download the most recent ingredient master, inventory snapshot, order export, or any vendor catalog file.

## Project layout

```
Home.py                 # Dashboard entry point
common/db.py            # File-backed data helpers & toast utilities
common/presets.py       # Vendor column-mapping presets loader
pages/                  # Streamlit multipage app (inventory, ordering, upload, etc.)
data/                   # Runtime CSV store (catalogs/, inventory_counts/, orders/)
presets/                # JSON mapping files for vendor uploads
```

## Running locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run Home.py --server.port=3000 --server.address=0.0.0.0
```

Data files (catalogs, ingredient master, order exports, inventory snapshots) are written into the `data/` directory alongside the codebase. Commit the directory structure but keep the CSVs out of version control.

## Running on Replit

1. Click the **Run** button (or execute the provided workflow). The command mirrors the local experience:
   ```bash
   streamlit run Home.py --server.port=3000 --server.address=0.0.0.0
   ```
2. Replit automatically exposes port 3000; open the webview to interact with the app.
3. Persistent data lives under `/home/runner/workspace/data/` with sub-folders for `catalogs/`, `inventory_counts/`, and `orders/`. You can download the latest artifacts from the in-app **⬇️ Export** page.

## Acceptance criteria reference

- Upload a preset-backed vendor file (with or without `price_date`) → import completes with created/updated counts and defaults missing dates to today.
- Record a walk-in inventory count → save draft, submit, and confirm a timestamped CSV appears under `data/inventory_counts/`.
- Build a Sysco order → export to CSV/XLSX, files land in `data/orders/` and are immediately downloadable in-app.
- Cold start stays snappy (cached reads, minimal reruns) and the UI uses large tap targets, sticky action bars, and inline toasts for error handling.
