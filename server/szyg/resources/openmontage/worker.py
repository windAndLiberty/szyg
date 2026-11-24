"""Run the pinned upstream project's tool contracts in its own Python interpreter."""

import contextlib
import json
import sys
from pathlib import Path

# Only declarative operations with bounded inputs belong on the chat interface.
# Paths are substituted by the host; commands, credentials, callbacks, arbitrary
# filters, provider payloads and renderer source code are never accepted here.
LOCAL = {
    "audio_probe": "input_path",
    "audio_energy": "input_path video_duration_seconds energy_threshold_lufs",
    "scene_detect": "input_path method threshold min_scene_length_seconds",
    "frame_sampler": "input_path strategy count interval_seconds max_frames",
    "audio_enhance": "input_path preset",
    "silence_cutter": "input_path mode silence_threshold_db min_silence_duration padding_seconds",
    "video_trimmer": "operation input_path start_seconds end_seconds speed_factor",
    "video_stitch": "operation clips transition transition_duration auto_normalize layout pip_position pip_scale",
    "audio_mixer": "operation input_path primary_audio secondary_audio video_path music_path music_volume duck_level",
    "auto_reframe": "input_path target_aspect",
    "video_analyzer": "source analysis_depth max_keyframes",
    "export_bundle": "video_path title description platform subtitles_path thumbnail_path",
    "green_screen_processor": "input_path method fps max_frames",
    "talking_head": "image_path audio_path",
    "lip_sync": "video_path audio_path",
    "subtitle_gen": "segments format max_chars_per_line max_words_per_cue",
    "remotion_caption_burn": "input_path srt_path words_per_page font_size force_ffmpeg",
    "character_spec_generator": "characters brief style",
    "svg_rig_builder": "character_design",
    "pose_library_builder": "rig_plan",
    "action_timeline_compiler": "scene_plan character_ids fps",
    "video_compose": "operation input_path subtitle_path profile",
    "visual_qa": "operation input_path",
    "face_tracker": "input_path sample_fps min_detection_confidence",
    "transcriber": "input_path model_size language",
    "bg_remove": "input_path model alpha_matting",
    "color_grade": "input_path profile intensity",
    "eye_enhance": "input_path dark_circle_intensity eye_brighten_intensity sharpen_intensity",
    "face_enhance": "input_path preset",
    "face_restore": "input_path model fidelity upscale",
    "upscale": "input_path scale model face_enhance",
    "green_screen_composite": "speaker_path background_path original_audio_path layout speaker_scale",
    "showcase_card": "input_path title subtitle watermark",
    "bgm_montage_lite": "audio_path video_paths aspect_ratio",
    "direct_clip_search": "queries sources clips_per_query extract_thumbnails",
}
PROVIDERS = frozenset(
    """
openai_image bfl_image bria_image dashscope_image google_imagen grok_image ideogram_image
kling_official_image mai_image minimax_image recraft_image seedream_image openai_fal_image
flux_image qwen_image_21 flux3_fal_image flux3_replicate_image wan_fal_video wan_replicate_video
fal_3d atlas_3d atlas_image kling_o3_fal_image fal_elevenlabs_tts fal_elevenlabs_music
azure_tts cartesia_tts dashscope_tts doubao_tts elevenlabs_tts fish_audio_tts google_tts
inworld_tts mai_tts mistral_tts openai_tts piper_tts suno_music google_music grok_tts
bria_fal_image gemini_fal_image gemini_replicate_image hunyuan_image ideogram_fal_image flux3_video comfyui_image comfyui_music comfyui_video gemini_omni_fal gemini_omni_video atlas_video higgsfield_video gemini_tts dashscope_asr heygen_catalog_tts heygen_avatar heygen_voice_convert kling_avatar elevenlabs_soundtrack ltx_video_local video_understand h3_max_video hunyuan_cloud_video jimeng_video wan_atlas_video seedance_replicate azure_stt mistral_stt music_gen freesound_music pixabay_music pexels_image pexels_video
pixabay_image pixabay_video sora_video seedance_ark seedance_replicate_video seedance_video
runway_video pika_video kling_video kling_official_video kling_o3_fal_video veo_video
vidu_video minimax_video minimax_fal_video ltx_api_video grok_video heygen_video
wan_video hunyuan_video cogvideo_video local_diffusion heygen_tts kling_tts
""".split()
)
PATH_KEYS = set(
    """
input_path source thumbnail_path subtitles_path srt_path subtitle_path speaker_path background_path original_audio_path video_paths image_path image_paths mask_path first_frame_path last_frame_path end_image_path
reference_image_path reference_image_paths reference_video_path reference_audio_path
input_reference_path audio_path video_path music_path primary_audio secondary_audio clips
""".split()
)
COMMON = set(
    """
text prompt negative_prompt instructions query title style voice voice_id language language_code avatar_id script motion_prompt reference_look_id engine enable_words video_path video_paths
locale duration duration_seconds aspect_ratio resolution size quality seed speed operation
generate_audio force_instrumental instrumental orientation sample_rate speaking_rate ratio
generation_mode model model_variant watermark image_path image_paths mask_path first_frame_path
last_frame_path end_image_path reference_image_path reference_image_paths reference_video_path
reference_audio_path input_reference_path audio_path input_path
""".split()
)
OUTPUT_EXT = {
    "video_generation": ".mp4",
    "video_post": ".mp4",
    "tts": ".mp3",
    "music_generation": ".mp3",
    "music_search": ".mp3",
    "image_generation": ".png",
    "audio_processing": ".wav",
    "3d_generation": ".glb",
}
NUM_LIMITS = {
    "count": (1, 30),
    "max_keyframes": (1, 30),
    "max_frames": (1, 30),
    "duration": (1, 30),
    "duration_seconds": (1, 30),
    "start_seconds": (0, 3600),
    "end_seconds": (0, 3600),
    "speed_factor": (0.25, 4),
    "words_per_page": (1, 20),
    "font_size": (12, 120),
    "fps": (1, 60),
    "clips_per_query": (1, 5),
    "sample_fps": (0.1, 5),
    "max_words_per_cue": (1, 24),
    "max_chars_per_line": (4, 100),
    "interval_seconds": (0.2, 120),
    "transition_duration": (0.05, 5),
}


def public_schema(tool):
    base = tool.input_schema or {}
    fields = LOCAL.get(tool.name, "").split() if tool.name in LOCAL else COMMON
    if tool.name == "dashscope_asr":
        fields = {"audio_url", "model", "enable_words"}
    properties = {}
    for key in fields:
        if key not in base.get("properties", {}):
            continue
        field = dict(base["properties"][key])
        if key == "audio_url" and tool.name == "dashscope_asr":
            field = {
                "type": "string",
                "description": "小妤素材库音频链接。确认后会上传到临时素材网关供 DashScope 读取。",
                "maxLength": 4096,
            }
        if key in PATH_KEYS:
            file_ref = {
                "type": "string",
                "description": "Local Xiaoyu media library URL",
            }
            field = (
                {"type": "array", "items": file_ref, "maxItems": 12, "minItems": 1}
                if key
                in ("image_paths", "clips", "reference_image_paths", "video_paths")
                else file_ref
            )
        if key == "segments" and tool.name == "subtitle_gen":
            field = {
                "type": "array",
                "minItems": 1,
                "maxItems": 400,
                "items": {
                    "type": "object",
                    "required": ["start", "end", "text"],
                    "additionalProperties": False,
                    "properties": {
                        "start": {"type": "number", "minimum": 0, "maximum": 10800},
                        "end": {"type": "number", "minimum": 0, "maximum": 10800},
                        "text": {"type": "string", "maxLength": 480},
                    },
                },
            }
        if key == "queries":
            field = {
                "type": "array",
                "minItems": 1,
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "required": ["query"],
                    "additionalProperties": False,
                    "properties": {
                        "query": {"type": "string", "maxLength": 100},
                        "kind": {"enum": ["image", "video", "any"]},
                    },
                },
            }
        if key == "sources":
            field = {
                "type": "array",
                "minItems": 1,
                "maxItems": 8,
                "items": {
                    "enum": [
                        "pexels",
                        "pixabay_video",
                        "coverr",
                        "unsplash",
                        "mixkit",
                        "archive_org",
                        "openverse",
                        "videvo",
                        "wikimedia",
                        "nasa",
                        "nara",
                        "pond5_pd",
                        "loc",
                        "esa",
                        "noaa",
                        "dareful",
                        "jaxa",
                    ]
                },
            }
        if tool.name == "video_compose" and key == "profile":
            field = {
                "type": "string",
                "enum": [
                    "youtube_landscape",
                    "youtube_shorts",
                    "instagram_reels",
                    "instagram_feed",
                    "tiktok",
                    "linkedin",
                    "cinematic",
                    "generic_hd",
                ],
            }
        if tool.name == "subtitle_gen" and key == "format":
            field = {"type": "string", "enum": ["srt", "vtt"]}
        if key == "operation" and (
            tool.name
            in {"video_trimmer", "audio_mixer", "video_stitch", "video_compose"}
            or tool.name in PROVIDERS
        ):
            allowed = {
                "video_trimmer": ["cut", "speed"],
                "audio_mixer": ["extract", "duck", "full_mix"],
                "video_compose": ["encode", "burn_subtitles"],
                "video_stitch": ["stitch", "spatial", "validate"],
            }.get(
                tool.name,
                [
                    "text_to_video",
                    "text_to_3d",
                    "image_to_3d",
                    "video_edit",
                    "edit_video",
                    "image_to_video",
                    "reference_to_video",
                    "generate",
                    "synthesize",
                ],
            )
            field["enum"] = [v for v in allowed if v in field.get("enum", allowed)]
            if not field["enum"]:
                continue
        if key == "model" and not field.get("enum"):
            continue
        if (
            not field.get("type")
            and not field.get("enum")
            and (field.get("anyOf") or field.get("oneOf"))
        ):
            # Provider contracts sometimes permit remote references or free-form objects.
            # Expose only the documented scalar form on the chat interface.
            field = (
                {"type": "number"}
                if key in {"seed", "duration", "duration_seconds", "speed"}
                else {"type": "boolean"}
                if key in {"generate_audio", "watermark", "instrumental"}
                else {"type": "string"}
            )
        if key in NUM_LIMITS and field.get("type") in ("integer", "number"):
            low, high = NUM_LIMITS[key]
            field.update(
                minimum=max(low, field.get("minimum", low)),
                maximum=min(high, field.get("maximum", high)),
            )
        if field.get("type") == "string":
            field["maxLength"] = (
                8000
                if key
                in {
                    "text",
                    "prompt",
                    "negative_prompt",
                    "instructions",
                    "query",
                    "title",
                    "style",
                }
                else 512
            )
        properties[key] = field
    required = [
        k for k in base.get("required", []) if k not in {"output_path", "output_dir"}
    ]
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def info(tool):
    schema = public_schema(tool)
    executable = tool.name in (set(LOCAL) | PROVIDERS) and all(
        x in schema["properties"] for x in schema["required"]
    )
    try:
        state = tool.get_status().value if executable else "unchecked"
    except Exception:
        state = "unavailable"
    if not executable:
        reason = "此原版工具未开放通过对话直接执行，可查阅其原始契约。"
    elif state == "available":
        reason = ""
    else:
        reason = tool.install_instructions or "请检查本地依赖、模型权重或供应商配置。"
    return {
        "reason": reason,
        "key": tool.name,
        "name": tool.name,
        "kind": "tool",
        "capability": tool.capability,
        "provider": tool.provider,
        "requires_source_upload": tool.name == "dashscope_asr",
        "description": (type(tool).__doc__ or "").strip().split("\n")[0][:280],
        "status": state,
        "available": state == "available",
        "executable": executable,
        "requires_approval": tool.name in PROVIDERS
        or tool.name == "direct_clip_search",
        "input_schema": schema,
        "dependencies": tool.dependencies,
        "install_instructions": tool.install_instructions,
        "upstream_schema": tool.input_schema if not executable else None,
    }


def run(payload):
    sys.path.insert(0, str(Path(sys.argv[1]).resolve()))
    from tools.tool_registry import registry

    if payload["op"] == "compose":
        from tools.video.video_compose import VideoCompose

        result = VideoCompose().execute(payload["settings"])
    else:
        registry.discover()
        if payload["op"] == "catalog":
            return [info(registry.get(n)) for n in registry.list_all()]
        tool = registry.get(payload["key"])
        if not tool:
            raise ValueError("未知的 OpenMontage 工具")
        detail = info(tool)
        if payload["op"] == "info":
            return detail
        if not detail["executable"] or not detail["available"]:
            raise ValueError("此工具当前不可运行，请检查依赖或供应商配置")
        settings = payload["settings"]
        import jsonschema

        jsonschema.validate(settings, detail["input_schema"])
        if tool.name == "direct_clip_search":
            settings.setdefault("clips_per_query", 2)
            settings["timeout_seconds"] = 180
        if tool.name == "subtitle_gen" and any(
            s["start"] >= s["end"] for s in settings["segments"]
        ):
            raise ValueError("字幕结束时间须晚于起点")
        if tool.name == "frame_sampler":
            settings.setdefault("max_frames", 30)
        if tool.name == "video_trimmer" and (
            not settings.get("input_path")
            or settings.get("end_seconds", 1) <= settings.get("start_seconds", 0)
            and "end_seconds" in settings
        ):
            raise ValueError("请选择素材及有效的起止点")
        fields = tool.input_schema.get("properties", {})
        if tool.name == "export_bundle":
            settings["export_dir"] = str(Path.cwd() / "delivery")
        if "output_dir" in fields:
            settings["output_dir"] = str(Path.cwd())
        if "output_path" in fields:
            ext = OUTPUT_EXT.get(tool.capability, ".json")
            # Several upstream tools use the image / video / audio prefix families.
            if tool.name == "subtitle_gen":
                ext = "." + settings.get("format", "srt")
            elif tool.name in {
                "heygen_avatar",
                "kling_avatar",
                "lip_sync",
                "talking_head",
            }:
                ext = ".mp4"
            elif tool.name in {"gemini_tts", "heygen_voice_convert"}:
                ext = ".wav" if tool.name == "gemini_tts" else ".mp3"
            elif tool.name in {"fal_3d", "atlas_3d"}:
                ext = ".glb"
            elif tool.name in {"bg_remove", "face_restore", "upscale"}:
                ext = ".png"
            elif tool.name in {
                "remotion_caption_burn",
                "color_grade",
                "face_enhance",
                "eye_enhance",
                "bgm_montage_lite",
            }:
                ext = ".mp4"
            elif (
                tool.name in {"pexels_image", "pixabay_image"}
                or "image" in tool.capability
            ):
                ext = ".png"
            elif tool.name in {"pexels_video", "pixabay_video"}:
                ext = ".mp4"
            elif tool.name == "audio_mixer" and settings.get("operation") == "full_mix":
                ext = ".mp4" if settings.get("video_path") else ".wav"
            elif tool.name == "piper_tts":
                ext = ".wav"
            settings["output_path"] = str(Path.cwd() / ("output" + ext))
        if tool.name == "remotion_caption_burn":
            # The original Remotion adapter stages a media copy and a props file under its public directory.
            # Inputs have host-generated UUID filenames. Remove our two files after the renderer exits.
            clip = Path(settings["input_path"])
            public = Path(sys.argv[1]) / "remotion-composer" / "public"
            try:
                result = tool.execute(settings)
            finally:
                (public / "talking-head" / clip.name).unlink(missing_ok=True)
                (
                    public / "demo-props" / ("caption-burn-" + clip.stem + ".json")
                ).unlink(missing_ok=True)
        else:
            result = tool.execute(settings)
    if not result.success:
        raise ValueError((result.error or "OpenMontage 操作未完成")[:450])
    return {
        "data": result.data,
        "cost_usd": getattr(result, "cost_usd", None),
        "artifacts": result.artifacts,
    }


if __name__ == "__main__":
    try:
        request = json.load(sys.stdin)
        with contextlib.redirect_stdout(sys.stderr):
            response = run(request)
        print(
            json.dumps(
                {"ok": True, "result": response},
                default=str,
                ensure_ascii=True,
                allow_nan=False,
            )
        )
    except Exception as err:
        # Avoid putting a provider request URL (possibly bearing a token) in the client.
        import re

        message = re.sub(
            r"https?://\S+|(?:Bearer\s+|sk-)[\w.-]+", "[redacted]", str(err)
        )[:450]
        print(json.dumps({"ok": False, "message": message}, ensure_ascii=True))
