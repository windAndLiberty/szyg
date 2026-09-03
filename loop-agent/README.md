# orchestration

Explorations in agent loop engineering with LangChain / LangGraph / Deep Agents.

## Run the examples

```bash
# Deterministic state loop (no API key required)
uv run python loop_patterns.py --example deterministic

# ReAct loop with an LLM
export ANTHROPIC_API_KEY=...
uv run python loop_patterns.py --example react --prompt "What is loop engineering?"

# Orchestrator-Worker loop with subagents
uv run python loop_patterns.py --example orch --prompt "Add a function that validates email addresses"
```
