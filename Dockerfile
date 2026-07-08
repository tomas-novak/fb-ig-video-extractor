FROM python:3.12-slim

# ffmpeg je potřeba pro yt-dlp (zpracování stažených videí)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Neběžet jako root
RUN useradd -m app
USER app

ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=60s --timeout=5s --start-period=15s \
    CMD python -c "import urllib.request, os; urllib.request.urlopen(f'http://localhost:{os.getenv(\"PORT\", \"8000\")}/health')"

CMD ["python", "main.py"]
