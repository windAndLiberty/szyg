"""Install and invoke the independent, versioned OpenMontage interpreter."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from szyg.data_path import DATA_DIR

COMMIT = "2e003e65fa99a0f329478a2c1cdcf26bc481933a"
CHECKSUM = "51babb685fa49586ba40e11615cf401ee539956b408ee11c8ae557e8ab1a16c8"
SOURCE = "https://github.com/OpenMontageInc/OpenMontage"
ARCHIVE = f"https://codeload.github.com/OpenMontageInc/OpenMontage/tar.gz/{COMMIT}"
WORKER = Path(__file__).parent / "resources" / "openmontage" / "worker.py"
STORE = DATA_DIR / "openmontage"
DEV = Path(__file__).resolve().parents[2] / ".local-dev"


@contextlib.contextmanager
def file_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt

            if path.stat().st_size == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _venv(directory: Path) -> Path:
    return directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def runtime() -> tuple[Path, Path] | None:
    directory = STORE / "runtime" / COMMIT
    if (directory / "ready").is_file() and _venv(directory / "env").is_file():
        return directory / "source", _venv(directory / "env")
    source = DEV / "openmontage-upstream"
    python = _venv(DEV / "openmontage-env")
    # Only a checkout at the supported revision may act as the development runtime.
    if python.is_file() and (source / ".git").is_dir():
        revision = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            capture_output=True,
            timeout=5,
        )
        if revision.stdout.decode().strip() == COMMIT:
            return source, python
    return None


def media_command(name: str) -> str | None:
    ffmpeg = os.getenv("SZYG_FFMPEG_PATH")
    if ffmpeg:
        other = Path(ffmpeg).with_name(name + (".exe" if os.name == "nt" else ""))
        if other.is_file():
            return str(other)
    return shutil.which(name)


def capabilities() -> dict:
    paths = runtime()
    media = {name: bool(media_command(name)) for name in ["ffmpeg", "ffprobe"]}
    return {
        "engine": "OpenMontage",
        "revision": COMMIT,
        "installed": bool(paths),
        "ready": bool(paths and all(media.values())),
        "dependencies": media,
        "source_url": f"{SOURCE}/tree/{COMMIT}",
        "license": "AGPL-3.0",
        "license_url": f"{SOURCE}/blob/{COMMIT}/LICENSE",
        "installation": "director.install",
        "installation_hint": "准备 Python 3.11–3.13、FFmpeg 和 ffprobe 后安装本地导演引擎。供应商密钥可在运行目录的 .env 中配置。",
        "configuration_directory": str(paths[0]) if paths else None,
        "aspects": ["16:9", "9:16", "1:1"],
        "pipeline_count": 12,
    }


def _host_python() -> str:
    paths = ([sys.executable] if not getattr(sys, "frozen", False) else []) + [
        shutil.which(v)
        for v in ("python3.12", "python3.11", "python3.13", "python3", "python")
    ]
    for path in filter(None, paths):
        try:
            check = subprocess.run(
                [
                    path,
                    "-c",
                    "import ensurepip,sys;sys.exit(not ((3,11)<=sys.version_info[:2]<=(3,13)))",
                ],
                capture_output=True,
                timeout=8,
            )
            if check.returncode == 0:
                return path
        except (OSError, subprocess.TimeoutExpired):
            continue
    raise ValueError("请先安装 Python 3.11–3.13（包含 venv 和 pip），然后重试安装。")


def install_runtime() -> dict:
    target = STORE / "runtime" / COMMIT
    with file_lock(target.parent / ".install.lock"):
        if runtime():
            return capabilities()
        python = _host_python()
        target.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=target.parent) as temp:
            scratch = Path(temp)
            archive = scratch / "source.tar.gz"
            with (
                urllib.request.urlopen(ARCHIVE, timeout=90) as response,
                archive.open("wb") as out,
            ):
                shutil.copyfileobj(response, out)
            with archive.open("rb") as handle:
                if hashlib.file_digest(handle, "sha256").hexdigest() != CHECKSUM:
                    raise ValueError("上游源码校验不一致，请重新安装。")
            with tarfile.open(archive, "r:gz") as bundle:
                bundle.extractall(scratch, filter="data")
            source = target / "source"
            if not source.exists():
                (scratch / f"OpenMontage-{COMMIT}").rename(source)
        env = _venv(target / "env")
        subprocess.run(
            [python, "-m", "venv", str(target / "env")],
            check=True,
            capture_output=True,
            timeout=120,
        )
        subprocess.run(
            [
                str(env),
                "-m",
                "pip",
                "--disable-pip-version-check",
                "install",
                "-r",
                str(source / "requirements.txt"),
                "-c",
                str(WORKER.with_name("constraints.txt")),
            ],
            check=True,
            capture_output=True,
            timeout=1200,
        )
        # Verify the upstream registry actually imports before reporting a successful installation.
        subprocess.run(
            [
                str(env),
                "-c",
                "from tools.tool_registry import registry; registry.discover()",
            ],
            cwd=source,
            check=True,
            capture_output=True,
            timeout=90,
        )
        (target / "ready").write_text(COMMIT, encoding="ascii")
        return capabilities()


def invoke(request: dict, cwd: Path, timeout=300):
    paths = runtime()
    if not paths:
        raise ValueError("请先安装本地 OpenMontage 导演引擎。")
    env = {
        k: v
        for k, v in os.environ.items()
        if k.upper()
        in {
            "PATH",
            "HOME",
            "USERPROFILE",
            "APPDATA",
            "LOCALAPPDATA",
            "TEMP",
            "TMP",
            "TMPDIR",
            "WINDIR",
            "SYSTEMROOT",
            "LANG",
            "LC_ALL",
            "SYSTEMDRIVE",
            "FONTCONFIG_PATH",
            "LD_LIBRARY_PATH",
            "SSL_CERT_FILE",
            "REQUESTS_CA_BUNDLE",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "NO_PROXY",
        }
    }
    bypass = env.get("NO_PROXY", env.get("no_proxy", ""))
    env["no_proxy"] = env["NO_PROXY"] = ",".join(
        filter(None, [bypass, "127.0.0.1", "localhost", "::1"])
    )
    ffmpeg = media_command("ffmpeg")
    if ffmpeg:
        env["PATH"] = str(Path(ffmpeg).parent) + os.pathsep + env.get("PATH", "")
    env["OPENMONTAGE_PROJECTS_DIR"] = str(STORE / "projects")
    env["PYTHONIOENCODING"] = "utf-8"
    process = subprocess.Popen(
        [str(paths[1]), "-IB", str(WORKER), str(paths[0])],
        cwd=cwd,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=os.name != "nt",
    )
    try:
        raw, _ = process.communicate(
            json.dumps(request, ensure_ascii=True).encode(), timeout=timeout
        )
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True
            )
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        raise ValueError("OpenMontage 执行超时，请检查项目状态。") from None
    if process.returncode or not raw or len(raw) > 12_000_000:
        raise ValueError("OpenMontage 未能完成工作，请检查本地运行环境。")
    message = json.loads(raw)
    if not message.get("ok"):
        raise ValueError(message["message"])
    return message["result"]
