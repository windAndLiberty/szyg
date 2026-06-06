import os, json, sys
from pathlib import Path
sys.path.insert(0, "D:/szyg/server")

from szyg.data_path import DATA_DIR, get_data_dir
print(f"data_path DATA_DIR: {DATA_DIR}")
print(f"get_data_dir(): {get_data_dir()}")

# Check what tools_routes actually uses
from szyg.api.tools_routes import TOOLS_FILE, INSTALL_FILE, _read_json
print(f"TOOLS_FILE: {TOOLS_FILE} (exists: {TOOLS_FILE.exists()})")
if TOOLS_FILE.exists():
    items = _read_json(TOOLS_FILE, [])
    print(f"items: {len(items)}")
else:
    print("TOOLS_FILE NOT FOUND!")
    
# Try hardcoded path
p = Path("D:/szyg/data/tools.json")
print(f"hardcoded: {p} exists={p.exists()}")
