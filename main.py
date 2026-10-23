"""Chạy toàn bộ pipeline: chủ đề -> kịch bản -> giọng đọc -> video nền -> video hoàn chỉnh."""

import argparse
import json
import os
import shutil
import sys
import time

from dotenv import load_dotenv

from src.pexels_fetcher import fetch_scene_videos
from src.script_generator import generate_script, save_script
from src.tts_generator import DEFAULT_VOICE, generate_scene_audio
from src.video_composer import compose_video

OUTPUT_DIR = "output"
TEMP_DIR = "temp"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tạo video ngắn tự động từ một chủ đề")
    parser.add_argument("--topic", help="Chủ đề video")
    parser.add_argument("--voice", default=DEFAULT_VOICE, help="Giọng edge-tts (vi-VN-HoaiMyNeural / vi-VN-NamMinhNeural)")
    parser.add_argument("--script", help="Dùng file kịch bản JSON có sẵn thay vì gọi Claude")
    parser.add_argument("--keep-temp", action="store_true", help="Giữ thư mục temp/ sau khi render")
    args = parser.parse_args()
    if not args.topic and not args.script:
        parser.error("cần --topic hoặc --script")
    return args


def main() -> int:
    load_dotenv()
    args = parse_args()
    started = time.time()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    script_path = os.path.join(OUTPUT_DIR, "script.json")

    if args.script:
        print(f"[1/4] Đọc kịch bản từ {args.script}")
        with open(args.script, encoding="utf-8") as f:
            script = json.load(f)
    else:
        print(f"[1/4] Viết kịch bản cho chủ đề: {args.topic}")
        script = generate_script(args.topic)
    save_script(script, script_path)
    scenes = script["scenes"]
    print(f"      {len(scenes)} phân cảnh -> {script_path}")

    print(f"[2/4] Tạo giọng đọc ({args.voice})")
    audio_items = generate_scene_audio(scenes, args.voice, os.path.join(TEMP_DIR, "audio"))

    print("[3/4] Tải video nền từ Pexels")
    video_paths = fetch_scene_videos(scenes, os.path.join(TEMP_DIR, "videos"))

    print("[4/4] Dựng video")
    output = compose_video(video_paths, audio_items, os.path.join(TEMP_DIR, "segments"),
                           os.path.join(OUTPUT_DIR, "final_video.mp4"))

    if not args.keep_temp:
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
    print(f"Hoàn tất sau {time.time() - started:.0f}s: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
