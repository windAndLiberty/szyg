"""Text-to-speech endpoints for content production."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from szyg.integrations.volcengine_client import VolcEngineClient
from szyg.media_storage import get_media_output_dir, media_url_for_path

router = APIRouter(prefix="/api/tts", tags=["tts"])

MAX_TTS_TEXT_CHARS = 3000
MAX_PREVIEW_TEXT_CHARS = 120
DEMO_TEXT = "您好，我是 SZYG 数字员工，很高兴为您服务。"


class TtsRequest(BaseModel):
    text: str
    voice: str = "warm_female"
    voice_prompt: str = ""
    scene: str = "short_video"
    emotion: str = "neutral"
    speed: float = 1.0
    pitch: int = 0
    format: Literal["mp3"] = "mp3"
    preview: bool = False


class InterpretVoiceRequest(BaseModel):
    voice_prompt: str
    voice: str = "warm_female"
    scene: str = "short_video"
    emotion: str = "neutral"
    speed: float = 1.0
    pitch: int = 0


class TtsVoice(BaseModel):
    id: str
    name: str
    provider_voice: str
    gender: str
    tags: list[str]
    scene: str
    description: str
    demo_text: str = DEMO_TEXT


class TtsResponse(BaseModel):
    ok: bool
    url: str
    path: str
    filename: str
    voice: str
    emotion: str
    speed: float
    pitch: int
    preview: bool
    estimated_duration: float


class InterpretVoiceResponse(BaseModel):
    voice: str
    emotion: str
    speed: float
    pitch: int
    summary: str
    interpreted_by: str = "rules"


VOICES: list[TtsVoice] = [
    TtsVoice(
        id="warm_female",
        name="温柔女声",
        provider_voice="zh_female_xiaoyi",
        gender="female",
        tags=["温柔", "自然", "小红书", "种草"],
        scene="短视频种草、品牌介绍",
        description="亲和自然的女声，适合产品介绍和生活方式内容。",
    ),
    TtsVoice(
        id="pro_male",
        name="专业男声",
        provider_voice="zh_male_yuanfeng",
        gender="male",
        tags=["专业", "清晰", "商务", "讲解"],
        scene="企业宣传、知识讲解",
        description="清晰稳重的男声，适合企业宣传和专业讲解。",
    ),
    TtsVoice(
        id="energetic_host",
        name="活力主播",
        provider_voice="zh_female_shuangjia",
        gender="female",
        tags=["活力", "带货", "热情", "短视频"],
        scene="抖音带货、活动促销",
        description="节奏更积极，适合直播切片和促销口播。",
    ),
    TtsVoice(
        id="friendly_service",
        name="亲和客服",
        provider_voice="zh_female_xiaoyi",
        gender="female",
        tags=["亲和", "客服", "清楚", "耐心"],
        scene="客服话术、售后说明",
        description="语气友好克制，适合客服、私域和售后说明。",
    ),
    TtsVoice(
        id="calm_business",
        name="沉稳商务",
        provider_voice="zh_male_yuanfeng",
        gender="male",
        tags=["沉稳", "可信", "商务", "品牌"],
        scene="品牌宣传、招商介绍",
        description="稳定、有信任感，适合企业品牌和招商内容。",
    ),
    TtsVoice(
        id="knowledge_teacher",
        name="知识讲解",
        provider_voice="zh_female_linjianvjin",
        gender="female",
        tags=["讲解", "清晰", "课程", "知识"],
        scene="课程、知识科普",
        description="表达清楚、节奏平稳，适合课程和科普内容。",
    ),
    TtsVoice(
        id="sales_pitch",
        name="带货口播",
        provider_voice="zh_female_shuangjia",
        gender="female",
        tags=["带货", "节奏快", "转化", "行动感"],
        scene="电商视频、评论区引导",
        description="更有行动指向，适合短视频带货和转化文案。",
    ),
]

LEGACY_VOICE_MAP = {
    "female": "warm_female",
    "male": "pro_male",
    "child": "warm_female",
}
EMOTIONS = {"neutral", "happy", "sad", "excited", "calm", "angry"}


def _voice_catalog() -> dict[str, TtsVoice]:
    return {voice.id: voice for voice in VOICES}


def _dump_model(model: BaseModel) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _copy_request(req: TtsRequest, update: dict) -> TtsRequest:
    if hasattr(req, "model_copy"):
        return req.model_copy(update=update)
    return req.copy(update=update)


def _normalize_voice_id(voice: str) -> str:
    value = voice.strip() or "warm_female"
    return LEGACY_VOICE_MAP.get(value, value)


def _voice_or_400(voice: str) -> TtsVoice:
    voice_id = _normalize_voice_id(voice)
    item = _voice_catalog().get(voice_id)
    if not item:
        raise HTTPException(400, "voice is not supported")
    return item


def _validate_request(req: TtsRequest) -> str:
    text = req.text.strip()
    if not text:
        raise HTTPException(400, "text is required")
    limit = MAX_PREVIEW_TEXT_CHARS if req.preview else MAX_TTS_TEXT_CHARS
    if len(text) > limit:
        if req.preview:
            text = text[:MAX_PREVIEW_TEXT_CHARS]
        else:
            raise HTTPException(400, f"text is too long, max {MAX_TTS_TEXT_CHARS} chars")
    if req.format != "mp3":
        raise HTTPException(400, "Only mp3 output is supported")
    if req.emotion not in EMOTIONS:
        raise HTTPException(400, "emotion is not supported")
    if req.speed < 0.5 or req.speed > 2.0:
        raise HTTPException(400, "speed must be between 0.5 and 2.0")
    if req.pitch < -100 or req.pitch > 100:
        raise HTTPException(400, "pitch must be between -100 and 100")
    return text


def _estimated_duration(text: str, speed: float) -> float:
    chars_per_second = 4.2 * max(speed, 0.5)
    return round(max(1.0, len(text) / chars_per_second), 1)


async def _interpret_with_local_model(req: InterpretVoiceRequest) -> InterpretVoiceResponse | None:
    prompt = req.voice_prompt.strip()
    if not prompt:
        return None
    try:
        from szyg.integrations.local_llama_runtime import get_local_llama_runtime
        from szyg.integrations.local_small_model_client import LocalSmallModelClient

        system = (
            "你是企业短视频配音参数助手。只输出 JSON，不要输出 Markdown。"
            "JSON 字段必须包含 voice, emotion, speed, pitch, summary。"
            "voice 只能从 warm_female, pro_male, energetic_host, friendly_service, calm_business, knowledge_teacher, sales_pitch 中选择。"
            "emotion 只能从 neutral, happy, sad, excited, calm, angry 中选择。"
            "speed 是 0.5 到 2.0 的数字，pitch 是 -100 到 100 的整数。"
        )
        user = {
            "voice_prompt": prompt,
            "current_voice": req.voice,
            "scene": req.scene,
            "current_emotion": req.emotion,
            "current_speed": req.speed,
            "current_pitch": req.pitch,
        }
        runtime = get_local_llama_runtime()
        state = await runtime.status()
        if not state.get("runtime_ready"):
            started = await runtime.start("qwen3-4b")
            if not started.get("success"):
                return None
        client = LocalSmallModelClient(default_model="qwen3-4b", timeout=30)
        try:
            result = await client.chat(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
                ],
                max_tokens=500,
                temperature=0.25,
            )
        finally:
            await client.close()
        raw = result.get("message", {}).get("content", "")
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return None
        data = json.loads(raw[start:end + 1])
        voice = _normalize_voice_id(str(data.get("voice") or req.voice))
        if voice not in _voice_catalog():
            voice = _normalize_voice_id(req.voice)
        emotion = str(data.get("emotion") or req.emotion)
        if emotion not in EMOTIONS:
            emotion = req.emotion if req.emotion in EMOTIONS else "neutral"
        speed = max(0.5, min(2.0, float(data.get("speed") or req.speed)))
        pitch = max(-100, min(100, int(data.get("pitch") or req.pitch)))
        return InterpretVoiceResponse(
            voice=voice,
            emotion=emotion,
            speed=round(speed, 2),
            pitch=pitch,
            summary=str(data.get("summary") or "已根据声音描述调整配音参数。").strip(),
            interpreted_by="qwen3-4b-local",
        )
    except Exception:
        return None


def _interpret_with_rules(req: InterpretVoiceRequest) -> InterpretVoiceResponse:
    prompt = req.voice_prompt.strip()
    voice = _normalize_voice_id(req.voice)
    emotion = req.emotion if req.emotion in EMOTIONS else "neutral"
    speed = max(0.5, min(2.0, req.speed))
    pitch = max(-100, min(100, req.pitch))
    if any(word in prompt for word in ("女", "温柔", "小红书", "种草")):
        voice = "warm_female"
        emotion = "calm"
        speed = min(speed, 1.0)
    if any(word in prompt for word in ("男", "商务", "专业", "财经")):
        voice = "pro_male"
        emotion = "calm"
    if any(word in prompt for word in ("带货", "热情", "兴奋", "促销", "主播")):
        voice = "sales_pitch"
        emotion = "excited"
        speed = max(speed, 1.12)
        pitch = max(pitch, 20)
    if any(word in prompt for word in ("客服", "亲和", "耐心")):
        voice = "friendly_service"
        emotion = "neutral"
        speed = min(speed, 0.95)
    if any(word in prompt for word in ("慢", "舒缓")):
        speed = min(speed, 0.85)
    if any(word in prompt for word in ("快", "节奏")):
        speed = max(speed, 1.15)
    return InterpretVoiceResponse(
        voice=voice,
        emotion=emotion,
        speed=round(speed, 2),
        pitch=pitch,
        summary="本地小模型不可用，已根据关键词给出配音参数建议。",
        interpreted_by="rules",
    )


@router.get("/voices")
async def voices() -> dict:
    return {"voices": [_dump_model(voice) for voice in VOICES]}


@router.post("/interpret-voice", response_model=InterpretVoiceResponse)
async def interpret_voice(req: InterpretVoiceRequest):
    _voice_or_400(req.voice)
    interpreted = await _interpret_with_local_model(req)
    return interpreted or _interpret_with_rules(req)


async def _synthesize_to_file(req: TtsRequest) -> tuple[str, str, TtsVoice, float]:
    text = _validate_request(req)
    voice = _voice_or_400(req.voice)
    voice_prompt_parts = [
        f"声音风格：{voice.name}",
        f"适用场景：{voice.scene}",
        voice.description,
    ]
    if voice.tags:
        voice_prompt_parts.append("关键词：" + "、".join(voice.tags))
    if req.voice_prompt.strip():
        voice_prompt_parts.append("用户要求：" + req.voice_prompt.strip())
    voice_prompt = "；".join(part for part in voice_prompt_parts if part)
    client = VolcEngineClient(output_dir=str(get_media_output_dir("audio")))
    try:
        path, duration = await client.seed_audio_text_to_speech(
            text=text,
            voice_id=voice.provider_voice,
            voice_prompt=voice_prompt,
            speed=req.speed,
            pitch=req.pitch,
            response_format=req.format,
            output_dir=str(get_media_output_dir("audio")),
        )
    except Exception as exc:
        raise HTTPException(500, str(exc))
    finally:
        await client.close()
    return text, path, voice, duration


def _response_for_path(req: TtsRequest, text: str, path: str, voice: TtsVoice, duration: float = 0) -> TtsResponse:
    file_path = Path(path)
    return TtsResponse(
        ok=True,
        url=media_url_for_path(file_path),
        path=str(file_path.resolve()),
        filename=file_path.name,
        voice=voice.id,
        emotion=req.emotion,
        speed=req.speed,
        pitch=req.pitch,
        preview=req.preview,
        estimated_duration=round(duration, 1) if duration else _estimated_duration(text, req.speed),
    )


@router.post("/preview", response_model=TtsResponse)
async def preview(req: TtsRequest):
    payload = _copy_request(req, {"text": req.text.strip()[:MAX_PREVIEW_TEXT_CHARS], "preview": True})
    text, path, voice, duration = await _synthesize_to_file(payload)
    return _response_for_path(payload, text, path, voice, duration)


@router.post("/synthesize")
async def synthesize(req: TtsRequest, response: str = Query(default="json")):
    text, path, voice, duration = await _synthesize_to_file(req)
    if response == "file":
        return FileResponse(path, media_type="audio/mpeg", filename=Path(path).name)
    if response != "json":
        raise HTTPException(400, "response must be json or file")
    return _response_for_path(req, text, path, voice, duration)
