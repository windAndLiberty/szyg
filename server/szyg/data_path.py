"""Cross-platform data path resolution"""
import os
from pathlib import Path

def get_data_dir() -> Path:
    # Priority: env var > project-relative > D:\szyg > C:\szyg (legacy)
    env_dir = (os.environ.get("SZYG_DATA_DIR", "") or "").strip()
    if env_dir:
        p = Path(env_dir).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        return p
    # Project-relative (works from server/szyg/data_path.py → ../../data)
    proj = Path(__file__).parent.parent.parent / "data"
    if (proj / "tools.json").exists():
        return proj
    # Windows: D:\szyg\data
    win_d = Path("D:/szyg/data")
    if (win_d / "tools.json").exists():
        return win_d
    # Windows: C:\szyg\data (legacy)
    win_c = Path("C:/szyg/data")
    if (win_c / "tools.json").exists():
        return win_c
    # Linux: /opt/szyg/data
    lin = Path("/opt/szyg/data")
    if (lin / "tools.json").exists():
        return lin
    # Last resort
    return proj if proj.exists() else Path("data")

DATA_DIR = get_data_dir()
