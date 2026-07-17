"""Isolated OmniParser HTTP service.

Run with:
    python -m szyg.integrations.omniparser_service

This module lives in szyg so the external OmniParser checkout stays untouched.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel


REPO_ROOT = Path(__file__).resolve().parents[3]
OMNIPARSER_DIR = Path(os.environ.get("SZYG_OMNIPARSER_DIR", "")) if os.environ.get("SZYG_OMNIPARSER_DIR") else REPO_ROOT / "external" / "OmniParser-master"
OMNIPARSER_URL = os.environ.get("SZYG_OMNIPARSER_URL", "http://127.0.0.1:7862")

host_port = OMNIPARSER_URL.rsplit(":", 1)
SERVICE_HOST = os.environ.get("SZYG_OMNIPARSER_HOST", "127.0.0.1")
SERVICE_PORT = int(os.environ.get("SZYG_OMNIPARSER_PORT", host_port[-1].rstrip("/") if len(host_port) == 2 else "7862"))

if str(OMNIPARSER_DIR) not in sys.path:
    sys.path.insert(0, str(OMNIPARSER_DIR))

from util.omniparser import Omniparser  # noqa: E402


class ParseRequest(BaseModel):
    base64_image: str


app = FastAPI(title="szyg OmniParser service")
_parser: Omniparser | None = None


def _config() -> dict:
    return {
        "som_model_path": str(OMNIPARSER_DIR / "weights" / "icon_detect" / "model.pt"),
        "caption_model_name": os.environ.get("SZYG_OMNIPARSER_CAPTION_MODEL", "florence2"),
        "caption_model_path": str(OMNIPARSER_DIR / "weights" / "icon_caption_florence"),
        "device": os.environ.get("SZYG_OMNIPARSER_DEVICE", "cuda" if os.environ.get("CUDA_VISIBLE_DEVICES") else "cpu"),
        "BOX_TRESHOLD": float(os.environ.get("SZYG_OMNIPARSER_BOX_THRESHOLD", "0.05")),
    }


def _get_parser() -> Omniparser:
    global _parser
    if _parser is None:
        _parser = Omniparser(_config())
    return _parser


@app.get("/probe/")
async def probe():
    return {"ok": True, "message": "OmniParser API ready", "source_dir": str(OMNIPARSER_DIR)}


@app.post("/parse/")
async def parse(body: ParseRequest):
    started = time.time()
    som_image_base64, parsed_content_list = _get_parser().parse(body.base64_image)
    return {
        "ok": True,
        "som_image_base64": som_image_base64,
        "parsed_content_list": parsed_content_list,
        "latency": time.time() - started,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=SERVICE_HOST, port=SERVICE_PORT)
