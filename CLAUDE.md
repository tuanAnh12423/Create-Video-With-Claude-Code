# Quy chuẩn Dự án Tạo Video Tự Động (CLAUDE.md)

Pipeline: chủ đề → kịch bản (Claude API) → giọng đọc + SRT (edge-tts) → video nền (Pexels) → dựng video 1080x1920 (MoviePy + FFmpeg).

## Ngăn xếp công nghệ (Tech Stack)
- Ngôn ngữ: Python 3.11+
- Tạo kịch bản: Anthropic SDK (`anthropic`), model mặc định `claude-sonnet-5-5` (đổi bằng env `CLAUDE_MODEL`), structured output JSON schema
- Giọng đọc & Phụ đề: `edge-tts` (giọng `vi-VN-HoaiMyNeural` và `vi-VN-NamMinhNeural`)
- Nguồn video: Pexels Video API (`https://api.pexels.com/v1/videos/search`)
- Xử lý video: `moviepy` 2.x (API mới: `subclipped`, `resized`, `with_*`) và `ffmpeg`

## Cấu trúc
- `main.py` — CLI chạy toàn bộ pipeline (`--topic`, `--voice`, `--script`, `--keep-temp`)
- `src/script_generator.py` — sinh `{"title", "scenes": [{"narration", "search_query"}]}`
- `src/tts_generator.py` — `temp/audio/scene_XX.mp3|.srt`
- `src/pexels_fetcher.py` — `temp/videos/scene_XX.mp4`
- `src/video_composer.py` — render từng phân cảnh vào `temp/segments/`, ghép thành `output/final_video.mp4` + `output/final_video.srt`
- `.github/workflows/generate_video.yml` — chạy thủ công trên GitHub Actions, tải kết quả qua Artifacts

## Cách chạy thử nghiệm
```bash
pip install -r requirements.txt          # cần ffmpeg trong PATH
cp .env.example .env                     # điền ANTHROPIC_API_KEY, PEXELS_API_KEY
python -m py_compile main.py src/*.py    # kiểm tra cú pháp
python main.py --topic "Cách bảo quản thực phẩm trong tủ lạnh" --voice vi-VN-NamMinhNeural
python main.py --script output/script.json   # render lại từ kịch bản có sẵn, không tốn token Claude
```

## Quy tắc viết code bắt buộc
1. Không lưu cứng (hardcode) API key trong mã nguồn; luôn đọc `ANTHROPIC_API_KEY` và `PEXELS_API_KEY` từ biến môi trường (hoặc `.env` cục bộ, không commit).
2. Khi dùng MoviePy, luôn đóng các clip (`clip.close()`) sau khi render xong để tránh tràn bộ nhớ RAM trên máy ảo GitHub Actions.
3. Không commit các file `.mp4`, `.mp3`, `.srt` hoặc thư mục `temp/`, `output/` vào Git (đã có trong `.gitignore`).
4. Khi gọi Pexels API, luôn xử lý ngoại lệ (fallback sang từ khóa chung như "nature" hoặc "abstract background" nếu từ khóa cụ thể không trả về kết quả).
5. Trong workflow, truyền input người dùng qua `env:` rồi dùng `"$VAR"`, không chèn `${{ }}` trực tiếp vào lệnh `run`.

## Tối ưu bộ nhớ khi render
- Render từng phân cảnh ra file riêng rồi mới ghép — không giữ mọi clip trong RAM cùng lúc.
- Chọn file Pexels gần 1080p (tránh 4K), `threads=2`, preset `veryfast` cho phân đoạn.
- Phụ đề dùng `TextClip` (Pillow) với font hỗ trợ tiếng Việt (Noto Sans / DejaVu Sans); ghi đè bằng env `SUBTITLE_FONT`.
