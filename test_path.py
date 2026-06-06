import os, json
from pathlib import Path
env = os.environ.get("SZYG_DATA_DIR", "NOT SET")
candidates = [
    Path(env) if env != "NOT SET" else None,
    Path("data"),
    Path("D:/szyg/data"),
]
for c in candidates:
    if c is None: continue
    f = c / "tools.json"
    print(f"PATH: {c} -> tools.json exists: {f.exists()}")
    if f.exists():
        d = json.loads(open(str(f), encoding='utf-8').read())
        print(f"  items: {len(d)}")
        break
