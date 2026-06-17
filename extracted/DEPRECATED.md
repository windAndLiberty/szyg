# ⚠️ DEPRECATED — Reference Only

This directory contains the **original reverse-engineering output** and early-stage
implementation from the "数创引擎" analysis phase. The code here is **NOT the running system**.

## What's here

| Path | Description | Status |
|------|-------------|--------|
| `SPEC.md` | Original architecture specification for 域灵 (YuLing) | Reference doc |
| `plan.md` | TDD build plan | Reference doc |
| `acceptance_criteria.md` | Acceptance test criteria | Reference doc |
| `project/yuling/` | Early implementation (package name: `yuling`) | **Stale** — superseded by `server/szyg/` |
| `project/tests/` | Early test suite | **Stale** — superseded by `server/tests/` |
| `project/data/` | Sample/test data from reverse engineering | Reference only |

## Where's the real code?

The active codebase lives in `server/szyg/` (the `szyg` Python package).
The package was renamed from `yuling` → `szyg` to match the project name.

## Why keep this?

- **SPEC.md** documents the original architecture design decisions
- **plan.md** captures the TDD implementation strategy
- The stale `yuling/` code serves as a historical reference for the migration from "域灵" to "szyg"
