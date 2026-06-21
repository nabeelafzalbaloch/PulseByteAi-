# STEP 5 — video rendering (ffmpeg + whisper)
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# whisper "tiny" model build me download -> runtime fast
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('tiny')"

COPY . .
CMD ["python", "telegram_bot.py"]
