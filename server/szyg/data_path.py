"""Cross-platform data path resolution"""
import os
from pathlib import Path

def get_data_dir() -> Path:
    # Windows: always try C:\szyg\data first
    win = Path("C:/szyg/data")
    if (win / "tools.json").exists():
        return win
    # Linux: try /opt/szyg/data
    lin = Path("/opt/szyg/data")
    if (lin / "tools.json").exists():
        return lin
    # Env var (strip trailing spaces from Windows batch files)
    env_dir = (os.environ.get("SZYG_DATA_DIR", "") or "").strip()
    if env_dir:
        p = Path(env_dir)
        if (p / "tools.json").exists():
            return p
    # Project-relative fallback
    proj = Path(__file__).parent.parent.parent / "data"
    if (proj / "tools.json").exists():
        return proj
    # Last resort
    return Path("data")

DATA_DIR = get_data_dir()
