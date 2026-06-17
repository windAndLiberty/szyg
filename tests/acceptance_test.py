#!/usr/bin/env python3
"""
szyg Acceptance Test Suite — run on Windows client
Tests all core APIs with pass/fail reporting
"""
import json, sys, os, time, urllib.request, urllib.error, urllib.parse

os.environ["SZYG_DATA_DIR"] = "C:/szyg/data"
BASE = "http://localhost:8000"
PASS, FAIL = 0, 0
TOKEN = ""
HEADERS = {}

def test(name, fn):
    global PASS, FAIL
    try:
        fn()
        print(f"  PASS {name}")
        PASS += 1
    except Exception as e:
        print(f"  FAIL {name}: {e}")
        FAIL += 1

def api(method, path, data=None, expect_code=200, params=None):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers={**HEADERS, "Content-Type": "application/json"}, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        assert resp.status == expect_code, f"Expected {expect_code}, got {resp.status}"
        return json.loads(resp.read()) if resp.status != 204 else None
    except urllib.error.HTTPError as e:
        if e.code == expect_code:
            return json.loads(e.read()) if e.code != 204 else None
        raise

def check(condition, msg):
    assert condition, msg

def check_eq(actual, expected, msg):
    assert actual == expected, f"{msg}: expected {expected}, got {actual}"


# ═══════════════════════════════════════════
# 1. SYSTEM
# ═══════════════════════════════════════════
def test_health():
    r = api("GET", "/api/health")
    check_eq(r["status"], "ok", "health status")
    check("version" in r, "version present")

def test_root():
    r = api("GET", "/")
    check_eq(r["name"], "szyg", "root name")

def test_config():
    r = api("GET", "/api/config")
    check(isinstance(r, dict), "config is dict")


# ═══════════════════════════════════════════
# 2. AUTH
# ═══════════════════════════════════════════
def test_login_ok():
    global TOKEN, HEADERS
    r = api("POST", "/api/auth/login", {"username": "admin", "password": "admin123"})
    check("access_token" in r, "token present")
    check_eq(r["user"]["username"], "admin", "username")
    check_eq(r["user"]["role"], "admin", "role")
    TOKEN = r["access_token"]
    HEADERS = {"Authorization": f"Bearer {TOKEN}"}

def test_login_fail():
    api("POST", "/api/auth/login", {"username": "admin", "password": "wrong"}, expect_code=401)

def test_session():
    r = api("GET", "/api/auth/session")
    check_eq(r["username"], "admin", "session username")

def test_users_list():
    r = api("GET", "/api/auth/users")
    check(len(r) >= 1, "at least 1 user")


# ═══════════════════════════════════════════
# 3. TOOLS
# ═══════════════════════════════════════════
def test_tools_catalog():
    r = api("GET", "/api/tools/catalog")
    check(len(r) == 8, f"8 tools, got {len(r)}")

def test_tools_categories():
    r = api("GET", "/api/tools/categories")
    check("ai" in r, "ai category present")

def test_tools_stats():
    r = api("GET", "/api/tools/stats")
    check(r["tools_total"] >= 8, "tools_total >= 8")


# ═══════════════════════════════════════════
# 4. AGENTS
# ═══════════════════════════════════════════
def test_agents_list():
    r = api("GET", "/api/agents/list")
    check(len(r) == 12, f"12 agents, got {len(r)}")

def test_agents_tiers():
    r = api("GET", "/api/agents/tiers")
    check(len(r) == 3, "3 tiers")

def test_agents_filter():
    r = api("GET", "/api/agents/list?tier=domain")
    check(len(r) >= 3, f"domain tier: >=3 agents, got {len(r)}")

def test_agents_detail():
    r = api("GET", "/api/agents/copywriter")
    check("system_prompt" in r, "system_prompt present")


# ═══════════════════════════════════════════
# 5. SCHEDULER
# ═══════════════════════════════════════════
def test_scheduler_jobs():
    r = api("GET", "/api/scheduler/jobs")
    check(len(r) == 5, f"5 demo jobs, got {len(r)}")

def test_scheduler_execute():
    r = api("GET", "/api/scheduler/jobs")
    job_id = r[0]["id"]
    x = api("POST", f"/api/scheduler/jobs/{job_id}/execute")
    check(x["status"] == "success", "execution success")

def test_scheduler_stats():
    r = api("GET", "/api/scheduler/stats")
    check(r["total_jobs"] == 5, "total_jobs=5")


# ═══════════════════════════════════════════
# 6. PUBLISHER
# ═══════════════════════════════════════════
def test_publisher_create():
    r = api("POST", "/api/publisher/contents", params={"title":"Test","body":"test body","content_type":"post","platforms":"all","tags":"test"})
    check(r["title"] == "Test", "title match")
    return r["id"]

def test_publisher_pipeline():
    # Create → submit → approve → publish
    cid = test_publisher_create()
    r = api("POST", f"/api/publisher/contents/{cid}/submit")
    check_eq(r["status"], "pending", "submit status")
    r = api("POST", f"/api/publisher/contents/{cid}/approve")
    check_eq(r["status"], "approved", "approve status")
    r = api("POST", f"/api/publisher/contents/{cid}/publish")
    check(r.get("ok"), "publish ok")

def test_publisher_ai_generate():
    r = api("POST", "/api/publisher/ai-generate", params={"topic":"test","agent_id":"copywriter"})
    check(r["ai_generated"], "ai_generated flag")


# ═══════════════════════════════════════════
# 7. BRAIN
# ═══════════════════════════════════════════
def test_brain_status():
    r = api("GET", "/api/brain/status")
    check_eq(r["engine"], "hermes-agent", "engine")
    check(r["mcp_servers"] >= 6, f"6+ MCP servers, got {r['mcp_servers']}")

def test_brain_mcp():
    r = api("GET", "/api/brain/mcp")
    check(len(r) >= 1, "MCP servers listed")


# ═══════════════════════════════════════════
# 8. HUB
# ═══════════════════════════════════════════
def test_hub_list():
    r = api("GET", "/api/hub/list")
    check(len(r) >= 20, f"20+ hub tools, got {len(r)}")

def test_hub_categories():
    r = api("GET", "/api/hub/categories")
    check(len(r) >= 5, "5+ categories")


# ═══════════════════════════════════════════
# 9. OEM
# ═══════════════════════════════════════════
def test_oem_config():
    r = api("GET", "/api/oem/config/default")
    check("name" in r, "name present")
    check("theme" in r, "theme present")


# ═══════════════════════════════════════════
# 10. ANNOUNCEMENTS
# ═══════════════════════════════════════════
def test_announce_list():
    r = api("GET", "/api/announce/list")
    check(len(r) >= 1, "at least 1 announcement")


# ═══════════════════════════════════════════
# 11. CLIENT
# ═══════════════════════════════════════════
def test_client_status():
    r = api("GET", "/api/client/status")
    check_eq(r["os"], "nt", "Windows OS")
    check(isinstance(r["ollama"], bool), "ollama bool")

def test_client_ollama_models():
    r = api("GET", "/api/client/ollama/models")
    if "error" not in r:
        check(len(r.get("models", [])) >= 1, "at least 1 Ollama model")
    else:
        print(f"    (Ollama offline: {r['error']})")

def test_client_ollama_chat():
    r = api("POST", "/api/client/ollama/chat", params={"prompt":"say hello","model":"qwen2.5:7b"})
    if "error" not in r:
        check(len(r.get("response", "")) > 5, "meaningful response")
    else:
        print(f"    (Ollama offline: {r['error']})")


# ═══════════════════════════════════════════
# 12. ERROR HANDLING
# ═══════════════════════════════════════════
def test_404():
    api("GET", "/api/nonexistent", expect_code=404)

def test_auth_required():
    global HEADERS
    old = HEADERS
    HEADERS = {}
    api("GET", "/api/auth/users", expect_code=401)
    HEADERS = old


# ═══════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  szyg ACCEPTANCE TEST SUITE")
    print("=" * 60)

    suites = [
        ("System",     [test_health, test_root, test_config]),
        ("Auth",       [test_login_ok, test_login_fail, test_session, test_users_list]),
        ("Tools",      [test_tools_catalog, test_tools_categories, test_tools_stats]),
        ("Agents",     [test_agents_list, test_agents_tiers, test_agents_filter, test_agents_detail]),
        ("Scheduler",  [test_scheduler_jobs, test_scheduler_execute, test_scheduler_stats]),
        ("Publisher",  [test_publisher_create, test_publisher_pipeline]),
        ("Brain",      [test_brain_status, test_brain_mcp]),
        ("Hub",        [test_hub_list, test_hub_categories]),
        ("OEM",        [test_oem_config]),
        ("Announce",   [test_announce_list]),
        ("Client",     [test_client_status, test_client_ollama_models, test_client_ollama_chat]),
        ("Errors",     [test_404, test_auth_required]),
    ]

    for name, tests in suites:
        print(f"\n── {name} ──")
        for t in tests:
            test(t.__name__, t)

    print(f"\n{'=' * 60}")
    print(f"  PASS: {PASS}  FAIL: {FAIL}  TOTAL: {PASS+FAIL}")
    print(f"{'=' * 60}")

    sys.exit(0 if FAIL == 0 else 1)
