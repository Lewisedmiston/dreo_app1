"""
Vendor preset functionality for catalog uploads
"""
import json
from pathlib import Path
from typing import Dict, Any

def load_vendor_presets() -> Dict[str, Any]:
    """Load vendor presets from JSON file"""
    try:
        presets_file = Path("presets/vendor_presets.json")
        if presets_file.exists():
            with open(presets_file, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    
    # Fallback to hardcoded presets
    return {
        "PFG": {
            "description": "Performance Food Group mapping",
            "columns": {
                "item_number": "Item #",
                "item_description": "Description", 
                "pack_size_str": "Pack Size",
                "case_price": "Case Price",
                "vendor_name": "PFG",
                "price_date": "Price Date"
            },
            "required": ["Item #", "Description", "Case Price"],
            "auto_fields": {
                "vendor_name": "PFG"
            }
        },
        "Sysco": {
            "description": "Sysco Foods mapping", 
            "columns": {
                "item_number": "SUPC",
                "item_description": "Product Name",
                "pack_size_str": "Pack",
                "case_price": "Price",
                "vendor_name": "Sysco",
                "price_date": "Date"
            },
            "required": ["SUPC", "Product Name", "Price"],
            "auto_fields": {
                "vendor_name": "Sysco"
            }
        },
        "Produce": {
            "description": "Produce vendor mapping",
            "columns": {
                "item_number": "SKU",
                "item_description": "Item",
                "pack_size_str": "Unit",
                "case_price": "Cost",
                "vendor_name": "Produce",
                "price_date": "Updated"
            },
            "required": ["SKU", "Item", "Cost"],
            "auto_fields": {
                "vendor_name": "Produce"
            }
        }
    }

def get_preset_for_vendor(vendor: str) -> Dict[str, Any]:
    """Get preset configuration for a specific vendor"""
    presets = load_vendor_presets()
    return presets.get(vendor, {})

def suggest_vendor_from_filename(filename: str) -> str:
    """Suggest vendor based on filename"""
    filename_lower = filename.lower()
    
    if 'pfg' in filename_lower or 'performance' in filename_lower:
        return 'PFG'
    elif 'sysco' in filename_lower:
        return 'Sysco'
    elif 'produce' in filename_lower:
        return 'Produce'
    
    return 'Custom'

def apply_preset_mapping(df, vendor: str) -> tuple[dict, list]:
    """
    Apply vendor preset to DataFrame and return column mapping and missing columns
    Returns (column_mapping, missing_required_columns)
    """
    preset = get_preset_for_vendor(vendor)
    if not preset:
        return {}, []
    
    column_mapping = {}
    preset_columns = preset.get('columns', {})
    required_columns = preset.get('required', [])
    
    # Create reverse mapping from preset columns to df columns
    df_columns_lower = {col.lower(): col for col in df.columns}
    
    # Find matches
    for target_field, expected_name in preset_columns.items():
        # Try exact match first
        if expected_name in df.columns:
            column_mapping[target_field] = expected_name
        else:
            # Try case-insensitive match
            expected_lower = expected_name.lower()
            if expected_lower in df_columns_lower:
                column_mapping[target_field] = df_columns_lower[expected_lower]
    
    # Check for missing required columns
    missing_required = []
    for req_col in required_columns:
        if req_col not in df.columns:
            # Check if any of our mapped columns would satisfy this requirement
            found = False
            for target_field, mapped_col in column_mapping.items():
                if preset_columns.get(target_field) == req_col:
                    found = True
                    break
            
            if not found:
                missing_required.append(req_col)
    
    return column_mapping, missing_required