# Dreo Kitchen Ops App (MVP)

Chef-friendly Streamlit app to replace Excel costing workflows.

## Quick Start (Windows PowerShell)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
$env:FOOD_COST_TARGET_PCT="35"
streamlit run pages/1_🧾_Upload_Catalogs.py
```

## Structure

- `common/` core modules (db, etl, costing, excel_export, settings, utils)
- `pages/` Streamlit app pages
- `models.sql` schema
- `sample_data/` tiny CSVs to test
