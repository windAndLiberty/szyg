import sys, os, json, asyncio
os.environ["SZYG_DATA_DIR"] = "D:/szyg/data"
sys.path.insert(0, "D:/szyg/server")

from pathlib import Path

# Direct file read
p = Path("D:/szyg/data/tools.json")
print(f"Direct read: exists={p.exists()}, items={len(json.loads(p.read_text(encoding='utf-8')))}")

# Via _read_json
from szyg.api.tools_routes import _read_json, TOOLS_FILE
items = _read_json(TOOLS_FILE, [])
print(f"_read_json: TOOLS_FILE={TOOLS_FILE}, items={len(items)}")

# Via catalog function
from szyg.api.tools_routes import catalog as tools_catalog_func
async def test():
    result = await tools_catalog_func()
    print(f"catalog endpoint: {len(result)} items")
asyncio.run(test())

# Same for agents
from szyg.api.agent_routes import _read_agents, AGENTS_FILE
agents = _read_agents()
print(f"agents: AGENTS_FILE={AGENTS_FILE}, items={len(agents)}")
