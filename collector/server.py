import sys
import os
import time
import json
import logging
import grpc
from concurrent import futures
from prometheus_client import start_http_server, Counter, Histogram, Gauge

# Add generated stubs to path
sys.path.insert(0, '/app')

import telemetry_pb2
import telemetry_pb2_grpc
import redis

# ── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [Collector] %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────
GRPC_PORT       = int(os.getenv('GRPC_PORT',       '50051'))
REDIS_HOST      = os.getenv('REDIS_HOST',           'localhost')
REDIS_PORT      = int(os.getenv('REDIS_PORT',       '6379'))
PROMETHEUS_PORT = int(os.getenv('PROMETHEUS_PORT',  '8000'))
REDIS_TTL       = int(os.getenv('REDIS_TTL',        '3600'))

# ── Prometheus metrics ────────────────────────────────────────────────────
metrics_received = Counter(
    'distro_metrics_received_total',
    'Total metrics received from probes',
    ['probe_id', 'probe_type', 'region']
)
latency_histogram = Histogram(
    'distro_latency_ms',
    'Latency measurements in milliseconds',
    ['probe_id', 'target_host'],
    buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000]
)
active_probes = Gauge(
    'distro_active_probes',
    'Number of unique probes reporting'
)
redis_write_errors = Counter(
    'distro_redis_write_errors_total',
    'Redis write failures'
)

# ── Redis connection ──────────────────────────────────────────────────────
def connect_redis():
    for attempt in range(10):
        try:
            r = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                decode_responses=True,
                socket_connect_timeout=5
            )
            r.ping()
            log.info(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
            return r
        except Exception as e:
            log.warning(f"Redis not ready (attempt {attempt+1}/10): {e}")
            time.sleep(2)
    raise RuntimeError("Could not connect to Redis after 10 attempts")

# ── gRPC Service ──────────────────────────────────────────────────────────
class TelemetryServicer(telemetry_pb2_grpc.TelemetryServiceServicer):

    def __init__(self, redis_client):
        self.redis  = redis_client
        self.probes = set()

    def StreamMetrics(self, request_iterator, context):
        metrics_stored = 0
        batch_start    = time.time()

        try:
            pipe = self.redis.pipeline()

            for metric in request_iterator:
                if metric.latency_ms <= 0:
                    continue

                key  = f"probe:latest:{metric.probe_id}"
                data = {
                    "probe_id":        metric.probe_id,
                    "target_host":     metric.target_host,
                    "latency_ms":      metric.latency_ms,
                    "timestamp_unix":  metric.timestamp_unix,
                    "region":          metric.region,
                    "probe_type":      metric.probe_type,
                    "sequence_number": metric.sequence_number,
                    "collected_at":    time.time()
                }
                pipe.setex(key, REDIS_TTL, json.dumps(data))

                ts_key = f"probe:timeseries:{metric.probe_id}"
                pipe.lpush(ts_key, json.dumps(data))
                pipe.ltrim(ts_key, 0, 999)
                pipe.sadd("probes:active", metric.probe_id)

                metrics_received.labels(
                    probe_id=metric.probe_id,
                    probe_type=metric.probe_type,
                    region=metric.region
                ).inc()
                latency_histogram.labels(
                    probe_id=metric.probe_id,
                    target_host=metric.target_host
                ).observe(metric.latency_ms)

                metrics_stored += 1

            pipe.execute()

            probe_count = self.redis.scard("probes:active")
            active_probes.set(probe_count)

            elapsed = (time.time() - batch_start) * 1000
            log.info(
                f"Stored {metrics_stored} metrics in {elapsed:.1f}ms | "
                f"active probes={probe_count}"
            )

        except redis.RedisError as e:
            redis_write_errors.inc()
            log.error(f"Redis write error: {e}")
            return telemetry_pb2.CollectorAck(
                received=False,
                message=f"Redis error: {str(e)}",
                server_time=int(time.time()),
                metrics_stored=0
            )

        return telemetry_pb2.CollectorAck(
            received=True,
            message=f"OK - stored {metrics_stored} metrics",
            server_time=int(time.time()),
            metrics_stored=metrics_stored
        )

# ── Server startup ────────────────────────────────────────────────────────
def serve():
    redis_client = connect_redis()

    start_http_server(PROMETHEUS_PORT)
    log.info(f"Prometheus metrics at http://localhost:{PROMETHEUS_PORT}")

    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        options=[
            ('grpc.max_receive_message_length', 100 * 1024 * 1024),
            ('grpc.max_send_message_length',    100 * 1024 * 1024),
        ]
    )
    telemetry_pb2_grpc.add_TelemetryServiceServicer_to_server(
        TelemetryServicer(redis_client), server
    )
    server.add_insecure_port(f'[::]:{GRPC_PORT}')
    server.start()

    log.info(f"gRPC server listening on port {GRPC_PORT}")
    log.info("Ready to receive metrics from probes...\n")

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        log.info("Shutting down...")
        server.stop(0)

if __name__ == '__main__':
    serve()
