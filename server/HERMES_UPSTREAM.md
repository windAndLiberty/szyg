# Hermes Agent — Upstream Reference

- **Project**: Hermes Agent (hermes-agent)
- **Version**: 0.15.1
- **Author**: Nous Research
- **License**: MIT
- **Runtime location**: `server/` (the complete hermes runtime is embedded here)
- **Build config**: `server/pyproject.hermes-agent.toml` (hermes kernel dependencies)
- **szyg integration**: `server/szyg/brain_hermes.py` — HermesBrain class wraps hermes as szyg's AI kernel

## Project Configuration

- `pyproject.toml` (root) — szyg application project
- `server/pyproject.hermes-agent.toml` — hermes kernel dependencies (embedded runtime)

## Upgrade Procedure

To upgrade hermes to a newer version:

1. Fetch the latest release from upstream
2. Diff the runtime files in `server/` against the new version
3. Port any szyg-specific patches (check `server/szyg/` imports)
4. Update the version number in `server/szyg/brain_hermes.py` (`get_status()`)
5. Update this file with the new version
