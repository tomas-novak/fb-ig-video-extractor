import html
import os
import re
import shutil
import tempfile
import httpx
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
            try:
                info = ydl.extract_info(url, download=True)
            except yt_dlp.utils.DownloadError as e:
                # yt-dlp's Instagram extractor has no downloadable formats for
                # photo posts at all (video-only) - fall back to grabbing the
                # photo directly instead of failing the post. Carousels raise
                # a generic message from the playlist wrapper and still expose
                # raw entries/thumbnails via process=False; single-photo posts
                # raise from deep inside the extractor itself before any info
                # is returned at all, so that path needs a page-scrape instead.
                msg = str(e)
                if "No video formats found" in msg:
                    raw = ydl.extract_info(url, download=False, process=False)
                    return _download_photo(raw, tmp_dir)
                if "There is no video in this post" in msg:
                    return _download_photo_via_webpage(url, tmp_dir)
                raise
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


def _download_photo(raw_info: dict, tmp_dir: str) -> tuple[str, dict]:
    """Fallback for Instagram photo/carousel posts. yt-dlp's Instagram extractor
    finds no downloadable formats for these at all (video-only), so instead we
    grab the highest-resolution CDN thumbnail of the first photo directly.
    raw_info is the un-processed result of extract_info(process=False), whose
    top-level fields (id/uploader/description/title) already match what the
    rest of the pipeline expects from a video's info dict."""
    entries = list(raw_info.get("entries") or [raw_info])
    first = entries[0]
    thumbnails = first.get("thumbnails") or []
    if not thumbnails:
        raise RuntimeError("no photo found in post")
    # yt-dlp orders Instagram thumbnails from lowest to highest resolution.
    photo_url = thumbnails[-1]["url"]
    photo_path = os.path.join(tmp_dir, f"{first.get('id', 'photo')}.jpg")
    with httpx.stream("GET", photo_url, timeout=30) as r:
        r.raise_for_status()
        with open(photo_path, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)
    return photo_path, raw_info


def _download_photo_via_webpage(url: str, tmp_dir: str) -> tuple[str, dict]:
    """Second-level fallback for single (non-carousel) Instagram photo posts.
    For these yt-dlp's extractor raises deep inside its own code before
    returning any info at all, even with process=False, so there is nothing
    to fall back on within yt-dlp itself. Instagram still serves standard
    Open Graph meta tags on the public post page (for link previews), so we
    scrape the photo URL and caption straight from there instead."""
    r = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15, follow_redirects=True)
    r.raise_for_status()
    page = r.text

    def og(prop: str) -> str:
        m = re.search(rf'<meta property="{prop}" content="([^"]*)"', page)
        return html.unescape(m.group(1)) if m else ""

    photo_url = og("og:image")
    if not photo_url:
        raise RuntimeError("no photo found in post")

    # og:title is "{author} on Instagram: "{caption}"" for posts with a caption.
    author, _, rest = og("og:title").partition(" on Instagram: ")
    description = rest.strip().strip('"') if rest else og("og:description")

    post_id = url.rstrip("/").rsplit("/", 1)[-1]
    photo_path = os.path.join(tmp_dir, f"{post_id}.jpg")
    with httpx.stream("GET", photo_url, timeout=30) as resp:
        resp.raise_for_status()
        with open(photo_path, "wb") as f:
            for chunk in resp.iter_bytes():
                f.write(chunk)
    return photo_path, {"id": post_id, "uploader": author, "description": description, "title": ""}


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
