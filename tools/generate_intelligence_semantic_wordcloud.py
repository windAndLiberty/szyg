"""Generate a data-driven Chinese semantic word cloud from intelligence reports."""

from __future__ import annotations

import argparse
import json
import math
import random
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

import jieba
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize


CANVAS_WIDTH = 2600
CANVAS_HEIGHT = 1700
CLOUD_LEFT = 120
CLOUD_TOP = 300
CLOUD_WIDTH = 2360
CLOUD_HEIGHT = 1080

CLUSTER_COLORS = [
    "#4F46E5",
    "#0891B2",
    "#059669",
    "#D97706",
    "#DB2777",
]

STOP_WORDS = {
    "一个", "一些", "以及", "其中", "什么", "如何", "哪些", "这个", "这些", "通过", "进行",
    "相关", "当前", "本轮", "可以", "需要", "能够", "比较", "可能", "属于", "直接", "提供",
    "内容", "信息", "产品", "用户", "市场", "方面", "情况", "问题", "方向", "工具", "软件",
    "真实", "核心", "关注", "选择", "使用", "学习", "英语", "口语", "陪练", "竞品",
    "时候", "已经", "还是", "同时", "对于", "为了", "避免", "解决", "提升", "获得",
    "我们", "他们", "它们", "自己", "目前", "成为", "影响", "包括", "属于", "没有",
    "的", "了", "和", "与", "及", "是", "在", "对", "为", "从", "把", "将", "中", "上", "下",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/intelligence_reports.json")
    parser.add_argument("--output", default="data/intelligence_exports/semantic_wordcloud.png")
    parser.add_argument("--report-id", default="")
    parser.add_argument("--max-words", type=int, default=42)
    return parser.parse_args()


def load_report(path: Path, report_id: str) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        reports = payload["items"]
    elif isinstance(payload, list):
        reports = payload
    else:
        reports = [payload]
    if report_id:
        for report in reports:
            if report.get("id") == report_id:
                return report
        raise ValueError(f"Report not found: {report_id}")
    return max(reports, key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""))


def clean_text(value: object) -> str:
    text = re.sub(r"https?://\S+", " ", str(value or ""))
    text = re.sub(r"[\w.-]+\.(?:com|cn|net|org)\S*", " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def collect_documents(report: dict) -> list[str]:
    documents: list[str] = []

    def add(*parts: object) -> None:
        text = clean_text("。".join(str(part or "") for part in parts))
        if len(text) >= 4:
            documents.append(text)

    add(report.get("query"), report.get("title"))
    for item in report.get("executive_summary", []):
        add(item.get("title"), item.get("finding"), item.get("why_it_matters"))
    for item in report.get("customer_voice", []):
        add(item.get("theme"), item.get("summary"))
    for item in report.get("content_patterns", []):
        add(item.get("pattern"), item.get("finding"), item.get("recommendation"))
    for item in report.get("evidence", []):
        add(item.get("title"), item.get("summary"), item.get("reason"))
    for item in report.get("actions", []):
        add(item.get("title"), item.get("description"))
    for item in report.get("industry_moves", []):
        add(item.get("title"), item.get("summary"), item.get("impact"))
    return documents


def domain_phrases(report: dict) -> list[str]:
    phrases: list[str] = []
    for item in report.get("word_cloud", []):
        phrases.append(clean_text(item.get("text")))
    for item in report.get("topic_trends", []):
        phrases.append(clean_text(item.get("topic")))
    for item in report.get("customer_voice", []):
        phrases.append(clean_text(item.get("theme")))
    return [item for item in phrases if 2 <= len(item) <= 18 and "http" not in item.lower()]


def valid_token(token: str) -> bool:
    token = token.strip(" \t\r\n，。！？；：、（）《》【】“”‘’…—-_/|,.!?;:()[]{}\"'")
    if not token or token in STOP_WORDS:
        return False
    if re.fullmatch(r"\d+", token):
        return False
    if len(token) < 2 and token.upper() not in {"AI"}:
        return False
    if len(token) > 20:
        return False
    return bool(re.search(r"[\u4e00-\u9fffA-Za-z]", token))


def build_terms(report: dict, documents: list[str], max_words: int) -> tuple[list[dict], int]:
    phrases = domain_phrases(report)
    for phrase in phrases:
        jieba.add_word(phrase, freq=2_000_000)

    def tokenize(text: str) -> list[str]:
        return [token.strip() for token in jieba.lcut(text, cut_all=False) if valid_token(token.strip())]

    tokenized = [tokenize(document) for document in documents]
    usable_documents = [" ".join(tokens) for tokens in tokenized if tokens]
    if not usable_documents:
        raise ValueError("No usable Chinese terms found in the report")

    vectorizer = TfidfVectorizer(
        tokenizer=str.split,
        preprocessor=None,
        token_pattern=None,
        lowercase=False,
        min_df=1,
        sublinear_tf=True,
        norm="l2",
    )
    matrix = vectorizer.fit_transform(usable_documents)
    vocabulary = np.asarray(vectorizer.get_feature_names_out())
    frequencies = Counter(token for tokens in tokenized for token in tokens)
    tfidf_scores = np.asarray(matrix.sum(axis=0)).ravel()

    prior = {
        clean_text(item.get("text")): float(item.get("weight") or 0)
        for item in report.get("word_cloud", [])
    }
    prior_max = max([1.0, *prior.values()])
    frequency_values = np.asarray([frequencies.get(term, 0) for term in vocabulary], dtype=float)
    frequency_norm = np.log1p(frequency_values) / max(1.0, np.log1p(frequency_values.max(initial=1)))
    tfidf_norm = tfidf_scores / max(1.0e-9, tfidf_scores.max(initial=1.0e-9))
    prior_norm = np.asarray([prior.get(term, 0.0) / prior_max for term in vocabulary])
    combined = 0.55 * tfidf_norm + 0.30 * frequency_norm + 0.15 * prior_norm

    ranked_indices = np.argsort(combined)[::-1]
    selected_indices = [index for index in ranked_indices if valid_token(vocabulary[index])][:max_words]
    if len(selected_indices) < 8:
        raise ValueError("The report does not contain enough usable terms")

    term_vectors = normalize(matrix[:, selected_indices].T, norm="l2")
    cluster_count = min(5, max(3, len(selected_indices) // 10))
    cluster_count = min(cluster_count, len(selected_indices))
    labels = KMeans(n_clusters=cluster_count, random_state=42, n_init=20).fit_predict(term_vectors)

    terms: list[dict] = []
    for rank, (index, label) in enumerate(zip(selected_indices, labels, strict=True)):
        terms.append({
            "text": str(vocabulary[index]),
            "frequency": int(frequency_values[index]),
            "tfidf": round(float(tfidf_norm[index]), 6),
            "prior": round(float(prior_norm[index]), 6),
            "score": round(float(combined[index]), 6),
            "cluster": int(label),
            "rank": rank + 1,
        })
    return terms, cluster_count


def find_font(bold: bool = False) -> str:
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise FileNotFoundError("No supported Chinese font found")


def create_cloud_mask() -> np.ndarray:
    mask_image = Image.new("L", (CLOUD_WIDTH, CLOUD_HEIGHT), 0)
    draw = ImageDraw.Draw(mask_image)
    shapes = [
        (130, 250, 2230, 1010),
        (210, 150, 1080, 900),
        (650, 30, 1650, 900),
        (1280, 120, 2180, 900),
        (10, 420, 600, 980),
        (1800, 410, 2350, 980),
    ]
    for shape in shapes:
        draw.ellipse(shape, fill=255)
    return np.asarray(mask_image) > 0


def boxes_overlap(first: tuple[int, int, int, int], second: tuple[int, int, int, int], padding: int = 8) -> bool:
    return not (
        first[2] + padding <= second[0]
        or second[2] + padding <= first[0]
        or first[3] + padding <= second[1]
        or second[3] + padding <= first[1]
    )


def inside_mask(mask: np.ndarray, box: tuple[int, int, int, int]) -> bool:
    left, top, right, bottom = box
    if left < 0 or top < 0 or right >= mask.shape[1] or bottom >= mask.shape[0]:
        return False
    points = [
        (left, top), (right, top), (left, bottom), (right, bottom),
        ((left + right) // 2, top), ((left + right) // 2, bottom),
        (left, (top + bottom) // 2), (right, (top + bottom) // 2),
    ]
    return all(mask[y, x] for x, y in points)


def place_terms(terms: list[dict], cluster_count: int, mask: np.ndarray) -> list[dict]:
    core_cluster = terms[0]["cluster"]
    cluster_order = [core_cluster] + [item for item in range(cluster_count) if item != core_cluster]
    center_positions = [
        (CLOUD_WIDTH * 0.50, CLOUD_HEIGHT * 0.50),
        (CLOUD_WIDTH * 0.34, CLOUD_HEIGHT * 0.41),
        (CLOUD_WIDTH * 0.66, CLOUD_HEIGHT * 0.40),
        (CLOUD_WIDTH * 0.37, CLOUD_HEIGHT * 0.67),
        (CLOUD_WIDTH * 0.65, CLOUD_HEIGHT * 0.66),
    ]
    cluster_centers = {cluster: center_positions[index] for index, cluster in enumerate(cluster_order)}
    maximum = max(term["score"] for term in terms)
    minimum = min(term["score"] for term in terms)
    score_range = max(1.0e-9, maximum - minimum)
    bold_font = find_font(True)
    regular_font = find_font(False)
    occupied: list[tuple[int, int, int, int]] = []
    placed: list[dict] = []
    rng = random.Random(42)

    for index, term in enumerate(terms):
        normalized_score = (term["score"] - minimum) / score_range
        font_size = int(36 + normalized_score * 90)
        if index == 0:
            font_size = max(font_size, 118)
        font_path = bold_font if normalized_score >= 0.58 else regular_font
        placed_box: tuple[int, int, int, int] | None = None
        placed_font: ImageFont.FreeTypeFont | None = None
        target_x, target_y = cluster_centers[term["cluster"]]
        outward = (1.0 - normalized_score) * 0.22
        target_x += (target_x - CLOUD_WIDTH / 2) * outward
        target_y += (target_y - CLOUD_HEIGHT / 2) * outward

        for shrink in range(17):
            size = max(17, int(font_size * (0.91 ** shrink)))
            font = ImageFont.truetype(font_path, size=size)
            text_box = font.getbbox(term["text"])
            text_width = text_box[2] - text_box[0]
            text_height = text_box[3] - text_box[1]
            if text_width >= CLOUD_WIDTH * 0.72:
                continue
            for step in range(5200):
                if index == 0 and step == 0:
                    candidate_x, candidate_y = CLOUD_WIDTH / 2, CLOUD_HEIGHT / 2
                else:
                    angle = step * 0.41 + rng.random() * 0.10
                    radius = 9.5 * math.sqrt(step)
                    candidate_x = target_x + radius * math.cos(angle)
                    candidate_y = target_y + radius * 0.72 * math.sin(angle)
                left = int(candidate_x - text_width / 2)
                top = int(candidate_y - text_height / 2)
                box = (left, top, left + text_width, top + text_height)
                if inside_mask(mask, box) and not any(boxes_overlap(box, other) for other in occupied):
                    placed_box = box
                    placed_font = font
                    break
            if placed_box is not None:
                break
        if placed_box is None or placed_font is None:
            raise RuntimeError(f"Unable to place complete term: {term['text']}")
        occupied.append(placed_box)
        placed.append({**term, "box": placed_box, "font": placed_font, "font_size": placed_font.size})
    return placed


def draw_report(report: dict, terms: list[dict], cluster_count: int, output: Path) -> None:
    image = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), "white")
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.truetype(find_font(True), 58)
    subtitle_font = ImageFont.truetype(find_font(False), 28)
    metric_font = ImageFont.truetype(find_font(True), 34)
    small_font = ImageFont.truetype(find_font(False), 22)
    legend_font = ImageFont.truetype(find_font(False), 23)

    draw.text((120, 70), "智能情报 · NLP 语义词云分析", fill="#111827", font=title_font)
    query = clean_text(report.get("query"))
    draw.text((120, 150), query[:84], fill="#475569", font=subtitle_font)

    scope = report.get("data_scope", {})
    metrics = [
        ("有效信号", str(scope.get("relevant_samples", 0))),
        ("过滤噪声", str(scope.get("filtered_samples", 0))),
        ("分析语料", str(len(collect_documents(report)))),
        ("入图词语", str(len(terms))),
    ]
    card_width = 260
    for index, (label, value) in enumerate(metrics):
        left = 1430 + index * (card_width + 20)
        draw.rounded_rectangle((left, 55, left + card_width, 205), radius=18, fill="#F8FAFC", outline="#E2E8F0", width=2)
        draw.text((left + 24, 82), value, fill="#111827", font=metric_font)
        draw.text((left + 24, 145), label, fill="#64748B", font=small_font)

    mask = create_cloud_mask()
    placed = place_terms(terms, cluster_count, mask)
    cloud_alpha = Image.fromarray((mask.astype(np.uint8) * 255), mode="L")
    expanded = cloud_alpha.filter(ImageFilter.MaxFilter(17))
    outline_alpha = ImageChops.subtract(expanded, cloud_alpha)
    outline_layer = Image.new("RGB", (CLOUD_WIDTH, CLOUD_HEIGHT), "#D7E0EC")
    fill_layer = Image.new("RGB", (CLOUD_WIDTH, CLOUD_HEIGHT), "#F8FAFD")
    image.paste(outline_layer, (CLOUD_LEFT, CLOUD_TOP), outline_alpha)
    image.paste(fill_layer, (CLOUD_LEFT, CLOUD_TOP), cloud_alpha)

    for term in placed:
        left, top, _, _ = term["box"]
        base_color = CLUSTER_COLORS[term["cluster"] % len(CLUSTER_COLORS)]
        draw.text(
            (CLOUD_LEFT + left, CLOUD_TOP + top),
            term["text"],
            fill=base_color,
            font=term["font"],
        )

    cluster_terms: dict[int, list[dict]] = {}
    for term in terms:
        cluster_terms.setdefault(term["cluster"], []).append(term)
    legend_y = 1430
    draw.text((120, legend_y), "语义主题", fill="#111827", font=metric_font)
    legend_x = 380
    for cluster in sorted(cluster_terms):
        top_terms = sorted(cluster_terms[cluster], key=lambda item: item["score"], reverse=True)[:2]
        label = " / ".join(item["text"] for item in top_terms)
        color = CLUSTER_COLORS[cluster % len(CLUSTER_COLORS)]
        draw.rounded_rectangle((legend_x, legend_y - 5, legend_x + 24, legend_y + 19), radius=5, fill=color)
        draw.text((legend_x + 38, legend_y - 8), label, fill="#334155", font=legend_font)
        legend_x += min(560, 80 + draw.textlength(label, font=legend_font))

    method = "字号 = 词频 30% + TF-IDF 55% + 报告权重 15% · 语义聚类 = 词语-文档向量 KMeans · 布局 = 云形边界内螺旋碰撞检测"
    draw.text((120, 1580), method, fill="#64748B", font=small_font)
    draw.text(
        (120, 1625),
        f"数据来源：SZYG 智能情报报告 {report.get('id', '-')} · 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        fill="#94A3B8",
        font=small_font,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG", optimize=True)
    metadata = {
        "report_id": report.get("id"),
        "query": report.get("query"),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "algorithm": {
            "weight": "0.55*tfidf + 0.30*log_frequency + 0.15*report_prior",
            "semantic_clustering": "KMeans on normalized term-document TF-IDF vectors",
            "layout": "cluster-centered Archimedean spiral with collision and cloud-mask checks",
        },
        "terms": [
            {key: value for key, value in term.items() if key not in {"box", "font"}}
            for term in placed
        ],
    }
    output.with_suffix(".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    report = load_report(Path(args.input), args.report_id)
    documents = collect_documents(report)
    terms, cluster_count = build_terms(report, documents, args.max_words)
    draw_report(report, terms, cluster_count, Path(args.output))
    print(json.dumps({
        "ok": True,
        "report_id": report.get("id"),
        "documents": len(documents),
        "terms": len(terms),
        "clusters": cluster_count,
        "output": str(Path(args.output).resolve()),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
