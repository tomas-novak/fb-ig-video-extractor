import os
import tempfile
import yt_dlp


FFMPEG_LOCATIONS = [
    # Railway (nixpacks)
    "/usr/bin/ffmpeg",
    # Windows winget
    r"C:\Users\novak\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe",
]


def _find_ffmpeg() -> str | None:
    override = os.getenv("FFMPEG_LOCATION")
    if override:
        return override
    for path in FFMPEG_LOCATIONS:
        if os.path.exists(path):
            return path
    return None


def download_audio(url: str) -> tuple[str, dict]:
    """Download audio from Facebook/Instagram URL. Returns (audio_path, info_dict)."""
    tmp_dir = tempfile.mkdtemp()
    output_template = os.path.join(tmp_dir, "%(id)s.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "64",
        }],
        "quiet": True,
        "no_warnings": True,
        "cookiefile": os.getenv("COOKIES_FILE"),
    }

    ffmpeg = _find_ffmpeg()
    if ffmpeg:
        ydl_opts["ffmpeg_location"] = os.path.dirname(ffmpeg)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_id = info.get("id", "video")
        audio_path = os.path.join(tmp_dir, f"{video_id}.mp3")

    return audio_path, info


def extract_source(url: str) -> str:
    if "instagram.com" in url:
        return "instagram"
    if "facebook.com" in url or "fb.watch" in url:
        return "facebook"
    return "unknown"
