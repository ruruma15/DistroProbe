FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY ../generated /app/generated
ENV GRPC_PORT=50051
ENV REDIS_HOST=redis
ENV REDIS_PORT=6379
ENV PROMETHEUS_PORT=8000
EXPOSE 50051 8000
CMD ["python", "server.py"]
