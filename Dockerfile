FROM python:3.12-slim

# ffmpeg is required by yt-dlp (processing the downloaded videos)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Do not run as root
RUN useradd -m app
# Pre-create the thumbnail cache dir owned by "app": it's a mount point for a
# named volume (see docker-compose.yml), and Docker only seeds a *fresh*
# volume's permissions from what already exists here at that path - an
# already-provisioned volume keeps whatever ownership it started with.
RUN mkdir -p /app/data/thumbnails && chown -R app:app /app/data
USER app

ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=60s --timeout=5s --start-period=15s \
    CMD python -c "import urllib.request, os; urllib.request.urlopen(f'http://localhost:{os.getenv(\"PORT\", \"8000\")}/health')"

CMD ["python", "main.py"]
