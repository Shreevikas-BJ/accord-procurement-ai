FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr poppler-utils gosu && rm -rf /var/lib/apt/lists/*
WORKDIR /app/apps/api
COPY apps/api/requirements.lock.txt ./requirements.lock.txt
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY apps/api ./
COPY demo-data /app/demo-data
RUN useradd --create-home procurement && mkdir -p /app/data/uploads && chown -R procurement:procurement /app && sed -i 's/\r$//' docker-entrypoint.sh && chmod +x docker-entrypoint.sh
ENTRYPOINT ["/app/apps/api/docker-entrypoint.sh"]
EXPOSE 8000
