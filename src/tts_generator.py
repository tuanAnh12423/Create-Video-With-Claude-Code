"""Tạo giọng đọc MP3 và phụ đề SRT cho từng phân cảnh bằng edge-tts."""

import asyncio
import os

import edge_tts

DEFAULT_VOICE = "vi-VN-HoaiMyNeural"


async def _synthesize(text: str, voice: str, mp3_path: str, srt_path: str) -> None:
    communicate = edge_tts.Communicate(text, voice, boundary="SentenceBoundary")
    submaker = edge_tts.SubMaker()
    with open(mp3_path, "wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                submaker.feed(chunk)
    with open(srt_path, "w", encoding="utf-8") as srt_file:
        srt_file.write(submaker.get_srt())


def generate_scene_audio(scenes: list[dict], voice: str, out_dir: str) -> list[dict]:
    """Tạo `scene_XX.mp3` + `scene_XX.srt` cho mỗi phân cảnh.

    Trả về danh sách {"audio": path, "srt": path} theo thứ tự phân cảnh.
    """
    os.makedirs(out_dir, exist_ok=True)
    results = []
    for i, scene in enumerate(scenes):
        mp3_path = os.path.join(out_dir, f"scene_{i:02d}.mp3")
        srt_path = os.path.join(out_dir, f"scene_{i:02d}.srt")
        asyncio.run(_synthesize(scene["narration"], voice, mp3_path, srt_path))
        results.append({"audio": mp3_path, "srt": srt_path})
        print(f"  [TTS] Phân cảnh {i + 1}/{len(scenes)} xong")
    return results
