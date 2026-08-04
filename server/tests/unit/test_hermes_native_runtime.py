from __future__ import annotations

import json
from pathlib import Path

from szyg.hermes_capabilities import get_hermes_capability_registry
from szyg.hermes_process_manager import HermesProcessManager


ROOT = Path(__file__).resolve().parents[3]


def test_upstream_release_is_pinned_and_licensed():
    lock = json.loads((ROOT / "server" / "vendor" / "hermes-agent.lock.json").read_text(encoding="utf-8"))
    assert lock["version"] == "0.19.1"
    assert lock["tag"] == "v2026.7.30"
    assert len(lock["archive_sha256"]) == 64
    assert (ROOT / "server" / "vendor" / "hermes_agent" / "LICENSE").is_file()


def test_business_capabilities_are_dynamic_and_context_bound():
    items = get_hermes_capability_registry().list()
    assert len(items) >= 45
    assert all("name" in item and "parameters" in item for item in items)
    assert any(item["confirmation_required"] for item in items)
    domains = {item["domain"] for item in items}
    assert {
        "content", "knowledge", "acquisition", "customers", "workflows",
        "materials", "publishing", "private_domain", "intelligence", "insights",
    } <= domains


def test_process_manager_uses_isolated_environment_in_development():
    command = HermesProcessManager()._command()
    assert command[-1].endswith("hermes_runtime_entry.py")
    assert ".hermes-venv" in command[0] or command[0].endswith("python.exe")


def test_release_build_has_single_computer_use_runtime():
    package = json.loads((ROOT / "electron" / "package.json").read_text(encoding="utf-8"))
    resources = json.dumps(package["build"]["extraResources"])
    assert "runtime/hermes/hermes-runtime" in resources
    assert "providers/cua" in resources
    assert "terminator" not in resources.lower()
    assert "omniparser" not in resources.lower()
    assert package["version"] == "1.1.0"


def test_runtime_integrity_manifest_covers_agent_and_driver():
    script = (ROOT / "electron" / "scripts" / "build-runtime-manifest.cjs").read_text(encoding="utf-8")
    for required in ("hermes-runtime.exe", "cua-driver.exe", "cua-driver-uia.exe", "upstream.lock.json"):
        assert required in script


def test_legacy_agent_and_visual_runtime_are_not_routable():
    assert not (ROOT / "server" / "szyg" / "api" / "hermes_chat.py").exists()
    assert not (ROOT / "server" / "szyg" / "brain_hermes.py").exists()
    assert not (ROOT / "server" / "szyg" / "hermes_runtime.py").exists()
    main = (ROOT / "electron" / "main.js").read_text(encoding="utf-8")
    assert "SZYG_TERMINATOR_DIR" not in main
    assert "SZYG_OMNIPARSER" not in main
