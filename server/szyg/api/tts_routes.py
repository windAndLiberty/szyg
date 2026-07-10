"""Text-to-speech endpoints for content production."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from szyg.integrations.volcengine_client import VolcEngineClient
from szyg.media_storage import get_media_output_dir

router = APIRouter(prefix="/api/tts", tags=["tts"])


class TtsRequest(BaseModel):
    text: str
    voice: str = "female"
    speed: float = 1.0


VOICE_MAP = {
    "female": "zh_female_xiaoyi",
    "male": "zh_male_yuanfeng",
    "child": "zh_female_xiaoyi",
}


@router.post("/synthesize")
async def synthesize(req: TtsRequest):
    text = req.text.strip()
    if not text:
        raise HTTPException(400, "text is required")
    client = VolcEngineClient(output_dir=str(get_media_output_dir("audio")))
    try:
        path = await client.text_to_speech(
            text=text,
            voice_id=VOICE_MAP.get(req.voice, req.voice),
            speed=req.speed,
            output_dir=str(get_media_output_dir("audio")),
        )
    except Exception as exc:
        raise HTTPException(500, str(exc))
    finally:
        await client.close()
    return FileResponse(path, media_type="audio/mpeg", filename=path.split("\\")[-1].split("/")[-1])
