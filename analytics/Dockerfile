FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV REDIS_HOST=redis
ENV REDIS_PORT=6379
ENV PROMETHEUS_PORT=8001
ENV RETRAIN_EVERY=300
ENV ANALYSIS_INTERVAL=10
ENV MIN_TRAIN_SAMPLES=100
EXPOSE 8001
CMD ["python", "analyzer.py"]
