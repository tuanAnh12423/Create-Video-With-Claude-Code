"""Sinh kịch bản video ngắn (30-60 giây) bằng Claude API, trả về JSON các phân cảnh."""

import json
import os

import anthropic

DEFAULT_MODEL = "claude-sonnet-5-5"

SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "narration": {"type": "string"},
                    "search_query": {"type": "string"},
                },
                "required": ["narration", "search_query"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "scenes"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """Bạn là biên kịch video ngắn dạng dọc (TikTok, YouTube Shorts, Reels).
Viết kịch bản tiếng Việt tự nhiên, dễ nghe khi đọc thành tiếng, tổng thời lượng 30-60 giây
(khoảng 90-150 từ), chia thành 5-8 phân cảnh. Câu mở đầu phải gây tò mò, câu cuối có lời kêu gọi
hoặc kết luận ngắn gọn.

Với mỗi phân cảnh:
- "narration": 1-2 câu lời bình tiếng Việt, không dùng ký hiệu đặc biệt, emoji hay chú thích sân khấu.
- "search_query": 1-3 từ khóa tiếng Anh cụ thể, mô tả hình ảnh cần quay, để tìm stock video trên Pexels
  (ví dụ "galaxy stars", "washing machine", "city night")."""


def generate_script(topic: str, model: str | None = None) -> dict:
    """Gọi Claude để sinh kịch bản cho chủ đề `topic`.

    Trả về dict {"title": str, "scenes": [{"narration": str, "search_query": str}, ...]}.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("Thiếu biến môi trường ANTHROPIC_API_KEY")

    client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model=model or os.environ.get("CLAUDE_MODEL", DEFAULT_MODEL),
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": SCRIPT_SCHEMA},
        },
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Chủ đề video: {topic}"}],
    )

    if response.stop_reason == "refusal":
        raise RuntimeError(f"Claude từ chối tạo kịch bản cho chủ đề này: {response.stop_details}")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("Kịch bản bị cắt ngang do vượt max_tokens")

    text = next(b.text for b in response.content if b.type == "text")
    script = json.loads(text)
    script["scenes"] = [
        s for s in script["scenes"] if s["narration"].strip() and s["search_query"].strip()
    ]
    if not script["scenes"]:
        raise RuntimeError("Kịch bản không có phân cảnh hợp lệ")
    script["topic"] = topic
    return script


def save_script(script: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)
