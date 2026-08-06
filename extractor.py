import os
import shutil
import tempfile
import yt_dlp

from i18n import t


# Fallbacks for when ffmpeg is not on PATH. Installs in non-standard locations
# (e.g. Windows winget) are covered by the FFMPEG_LOCATION env variable.
FFMPEG_LOCATIONS = [
    # Linux (apt)
    "/usr/bin/ffmpeg",
]


def _find_ffmpeg() -> str | None:
    override = os.getenv("FFMPEG_LOCATION")
    if override:
        return override
    # Primarily via the system PATH (finds apt/nix/winget installs)
    on_path = shutil.which("ffmpeg")
    if on_path:
        return on_path
    for path in FFMPEG_LOCATIONS:
        if os.path.exists(path):
            return path
    return None


def ffmpeg_diagnostics() -> dict:
    """Diagnostics of ffmpeg/ffprobe availability – for the /debug endpoint."""
    ffmpeg = _find_ffmpeg()
    ffprobe_which = shutil.which("ffprobe")
    ffprobe_sibling = None
    if ffmpeg:
        cand = os.path.join(os.path.dirname(ffmpeg), "ffprobe")
        if os.path.exists(cand):
            ffprobe_sibling = cand
    cookies = _resolve_cookies()
    cookie_lines = 0
    if cookies and os.path.exists(cookies):
        with open(cookies, encoding="utf-8", errors="ignore") as f:
            cookie_lines = sum(1 for ln in f if ln.strip() and not ln.startswith("#"))
    return {
        "ffmpeg": ffmpeg,
        "ffprobe_on_path": ffprobe_which,
        "ffprobe_sibling": ffprobe_sibling,
        "ffprobe_available": bool(ffprobe_which or ffprobe_sibling),
        "cookies_configured": bool(cookies),
        "cookie_entries": cookie_lines,
    }


_cookie_path_cache = None


def _resolve_cookies() -> str | None:
    """Return the path to the cookies file.
    Locally: COOKIES_FILE = path to the file.
    On the server: INSTAGRAM_COOKIES = contents of cookies.txt (written to a temp file)."""
    global _cookie_path_cache
    path = os.getenv("COOKIES_FILE")
    if path and os.path.exists(path):
        return path
    content = os.getenv("INSTAGRAM_COOKIES")
    if content:
        if _cookie_path_cache and os.path.exists(_cookie_path_cache):
            return _cookie_path_cache
        fd, tmp = tempfile.mkstemp(prefix="cookies_", suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        _cookie_path_cache = tmp
        return tmp
    return None


# Videos longer than the limit are not downloaded at all – the bot is built for
# short videos (Reels, TikTok, Shorts); for long ones both the download and the
# upload to Gemini would be slow and expensive. 0 = no limit; empty = default 10.
MAX_VIDEO_MINUTES = int(os.getenv("MAX_VIDEO_MINUTES") or 10)


def duration_error(info: dict) -> str | None:
    """Message when the video is longer than MAX_VIDEO_MINUTES; None otherwise.
    An unknown duration (live stream, missing metadata) passes through – it is
    caught later by the Gemini processing timeout."""
    duration = info.get("duration") or 0
    if MAX_VIDEO_MINUTES and duration > MAX_VIDEO_MINUTES * 60:
        return t("err_video_too_long", minutes=duration / 60, limit=MAX_VIDEO_MINUTES)
    return None


def download_media(url: str) -> tuple[str, dict]:
    """Download a video from FB/IG. Returns (media_path, info_dict).
    We download the video directly (not audio) – Gemini transcribes its sound and reads
    on-screen text, and above all we do not depend on the audio-only stream that FB
    does not offer to datacenter IPs."""
    tmp_dir = tempfile.mkdtemp()
    output_template = os.path.join(tmp_dir, "%(id)s.%(ext)s")

    ydl_opts = {
        # Progressive FB formats (hd/sd) are reasonably sized mp4; best as a fallback (and for IG).
        "format": "hd/sd/best",
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
    }

    # Cookies are a workaround for platforms that block anonymous downloads from
    # datacenter IPs: Instagram practically always, YouTube often ("Sign in to
    # confirm you're not a bot"). FB and TikTok still work anonymously.
    if extract_source(url) in ("instagram", "youtube"):
        cookies = _resolve_cookies()
        if cookies:
            ydl_opts["cookiefile"] = cookies

    ffmpeg = _find_ffmpeg()
    if ffmpeg:
        ydl_opts["ffmpeg_location"] = os.path.dirname(ffmpeg)

    # match_filter skips downloading a long video (metadata is still returned, so
    # below we can raise a clear error instead of failing on a missing file)
    if MAX_VIDEO_MINUTES:
        ydl_opts["match_filter"] = lambda info, *, incomplete=False: duration_error(info)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            err = duration_error(info)
            if err:
                raise RuntimeError(err)
            media_path = ydl.prepare_filename(info)
        if not os.path.exists(media_path):
            files = os.listdir(tmp_dir)
            if files:
                media_path = os.path.join(tmp_dir, files[0])
        return media_path, info
    except BaseException:
        # On failure clean up the temp directory, otherwise it would pile up on the server.
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise


def extract_source(url: str) -> str:
    """Platform derived from the URL – the value for column L (Source) in the sheet.
    Also covers short share links (fb.watch, vm.tiktok.com, youtu.be)."""
    if "instagram.com" in url:
        return "instagram"
    if "facebook.com" in url or "fb.watch" in url:
        return "facebook"
    if "tiktok.com" in url:  # including vm.tiktok.com share links
        return "tiktok"
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    return "unknown"
