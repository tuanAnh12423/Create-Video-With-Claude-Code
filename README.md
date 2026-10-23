# Create Video With Claude Code

Ứng dụng tạo video ngắn dọc (9:16) tự động từ một chủ đề: Claude viết kịch bản tiếng Việt, edge-tts đọc lời bình và tạo phụ đề, Pexels cung cấp video nền, MoviePy + FFmpeg dựng thành `final_video.mp4`.

## Chạy trên GitHub Actions
1. Thêm secrets `ANTHROPIC_API_KEY` và `PEXELS_API_KEY` tại **Settings → Secrets and variables → Actions**.
2. Mở tab **Actions → Auto Video Generator → Run workflow**, nhập chủ đề, chọn giọng đọc.
3. Khi chạy xong, tải video, phụ đề và kịch bản JSON trong mục **Artifacts**.

## Chạy trên máy
```bash
pip install -r requirements.txt   # cần cài ffmpeg
cp .env.example .env              # điền API key
python main.py --topic "5 mẹo dùng máy giặt bền lâu" --voice vi-VN-HoaiMyNeural
```
Kết quả nằm trong `output/`: `final_video.mp4`, `final_video.srt`, `script.json`.

Có thể sửa tay `output/script.json` rồi render lại mà không gọi Claude: `python main.py --script output/script.json`.
