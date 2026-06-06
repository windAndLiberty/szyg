"""
Tool Runtime — plugin execution engine
Handles local tool launching, process tracking, install/uninstall
"""
import os, json, shutil, subprocess, logging
from pathlib import Path
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("SZYG_DATA_DIR", "data"))
TOOLS_DIR = DATA_DIR / "tools"
INSTALL_FILE = DATA_DIR / "install.json"


class ToolRuntime:
    """Manages local tool installation and execution"""

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or DATA_DIR
        self.tools_dir = self.base_dir / "tools"
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        self._processes: dict[str, subprocess.Popen] = {}

    def list_installed(self) -> list[dict]:
        if not INSTALL_FILE.exists():
            return []
        return json.loads(INSTALL_FILE.read_text(encoding='utf-8'))

    def is_installed(self, soft_id: str) -> bool:
        for item in self.list_installed():
            if item.get("soft_id") == soft_id:
                return True
        return False

    def install_from_zip(self, zip_path: str, soft_id: str, soft_code: str, version: str) -> dict:
        """Extract a tool ZIP and register it"""
        import zipfile
        target_dir = self.tools_dir / soft_code
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True)

        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(target_dir)

        return self._register(soft_id, soft_code, version, str(target_dir))

    def _register(self, soft_id: str, soft_code: str, version: str, file_path: str) -> dict:
        installed = self.list_installed()
        installed = [i for i in installed if i.get("soft_id") != soft_id]
        entry = {
            "soft_id": soft_id, "soft_code": soft_code,
            "version": version, "file_path": file_path,
            "installed_at": datetime.now().isoformat(),
        }
        installed.append(entry)
        INSTALL_FILE.parent.mkdir(parents=True, exist_ok=True)
        INSTALL_FILE.write_text(json.dumps(installed, ensure_ascii=False, indent=2), encoding="utf-8")
        return entry

    def uninstall(self, soft_id: str) -> bool:
        installed = self.list_installed()
        entry = next((i for i in installed if i.get("soft_id") == soft_id), None)
        if entry:
            target = Path(entry["file_path"])
            if target.exists():
                shutil.rmtree(target)
            installed = [i for i in installed if i.get("soft_id") != soft_id]
            INSTALL_FILE.write_text(json.dumps(installed, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        return False

    def launch(self, soft_id: str) -> Optional[subprocess.Popen]:
        """Launch a tool by soft_id"""
        installed = self.list_installed()
        entry = next((i for i in installed if i.get("soft_id") == soft_id), None)
        if not entry:
            return None

        tool_path = Path(entry["file_path"])
        exe_path = tool_path / "run.exe"
        if not exe_path.exists():
            exe_path = tool_path / "main.py"
        if not exe_path.exists():
            # Try to find any executable
            for f in tool_path.iterdir():
                if f.suffix in ('.exe', '.py', '.sh', '.bat'):
                    exe_path = f
                    break

        if not exe_path.exists():
            raise FileNotFoundError(f"No executable found in {tool_path}")

        if exe_path.suffix == '.py':
            proc = subprocess.Popen(
                ["python3", str(exe_path)],
                cwd=str(tool_path),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
        else:
            proc = subprocess.Popen(
                [str(exe_path)],
                cwd=str(tool_path),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
        self._processes[soft_id] = proc
        return proc

    def stop(self, soft_id: str) -> bool:
        proc = self._processes.pop(soft_id, None)
        if proc:
            proc.terminate()
            return True
        return False

    def get_stats(self) -> dict:
        installed = self.list_installed()
        return {
            "tools_installed": len(installed),
            "tools_total": len(list(self.tools_dir.iterdir())) if self.tools_dir.exists() else 0,
            "running": len(self._processes),
        }


# Singleton
_runtime: ToolRuntime | None = None

def get_runtime() -> ToolRuntime:
    global _runtime
    if _runtime is None:
        _runtime = ToolRuntime()
    return _runtime
