FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV XDG_CACHE_HOME=/app/data/cache
ENV HF_HOME=/app/data/cache/huggingface
ENV TRANSFORMERS_CACHE=/app/data/cache/huggingface/transformers
ENV SENTENCE_TRANSFORMERS_HOME=/app/data/cache/sentence-transformers

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x startup.sh scripts/start_backend.sh scripts/start_frontend.sh

EXPOSE 8080 8501

CMD ["./startup.sh"]
