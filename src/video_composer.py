"""Dựng video 1080x1920: khớp video nền với giọng đọc, chèn phụ đề, ghép các phân cảnh."""

import os
import re
import subprocess

from imageio_ffmpeg import get_ffmpeg_exe
from moviepy import (
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    TextClip,
    VideoFileClip,
    vfx,
)
from PIL import ImageFont

WIDTH, HEIGHT = 1080, 1920
FPS = 30
FONT_SIZE = 68
TEXT_MAX_WIDTH = WIDTH - 160
SCENE_PADDING = 0.25  # giây nghỉ sau mỗi câu đọc

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]

_SRT_TIME = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)")


def find_font() -> str:
    """Font hỗ trợ tiếng Việt; có thể ghi đè bằng biến môi trường SUBTITLE_FONT."""
    custom = os.environ.get("SUBTITLE_FONT")
    if custom and os.path.exists(custom):
        return custom
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    raise RuntimeError("Không tìm thấy font cho phụ đề; đặt SUBTITLE_FONT=/đường/dẫn/font.ttf")


def _to_seconds(ts: str) -> float:
    h, m, s, ms = _SRT_TIME.match(ts.strip()).groups()
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def _format_ts(seconds: float) -> str:
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_srt(path: str) -> list[tuple[float, float, str]]:
    with open(path, encoding="utf-8") as f:
        blocks = re.split(r"\n\s*\n", f.read().strip())
    cues = []
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        start, end = lines[1].split("-->")
        cues.append((_to_seconds(start), _to_seconds(end), " ".join(lines[2:]).strip()))
    return cues


def _fit_background(path: str, duration: float) -> VideoFileClip:
    """Phóng to phủ kín 9:16, cắt giữa, rồi cắt/lặp cho đúng `duration`."""
    clip = VideoFileClip(path, audio=False)
    scale = max(WIDTH / clip.w, HEIGHT / clip.h)
    clip = clip.resized(scale).cropped(
        x_center=clip.w * scale / 2, y_center=clip.h * scale / 2, width=WIDTH, height=HEIGHT
    )
    if clip.duration < duration:
        return clip.with_effects([vfx.Loop(duration=duration)])
    return clip.subclipped(0, duration)


def _wrap_text(text: str, font: str) -> str:
    """Ngắt dòng theo độ rộng thực tế của chữ (không cắt giữa từ)."""
    measure = ImageFont.truetype(font, FONT_SIZE)
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and measure.getlength(candidate) > TEXT_MAX_WIDTH:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return "\n".join(lines)


def _subtitle_clips(cues, font: str, duration: float) -> list[TextClip]:
    clips = []
    for start, end, text in cues:
        if start >= duration:
            continue
        txt = TextClip(
            font=font,
            text=_wrap_text(text, font),
            font_size=FONT_SIZE,
            color="white",
            stroke_color="black",
            stroke_width=4,
            method="label",
            text_align="center",
            margin=(10, 20),
        )
        clips.append(
            txt.with_start(start).with_duration(min(end, duration) - start).with_position(("center", HEIGHT * 0.68))
        )
    return clips


def render_scene(video_path: str, audio_path: str, srt_path: str, out_path: str, font: str) -> float:
    """Render một phân cảnh ra file mp4 riêng. Trả về thời lượng (giây)."""
    audio = AudioFileClip(audio_path)
    duration = audio.duration + SCENE_PADDING
    background = _fit_background(video_path, duration)
    subtitles = _subtitle_clips(parse_srt(srt_path), font, duration)
    # CompositeAudioClip trả về khoảng lặng sau khi giọng đọc kết thúc (phần SCENE_PADDING)
    voice = CompositeAudioClip([audio]).with_duration(duration)
    scene = CompositeVideoClip([background, *subtitles], size=(WIDTH, HEIGHT)).with_audio(voice).with_duration(duration)
    try:
        scene.write_videofile(
            out_path, fps=FPS, codec="libx264", audio_codec="aac", preset="veryfast", threads=2, logger=None
        )
    finally:
        for c in (scene, background, voice, audio, *subtitles):
            c.close()
    return duration


def merge_srt(srt_paths: list[str], durations: list[float], out_path: str) -> None:
    """Gộp phụ đề từng phân cảnh thành 1 file SRT theo dòng thời gian video cuối."""
    offset, index, lines = 0.0, 1, []
    for path, dur in zip(srt_paths, durations):
        for start, end, text in parse_srt(path):
            lines.append(f"{index}\n{_format_ts(start + offset)} --> {_format_ts(end + offset)}\n{text}\n")
            index += 1
        offset += dur
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def concat_segments(segment_paths: list[str], output_path: str, temp_dir: str) -> None:
    """Ghép các phân đoạn đã render bằng FFmpeg concat: copy luồng video, chỉ mã hóa lại audio.

    Các phân đoạn cùng codec/kích thước/fps nên không cần render lại hình, nhanh và gần như không tốn RAM.
    """
    list_path = os.path.join(temp_dir, "concat.txt")
    with open(list_path, "w", encoding="utf-8") as f:
        for p in segment_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
    subprocess.run(
        [get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", list_path,
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output_path],
        check=True,
    )


def compose_video(video_paths: list[str], audio_items: list[dict], temp_dir: str, output_path: str) -> str:
    """Render từng phân cảnh (tiết kiệm RAM) rồi ghép thành video cuối."""
    font = find_font()
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    segment_paths, durations = [], []
    for i, (video, audio) in enumerate(zip(video_paths, audio_items)):
        seg = os.path.join(temp_dir, f"segment_{i:02d}.mp4")
        durations.append(render_scene(video, audio["audio"], audio["srt"], seg, font))
        segment_paths.append(seg)
        print(f"  [Render] Phân cảnh {i + 1}/{len(video_paths)} ({durations[-1]:.1f}s)")

    concat_segments(segment_paths, output_path, temp_dir)
    merge_srt([a["srt"] for a in audio_items], durations, os.path.splitext(output_path)[0] + ".srt")
    return output_path
