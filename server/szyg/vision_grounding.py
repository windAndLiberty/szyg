"""
Vision Grounding Module — Visual element detection for browser automation.

Architecture:
  Tier 1 (GPU available): OmniParser v2 — YOLO-based UI element detection
  Tier 2 (no GPU):        Hermes auxiliary vision model — text-based analysis
  Tier 3 (fallback):      CSS selector-based fallback

OmniParser v2 detects interactive elements from screenshots and returns
bounding boxes + functional descriptions. This module provides a clean API
for platform adapters to use vision-based element finding instead of
fragile CSS selectors.

Usage:
    from szyg.vision_grounding import VisionGrounding

    vg = VisionGrounding()

    # Find and click an element
    clicked = await vg.find_and_click(page, "发布按钮")

    # Find and type into an input
    typed = await vg.find_and_type(page, "标题输入框", "My Title")

    # Get all detected elements with coordinates
    elements = await vg.detect(page)

Setup (OmniParser):
    git clone https://github.com/microsoft/OmniParser.git
    cd OmniParser && pip install -r requirements.txt
    # Download weights from huggingface.co/microsoft/OmniParser-v2.0
    # Start API: python gradio_demo.py  →  http://localhost:7861
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────

# OmniParser API endpoint (set via env var or auto-detect)
OMNIPARSER_API_URL = os.environ.get(
    "OMNIPARSER_API_URL", "http://localhost:7861"
)

# Hermes home for cache
HERMES_HOME = os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))

# Screenshot cache directory
SCREENSHOTS_DIR = Path(HERMES_HOME) / "cache" / "vision_screenshots"


@dataclass
class DetectedElement:
    """A UI element detected by vision grounding."""
    index: int                        # 1-based index
    label: str                        # functional description (e.g. "button 发布")
    bbox: tuple[int, int, int, int]   # (x, y, w, h) in page coordinates
    confidence: float = 1.0           # detection confidence
    role: str = ""                    # element role (button, input, icon, text)

    def center(self) -> tuple[int, int]:
        x, y, w, h = self.bbox
        return x + w // 2, y + h // 2

    def __repr__(self) -> str:
        cx, cy = self.center()
        return (
            f"Element[{self.index}] '{self.label}' "
            f"bbox=({self.bbox[0]},{self.bbox[1]},{self.bbox[2]}x{self.bbox[3]}) "
            f"center=({cx},{cy}) conf={self.confidence:.2f}"
        )


class VisionGrounding:
    """
    Visual element detection for Playwright-powered browser automation.

    Two-tier architecture:
      1. OmniParser v2 (local HTTP API) — precise bounding boxes
      2. Hermes auxiliary vision model — text description, no coordinates
      3. CSS selector fallback

    Cache: detected elements can be cached per URL for short periods
           to avoid repeated API calls during a single publishing session.
    """

    def __init__(self, omniparser_url: str | None = None):
        self._omniparser_url = omniparser_url or OMNIPARSER_API_URL
        self._omniparser_available: bool | None = None  # lazy check
        self._cache: dict[str, list[DetectedElement]] = {}

    # ── Public API ───────────────────────────────────────

    async def detect(
        self,
        page,
        *,
        use_cache: bool = True,
    ) -> list[DetectedElement]:
        """
        Take a screenshot and detect all interactive UI elements.

        Args:
            page: Playwright Page object
            use_cache: If True, use cached results for the same URL

        Returns:
            List of DetectedElement with bounding boxes and labels
        """
        url = page.url
        cache_key = f"detect:{url}"

        if use_cache and cache_key in self._cache:
            logger.debug(f"Vision: using cached detection for {url}")
            return self._cache[cache_key]

        # Take full-page screenshot
        screenshot_bytes = await self._capture_screenshot(page)

        # Try OmniParser first
        omniparser_ok = await self._check_omniparser()
        if omniparser_ok:
            try:
                elements = await self._detect_via_omniparser(screenshot_bytes)
                if elements:
                    self._cache[cache_key] = elements
                    return elements
            except Exception as e:
                logger.warning(f"OmniParser detection failed: {e}")

        # Fallback: Hermes vision model (text only, no coordinates)
        try:
            elements = await self._detect_via_hermes_vision(screenshot_bytes, url)
            if elements:
                self._cache[cache_key] = elements
                return elements
        except Exception as e:
            logger.warning(f"Hermes vision detection failed: {e}")

        return []

    async def find_element(
        self,
        page,
        description: str,
        *,
        role: str | None = None,
    ) -> DetectedElement | None:
        """
        Find a specific UI element by description.

        Args:
            page: Playwright Page object
            description: Natural language description (e.g. "发布按钮", "标题输入框")
            role: Optional role filter (button, input, icon, text)

        Returns:
            DetectedElement if found, None otherwise
        """
        elements = await self.detect(page)
        if not elements:
            return None

        # Score each element against the description
        best = None
        best_score = 0.0

        for el in elements:
            score = self._match_score(el, description, role)
            if score > best_score:
                best_score = score
                best = el

        if best and best_score > 0.3:
            logger.info(
                f"Vision: found '{best.label}' for '{description}' "
                f"(score={best_score:.2f}, center={best.center()})"
            )
            return best

        return None

    async def find_and_click(
        self,
        page,
        description: str,
        *,
        role: str | None = None,
    ) -> bool:
        """
        Find an element by vision and click its center.

        Returns True if element was found and clicked.
        """
        el = await self.find_element(page, description, role=role)
        if el is None:
            logger.warning(f"Vision: element not found for '{description}'")
            return False

        cx, cy = el.center()
        try:
            await page.mouse.click(cx, cy)
            logger.info(f"Vision click: '{el.label}' at ({cx}, {cy})")
            return True
        except Exception as e:
            logger.error(f"Vision click failed at ({cx}, {cy}): {e}")
            return False

    async def find_and_type(
        self,
        page,
        description: str,
        text: str,
        *,
        role: str | None = None,
    ) -> bool:
        """
        Find an input element by vision, click it, and type text.

        Returns True if element was found and text was typed.
        """
        el = await self.find_element(page, description, role=role or "input")
        if el is None:
            logger.warning(f"Vision: input not found for '{description}'")
            return False

        cx, cy = el.center()
        try:
            await page.mouse.click(cx, cy)
            await asyncio.sleep(0.2)
            # Clear existing text first
            await page.keyboard.press("Control+a")
            await page.keyboard.press("Backspace")
            await page.keyboard.type(text, delay=50)
            logger.info(f"Vision type: '{el.label}' <- '{text[:30]}...'")
            return True
        except Exception as e:
            logger.error(f"Vision type failed at ({cx}, {cy}): {e}")
            return False

    async def find_and_upload(
        self,
        page,
        description: str,
        file_path: str,
    ) -> bool:
        """
        Find a file input by vision and upload a file.

        Returns True if file was uploaded.
        """
        el = await self.find_element(page, description, role="input")
        if el is None:
            # Try CSS fallback for file inputs (they're usually hidden)
            try:
                file_input = await page.wait_for_selector(
                    'input[type="file"]', state="attached", timeout=5000
                )
                if file_input:
                    await file_input.set_input_files(file_path)
                    logger.info(f"CSS fallback upload: {file_path}")
                    return True
            except Exception:
                logger.debug("Vision upload failed, trying CSS fallback", exc_info=True)
            return False

        cx, cy = el.center()
        try:
            # File inputs are often hidden — try to find the actual input
            file_input = await page.wait_for_selector(
                'input[type="file"]', state="attached", timeout=3000
            )
            if file_input:
                await file_input.set_input_files(file_path)
                logger.info(f"Vision upload: {file_path}")
                return True

            # Fallback: click and hope file dialog opens
            await page.mouse.click(cx, cy)
            logger.warning(f"Vision upload: clicked at ({cx},{cy}) but no file input found")
            return False
        except Exception as e:
            logger.error(f"Vision upload failed: {e}")
            return False

    def clear_cache(self) -> None:
        """Clear the detection cache."""
        self._cache.clear()

    # ── Screenshot capture ────────────────────────────────

    async def _capture_screenshot(self, page) -> bytes:
        """Take a viewport screenshot as PNG bytes."""
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        return await page.screenshot(type="png", full_page=False)

    # ── OmniParser backend ────────────────────────────────

    async def _check_omniparser(self) -> bool:
        """Check if OmniParser models are available for local inference."""
        if self._omniparser_available is not None:
            return self._omniparser_available

        # Try local model first
        try:
            detector = _get_omniparser_local()
            if detector.is_available():
                self._omniparser_available = True
                logger.info("OmniParser local inference available (YOLO + Florence-2)")
                return True
        except Exception as e:
            logger.debug(f"OmniParser local init failed: {e}")

        # Fallback: check HTTP API
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self._omniparser_url}/")
                self._omniparser_available = resp.status_code < 500
                if self._omniparser_available:
                    logger.info(f"OmniParser HTTP API available at {self._omniparser_url}")
                return self._omniparser_available
        except Exception:
            self._omniparser_available = False
            logger.debug("OmniParser not available (no local models, no HTTP API)")
            return False

    async def _detect_via_omniparser(
        self, screenshot_bytes: bytes
    ) -> list[DetectedElement]:
        """Run OmniParser local inference on a screenshot."""
        from PIL import Image
        import io

        detector = _get_omniparser_local()
        if not detector.is_available():
            # Fall back to HTTP API
            return await self._detect_via_omniparser_http(screenshot_bytes)

        image = Image.open(io.BytesIO(screenshot_bytes))
        elements = detector.detect(image)
        logger.info(f"OmniParser local: detected {len(elements)} elements")
        return elements

    async def _detect_via_omniparser_http(
        self, screenshot_bytes: bytes
    ) -> list[DetectedElement]:
        """Fallback: Call OmniParser HTTP API when local models unavailable."""
        import httpx

        temp_path = SCREENSHOTS_DIR / "omniparser_temp.png"
        temp_path.write_bytes(screenshot_bytes)

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                with open(temp_path, "rb") as f:
                    files = {"file": ("screenshot.png", f, "image/png")}
                    resp = await client.post(
                        f"{self._omniparser_url}/process_image",
                        files=files,
                    )
                resp.raise_for_status()
                result = resp.json()
        except Exception:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    b64 = base64.b64encode(screenshot_bytes).decode("ascii")
                    resp = await client.post(
                        f"{self._omniparser_url}/parse",
                        json={"image": b64},
                    )
                resp.raise_for_status()
                result = resp.json()
            except Exception as e:
                raise RuntimeError(f"OmniParser HTTP API call failed: {e}")

        elements = _parse_omniparser_result(result)
        logger.info(f"OmniParser HTTP: detected {len(elements)} elements")
        return elements

    # ── Hermes vision fallback ────────────────────────────

    async def _detect_via_hermes_vision(
        self, screenshot_bytes: bytes, page_url: str
    ) -> list[DetectedElement]:
        """
        Use Hermes's auxiliary vision model to analyze the screenshot.

        The vision model returns a text description of what it sees.
        We parse this into structured elements (without precise coordinates).
        """
        try:
            from agent.auxiliary_client import async_call_llm, extract_content_or_reasoning
            from hermes_cli.config import load_config
        except ImportError:
            logger.debug("Hermes agent modules not available for vision fallback")
            return []

        cfg = load_config()
        vision_cfg = cfg.get("auxiliary", {}).get("vision", {})

        provider = vision_cfg.get("provider")
        model = vision_cfg.get("model")
        base_url = vision_cfg.get("base_url")

        if not provider and not model:
            logger.debug("No auxiliary.vision configured — vision fallback unavailable")
            return []

        # Build prompt asking for structured element detection
        prompt = (
            "You are a UI element detector. Analyze this screenshot of a web page "
            f"(URL: {page_url}) and list ALL interactive elements you can see.\n\n"
            "For each element, estimate its approximate position as a percentage "
            "of the viewport (x%, y% from top-left, width%, height%).\n\n"
            "Return ONLY a JSON array, no other text:\n"
            '[\n'
            '  {"label": "button 发布", "role": "button", '
            '"x_pct": 85, "y_pct": 12, "w_pct": 8, "h_pct": 4},\n'
            '  {"label": "input 标题", "role": "input", '
            '"x_pct": 50, "y_pct": 40, "w_pct": 80, "h_pct": 5}\n'
            ']\n\n'
            "Be thorough — include at most 20 elements. Prioritize buttons, "
            "inputs, file upload areas, tabs, and text editors."
        )

        try:
            response = await async_call_llm(
                prompt=prompt,
                provider=provider,
                model=model,
                base_url=base_url,
                image_data=screenshot_bytes,
                temperature=0.1,
                timeout=60.0,
            )
            content = extract_content_or_reasoning(response)

            # Parse JSON from response
            elements = self._parse_vision_response(content)
            logger.info(f"Hermes vision detected {len(elements)} elements")
            return elements

        except Exception as e:
            logger.warning(f"Hermes vision call failed: {e}")
            return []

    def _parse_vision_response(self, content: str) -> list[DetectedElement]:
        """Extract structured element list from vision model response."""
        try:
            # Try to find JSON array in the response
            import re
            json_match = re.search(r'\[[\s\S]*\]', content)
            if not json_match:
                return []

            items = json.loads(json_match.group(0))
            elements = []

            for i, item in enumerate(items):
                label = item.get("label", "").strip()
                role = item.get("role", self._infer_role(label))

                # Convert percentage coordinates to bbox
                # Use a default viewport of 1280x900 (will be scaled by caller)
                vw, vh = 1280, 900
                x = int(item.get("x_pct", 50) * vw / 100)
                y = int(item.get("y_pct", 50) * vh / 100)
                w = int(item.get("w_pct", 10) * vw / 100)
                h = int(item.get("h_pct", 5) * vh / 100)

                elements.append(DetectedElement(
                    index=i + 1,
                    label=label,
                    bbox=(x, y, w, h),
                    confidence=0.7,  # vision model estimates are approximate
                    role=role,
                ))

            return elements

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.debug(f"Failed to parse vision response: {e}")
            return []

    # ── Matching ──────────────────────────────────────────

    def _match_score(
        self,
        element: DetectedElement,
        query: str,
        role_filter: str | None = None,
    ) -> float:
        """
        Score how well an element matches a natural language query.

        Uses simple keyword matching — Chinese and English both supported.
        """
        label_lower = element.label.lower()
        query_lower = query.lower()

        # Role filter
        if role_filter and element.role.lower() != role_filter.lower():
            # Allow some flexibility (e.g. "input" matches "textbox")
            if not (role_filter == "input" and element.role in ("textbox", "text")):
                return 0.0

        score = 0.0

        # Exact match
        if query_lower == label_lower:
            return 1.0

        # Query is substring of label
        if query_lower in label_lower:
            score += 0.6

        # Label is substring of query
        if label_lower in query_lower:
            score += 0.4

        # Individual keyword matches
        query_keywords = set(query_lower.split())
        label_keywords = set(label_lower.split())
        overlap = query_keywords & label_keywords
        if overlap:
            score += 0.3 * len(overlap) / max(len(query_keywords), 1)

        # Chinese character matching (handle multi-char queries)
        for char in query_lower:
            if char in label_lower and ord(char) > 127:  # CJK character
                score += 0.05

        return min(score, 1.0)

    def _infer_role(self, label: str) -> str:
        """Infer element role from its OmniParser/vision label."""
        label_lower = label.lower()

        if any(kw in label_lower for kw in ("button", "按钮", "btn", "发布", "提交", "确认", "取消")):
            return "button"
        if any(kw in label_lower for kw in ("input", "输入", "text", "文本框", "placeholder", "标题", "搜索")):
            return "input"
        if any(kw in label_lower for kw in ("icon", "图标", "image", "图片", "img")):
            return "icon"
        if any(kw in label_lower for kw in ("text", "文字", "文本", "描述", "内容")):
            return "text"
        if any(kw in label_lower for kw in ("upload", "上传", "file", "文件")):
            return "input"
        if any(kw in label_lower for kw in ("tab", "标签", "标签页")):
            return "tab"
        if any(kw in label_lower for kw in ("link", "链接", "a ")):
            return "link"
        if any(kw in label_lower for kw in ("checkbox", "radio", "选择", "勾选")):
            return "checkbox"

        return "element"

    # ── CSS fallback ──────────────────────────────────────

    async def fallback_click(
        self,
        page,
        selectors: list[str],
        description: str = "",
    ) -> bool:
        """
        Click an element using CSS selectors as last resort.
        Tries each selector in order. First success wins.

        Returns True if any selector matched and was clicked.
        """
        for sel in selectors:
            try:
                el = await page.wait_for_selector(sel, state="visible", timeout=3000)
                if el:
                    await el.click()
                    logger.info(f"CSS fallback click: '{sel}' for '{description}'")
                    return True
            except Exception:
                logger.debug("CSS fallback click selector %s failed", sel)
                continue
        return False

    async def fallback_type(
        self,
        page,
        selectors: list[str],
        text: str,
        description: str = "",
    ) -> bool:
        """
        Type text into an element using CSS selectors as last resort.
        """
        for sel in selectors:
            try:
                el = await page.wait_for_selector(sel, state="visible", timeout=3000)
                if el:
                    await el.click()
                    await asyncio.sleep(0.2)
                    await page.keyboard.press("Control+a")
                    await page.keyboard.press("Backspace")
                    await page.keyboard.type(text, delay=50)
                    logger.info(f"CSS fallback type: '{sel}' for '{description}'")
                    return True
            except Exception:
                logger.debug("CSS fallback type selector %s failed", sel)
                continue
        return False


# ═══════════════════════════════════════════════════════════════
# OmniParser Local Inference Engine
# ═══════════════════════════════════════════════════════════════

# Model weights directory (configurable via env var)
OMNIPARSER_WEIGHTS_DIR = os.environ.get(
    "OMNIPARSER_WEIGHTS_DIR",
    str(Path(__file__).resolve().parent.parent.parent / "data" / "models" / "omniparser"),
)

# YOLO detection confidence threshold
YOLO_CONF_THRESHOLD = float(os.environ.get("OMNIPARSER_CONF_THRESHOLD", "0.05"))

# Maximum number of elements to detect
MAX_ELEMENTS = int(os.environ.get("OMNIPARSER_MAX_ELEMENTS", "30"))

# Florence-2 model directory (separate from OmniParser for code/config compatibility)
FLORENCE2_DIR = Path(
    os.environ.get(
        "FLORENCE2_DIR",
        str(Path(__file__).resolve().parent.parent.parent / "data" / "models" / "florence2"),
    )
)


class OmniParserLocal:
    """
    Direct OmniParser v2 inference — no HTTP server needed.

    Uses:
      - YOLOv8 (ultralytics) for UI element detection
      - Florence-2 (transformers) for icon captioning

    Model weights auto-downloaded from HuggingFace on first use.
    """

    def __init__(self, weights_dir: str | None = None):
        self._weights_dir = Path(weights_dir or OMNIPARSER_WEIGHTS_DIR)
        self._yolo_model = None
        self._florence_model = None
        self._florence_processor = None
        self._device = "cuda" if self._cuda_available() else "cpu"
        self._loaded = False

    @staticmethod
    def _cuda_available() -> bool:
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    def is_available(self) -> bool:
        """Check if model weights exist and can be loaded."""
        detect_model = self._weights_dir / "icon_detect" / "model.pt"
        caption_model = self._weights_dir / "icon_caption_florence" / "model.safetensors"
        return detect_model.exists() and caption_model.exists()

    def _ensure_loaded(self):
        """Lazy-load models on first use."""
        if self._loaded:
            return

        logger.info(f"Loading OmniParser models (device={self._device})...")

        # Load YOLOv8 detection model
        from ultralytics import YOLO
        detect_path = str(self._weights_dir / "icon_detect" / "model.pt")
        self._yolo_model = YOLO(detect_path)
        logger.info(f"  YOLOv8 loaded: {detect_path}")

        # Load Florence-2 caption model
        # Use the florence2 directory which has compatible config/code files
        # The model.safetensors there is OmniParser fine-tuned (1.1 GB) for icon description
        from transformers import AutoProcessor, AutoModelForCausalLM
        import torch

        caption_path = str(FLORENCE2_DIR)
        self._florence_processor = AutoProcessor.from_pretrained(
            caption_path, trust_remote_code=True,
        )
        self._florence_model = AutoModelForCausalLM.from_pretrained(
            caption_path,
            trust_remote_code=True,
            torch_dtype=torch.float16 if self._device == "cuda" else torch.float32,
        ).to(self._device)
        logger.info(f"  Florence-2 loaded: {caption_path}")

        self._loaded = True
        logger.info("OmniParser models ready")

    def detect(self, image: "PIL.Image.Image") -> list[DetectedElement]:
        """
        Detect UI elements in a screenshot.

        Args:
            image: PIL Image of the browser screenshot

        Returns:
            List of DetectedElement with bounding boxes and labels
        """
        self._ensure_loaded()

        # Step 1: YOLOv8 element detection
        import torch
        from ultralytics import YOLO

        results = self._yolo_model(
            image,
            conf=YOLO_CONF_THRESHOLD,
            iou=0.3,
            max_det=MAX_ELEMENTS,
            verbose=False,
        )

        elements = []
        boxes = results[0].boxes

        if boxes is None or len(boxes) == 0:
            logger.debug("YOLO: no elements detected")
            return elements

        xyxy = boxes.xyxy.cpu().numpy()
        confs = boxes.conf.cpu().numpy() if boxes.conf is not None else None

        # Step 2: Florence-2 captioning for each detected element
        for i, bbox_xyxy in enumerate(xyxy):
            x1, y1, x2, y2 = [int(v) for v in bbox_xyxy]
            confidence = float(confs[i]) if confs is not None else 0.5

            # Crop the element region
            crop = image.crop((x1, y1, x2, y2))

            # Get caption from Florence-2
            caption = self._caption_element(crop)

            bbox = (x1, y1, x2 - x1, y2 - y1)
            role = self._infer_role_from_caption(caption)

            elements.append(DetectedElement(
                index=i + 1,
                label=caption,
                bbox=bbox,
                confidence=confidence,
                role=role,
            ))

        return elements

    def _caption_element(self, crop: "PIL.Image.Image") -> str:
        """Get a functional description of a UI element using Florence-2."""
        import torch

        prompt = "<OD>"  # Open vocabulary detection prompt

        try:
            inputs = self._florence_processor(
                text=prompt, images=crop, return_tensors="pt"
            ).to(self._device)

            # Cast pixel_values to match model dtype (fp16), keep input_ids as int
            if self._florence_model.dtype == torch.float16:
                inputs["pixel_values"] = inputs["pixel_values"].to(torch.float16)

            with torch.no_grad():
                generated_ids = self._florence_model.generate(
                    input_ids=inputs["input_ids"],
                    pixel_values=inputs["pixel_values"],
                    max_new_tokens=64,
                    num_beams=3,
                    do_sample=False,
                )

            caption = self._florence_processor.batch_decode(
                generated_ids, skip_special_tokens=True
            )[0]

            # Clean up caption
            caption = caption.replace("<OD>", "").strip()
            if not caption:
                caption = "element"

            return caption

        except Exception as e:
            logger.debug(f"Florence caption failed: {e}")
            return "element"

    @staticmethod
    def _infer_role_from_caption(caption: str) -> str:
        """Infer element role from Florence-2 caption."""
        caption_lower = caption.lower()

        if any(kw in caption_lower for kw in ("button", "按钮", "btn", "发布", "提交", "确认", "取消", "关闭")):
            return "button"
        if any(kw in caption_lower for kw in ("input", "text box", "textbox", "输入", "文本框", "标题", "搜索框")):
            return "input"
        if any(kw in caption_lower for kw in ("icon", "图标", "symbol", "符号")):
            return "icon"
        if any(kw in caption_lower for kw in ("image", "图片", "photo", "照片")):
            return "image"
        if any(kw in caption_lower for kw in ("text", "文字", "文本", "描述", "内容", "label", "标签")):
            return "text"
        if any(kw in caption_lower for kw in ("tab", "标签页")):
            return "tab"
        if any(kw in caption_lower for kw in ("link", "链接")):
            return "link"
        if any(kw in caption_lower for kw in ("checkbox", "radio", "选择", "勾选", "check")):
            return "checkbox"
        if any(kw in caption_lower for kw in ("menu", "菜单", "dropdown", "下拉")):
            return "menu"
        if any(kw in caption_lower for kw in ("scroll", "滚动", "slider", "滑块")):
            return "slider"

        return "element"


# ── Module-level helpers ──────────────────────────────────────

_omniparser_local: OmniParserLocal | None = None


def _get_omniparser_local() -> OmniParserLocal:
    """Get or create the singleton OmniParserLocal instance."""
    global _omniparser_local
    if _omniparser_local is None:
        _omniparser_local = OmniParserLocal()
    return _omniparser_local


def _parse_omniparser_result(result: dict) -> list[DetectedElement]:
    """Parse OmniParser API/CLI response into DetectedElement list."""
    elements = []

    content_list = (
        result.get("parsed_content_list")
        or result.get("result_data", {}).get("parsed_content_list")
        or []
    )
    coords = (
        result.get("label_coordinates")
        or result.get("result_data", {}).get("label_coordinates")
        or {}
    )

    for item in content_list:
        index = item.get("index", len(elements) + 1)
        label = item.get("label", "").strip()
        confidence = item.get("confidence", 1.0)

        bbox_raw = item.get("bbox")
        if bbox_raw is None and str(index) in coords:
            bbox_raw = coords[str(index)]
        if bbox_raw is None:
            continue

        if len(bbox_raw) == 4:
            x1, y1, x2, y2 = bbox_raw
            bbox = (int(x1), int(y1), int(x2 - x1), int(y2 - y1))
        else:
            continue

        role = _infer_role_static(item.get("type", label))
        elements.append(DetectedElement(
            index=index, label=label, bbox=bbox,
            confidence=float(confidence), role=role,
        ))

    return elements


def _infer_role_static(label: str) -> str:
    """Infer role from label without needing an instance."""
    label_lower = label.lower()
    if any(kw in label_lower for kw in ("button", "按钮", "btn")):
        return "button"
    if any(kw in label_lower for kw in ("input", "输入", "textbox", "标题")):
        return "input"
    if any(kw in label_lower for kw in ("icon", "图标", "image", "图片")):
        return "icon"
    if any(kw in label_lower for kw in ("text", "文字", "文本", "内容")):
        return "text"
    if any(kw in label_lower for kw in ("tab", "标签")):
        return "tab"
    return "element"


# ── Singleton ────────────────────────────────────────────────

_vision_grounding: VisionGrounding | None = None


def get_vision_grounding() -> VisionGrounding:
    """Get or create the singleton VisionGrounding instance."""
    global _vision_grounding
    if _vision_grounding is None:
        _vision_grounding = VisionGrounding()
    return _vision_grounding
