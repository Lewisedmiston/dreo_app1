PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS vendors (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS catalog_items (
  id INTEGER PRIMARY KEY,
  vendor_id INTEGER NOT NULL REFERENCES vendors(id),
  vendor_name TEXT NOT NULL,
  item_number TEXT NOT NULL,
  description TEXT,
  pack_size_raw TEXT,
  pack_count INTEGER,
  unit_qty REAL,
  unit_uom TEXT,
  case_total_oz REAL,
  case_total_each REAL,
  price REAL NOT NULL,
  price_date TEXT NOT NULL,
  cost_per_oz REAL,
  cost_per_each REAL,
  UNIQUE(vendor_id, item_number, price_date)
);

CREATE INDEX IF NOT EXISTS idx_catalog_vendor ON catalog_items(vendor_id);

CREATE TABLE IF NOT EXISTS ingredients (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  locked_vendor_id INTEGER,
  locked_item_number TEXT,
  lock_mode TEXT DEFAULT 'LOCK', -- LOCK or CHEAPEST
  last_cost_per_oz REAL,
  last_cost_per_each REAL,
  last_updated TEXT
);

CREATE TABLE IF NOT EXISTS ingredient_aliases (
  id INTEGER PRIMARY KEY,
  ingredient_id INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
  alias TEXT NOT NULL,
  UNIQUE(ingredient_id, alias)
);

CREATE TABLE IF NOT EXISTS recipes (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  menu_price REAL DEFAULT 0,
  yield_factor REAL DEFAULT 1.0 -- e.g., 0.9 for 10% loss
);

CREATE TABLE IF NOT EXISTS recipe_lines (
  id INTEGER PRIMARY KEY,
  recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
  line_type TEXT NOT NULL, -- INGREDIENT or SUBRECIPE
  ref_id INTEGER NOT NULL, -- ingredient_id or recipe_id
  qty REAL NOT NULL,
  uom TEXT NOT NULL DEFAULT 'oz'
);

CREATE TABLE IF NOT EXISTS inventory_locations (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory_stock (
  id INTEGER PRIMARY KEY,
  location_id INTEGER NOT NULL REFERENCES inventory_locations(id),
  ingredient_id INTEGER NOT NULL REFERENCES ingredients(id),
  on_hand_oz REAL DEFAULT 0,
  on_hand_each REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS purchase_orders (
  id INTEGER PRIMARY KEY,
  vendor_id INTEGER NOT NULL REFERENCES vendors(id),
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS po_lines (
  id INTEGER PRIMARY KEY,
  po_id INTEGER NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
  catalog_item_id INTEGER NOT NULL REFERENCES catalog_items(id),
  qty_cases REAL NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS receipts (
  id INTEGER PRIMARY KEY,
  vendor_id INTEGER NOT NULL REFERENCES vendors(id),
  received_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS receipt_lines (
  id INTEGER PRIMARY KEY,
  receipt_id INTEGER NOT NULL REFERENCES receipts(id) ON DELETE CASCADE,
  catalog_item_id INTEGER NOT NULL REFERENCES catalog_items(id),
  qty_cases REAL NOT NULL DEFAULT 1,
  unit_price REAL
);

CREATE TABLE IF NOT EXISTS waste_logs (
  id INTEGER PRIMARY KEY,
  ingredient_id INTEGER NOT NULL REFERENCES ingredients(id),
  qty_oz REAL,
  qty_each REAL,
  reason TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sales (
  id INTEGER PRIMARY KEY,
  sold_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sales_lines (
  id INTEGER PRIMARY KEY,
  sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
  recipe_id INTEGER NOT NULL REFERENCES recipes(id),
  qty INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS exceptions (
  id INTEGER PRIMARY KEY,
  ex_type TEXT NOT NULL,
  context TEXT,
  created_at TEXT NOT NULL,
  resolved INTEGER DEFAULT 0,
  resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS changelog (
  id INTEGER PRIMARY KEY,
  event_time TEXT NOT NULL,
  actor TEXT DEFAULT 'system',
  action TEXT NOT NULL,
  details TEXT
);
