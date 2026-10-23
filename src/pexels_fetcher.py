"""Tìm và tải stock video từ Pexels API theo từ khóa của từng phân cảnh."""

import os

import requests

SEARCH_URL = "https://api.pexels.com/v1/videos/search"
FALLBACK_QUERIES = ["nature", "abstract background"]
TIMEOUT = 30


def _pick_file(video: dict, orientation: str) -> dict | None:
    """Chọn file HD phù hợp nhất (ưu tiên đúng hướng, độ phân giải gần 1080p)."""
    files = [f for f in video.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("width")]
    if orientation == "portrait":
        files = [f for f in files if f["height"] >= f["width"]] or files
    elif orientation == "landscape":
        files = [f for f in files if f["width"] >= f["height"]] or files
    if not files:
        return None
    # Gần 1080 cạnh ngắn nhất, tránh tải 4K nặng
    return min(files, key=lambda f: abs(min(f["width"], f["height"]) - 1080))


def search_video(query: str, api_key: str, orientation: str = "portrait", exclude_ids: set | None = None) -> str | None:
    """Trả về URL tải video đầu tiên khớp từ khóa, hoặc None."""
    resp = requests.get(
        SEARCH_URL,
        headers={"Authorization": api_key},
        params={"query": query, "orientation": orientation, "size": "medium", "per_page": 15},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    for video in resp.json().get("videos", []):
        if exclude_ids and video["id"] in exclude_ids:
            continue
        file = _pick_file(video, orientation)
        if file:
            if exclude_ids is not None:
                exclude_ids.add(video["id"])
            return file["link"]
    return None


def download(url: str, path: str) -> None:
    with requests.get(url, stream=True, timeout=TIMEOUT) as resp:
        resp.raise_for_status()
        with open(path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                f.write(chunk)


def fetch_scene_videos(scenes: list[dict], out_dir: str, orientation: str = "portrait") -> list[str]:
    """Tải 1 video cho mỗi phân cảnh; fallback sang từ khóa chung nếu không có kết quả."""
    api_key = os.environ.get("PEXELS_API_KEY")
    if not api_key:
        raise RuntimeError("Thiếu biến môi trường PEXELS_API_KEY")

    os.makedirs(out_dir, exist_ok=True)
    used_ids: set = set()
    paths = []
    for i, scene in enumerate(scenes):
        url = None
        for query in [scene["search_query"], *FALLBACK_QUERIES]:
            try:
                url = search_video(query, api_key, orientation, used_ids)
            except requests.RequestException as e:
                print(f"  [Pexels] Lỗi tìm '{query}': {e}")
            if url:
                break
            print(f"  [Pexels] Không có kết quả cho '{query}', thử từ khóa khác")
        if not url:
            raise RuntimeError(f"Không tìm được video cho phân cảnh {i + 1}")

        path = os.path.join(out_dir, f"scene_{i:02d}.mp4")
        download(url, path)
        paths.append(path)
        print(f"  [Pexels] Phân cảnh {i + 1}/{len(scenes)}: '{query}' -> {path}")
    return paths
