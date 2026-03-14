FROM python:3.11-slim
WORKDIR /app
COPY collector/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY collector/server.py .
COPY generated/python ./generated/python
ENV GRPC_PORT=50051
ENV REDIS_HOST=redis
ENV REDIS_PORT=6379
ENV PROMETHEUS_PORT=8000
ENV PYTHONPATH=/app/generated/python
EXPOSE 50051 8000
CMD ["python", "server.py"]
