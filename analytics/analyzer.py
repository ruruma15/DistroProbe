import sys
import os
import time
import json
import logging
import redis
from prometheus_client import start_http_server, Gauge, Counter
from trainer import AnomalyTrainer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [Analytics] %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger(__name__)

# config
REDIS_HOST        = os.getenv('REDIS_HOST',          'localhost')
REDIS_PORT        = int(os.getenv('REDIS_PORT',       '6379'))
PROMETHEUS_PORT   = int(os.getenv('PROMETHEUS_PORT',  '8001'))
RETRAIN_EVERY     = int(os.getenv('RETRAIN_EVERY',    '300'))
ANALYSIS_INTERVAL = int(os.getenv('ANALYSIS_INTERVAL','10'))
MIN_TRAIN_SAMPLES = int(os.getenv('MIN_TRAIN_SAMPLES','100'))

# metrics
anomaly_score_gauge = Gauge(
    'distro_anomaly_score',
    'Current anomaly score per probe',
    ['probe_id']
)
anomaly_detected = Counter(
    'distro_anomalies_detected_total',
    'Total anomalies detected',
    ['probe_id', 'severity']
)
model_trained_gauge = Gauge(
    'distro_model_trained',
    'Whether the LSTM model has been trained (1=yes, 0=no)',
    ['probe_id']
)

SEVERITY_THRESHOLDS = {
    'LOW':      0.3,
    'MEDIUM':   0.5,
    'HIGH':     0.75,
    'CRITICAL': 0.9
}

def get_severity(score):
    if score >= SEVERITY_THRESHOLDS['CRITICAL']: return 'CRITICAL'
    if score >= SEVERITY_THRESHOLDS['HIGH']:     return 'HIGH'
    if score >= SEVERITY_THRESHOLDS['MEDIUM']:   return 'MEDIUM'
    if score >= SEVERITY_THRESHOLDS['LOW']:      return 'LOW'
    return 'NONE'

def connect_redis():
    for attempt in range(10):
        try:
            r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT,
                          decode_responses=True, socket_connect_timeout=5)
            r.ping()
            log.info(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
            return r
        except Exception as e:
            log.warning(f"Redis not ready ({attempt+1}/10): {e}")
            time.sleep(3)
    raise RuntimeError("Could not connect to Redis")

def get_probe_timeseries(r, probe_id, limit=500):
    key  = f"probe:timeseries:{probe_id}"
    data = r.lrange(key, 0, limit - 1)
    values = []
    for item in data:
        try:
            values.append(json.loads(item)['latency_ms'])
        except Exception:
            continue
    return list(reversed(values))

def run():
    r        = connect_redis()
    trainers = {}
    last_train = {}

    start_http_server(PROMETHEUS_PORT)
    log.info(f"Prometheus metrics at http://localhost:{PROMETHEUS_PORT}")
    log.info("Starting anomaly detection loop...\n")

    while True:
        try:
            probe_ids = r.smembers("probes:active")

            for probe_id in probe_ids:
                now    = time.time()
                values = get_probe_timeseries(r, probe_id)

                if len(values) < MIN_TRAIN_SAMPLES:
                    log.info(f"[{probe_id}] Waiting for data ({len(values)}/{MIN_TRAIN_SAMPLES})")
                    model_trained_gauge.labels(probe_id=probe_id).set(0)
                    continue

                if probe_id not in trainers:
                    trainers[probe_id]   = AnomalyTrainer()
                    last_train[probe_id] = 0

                trainer = trainers[probe_id]

                if now - last_train.get(probe_id, 0) > RETRAIN_EVERY:
                    log.info(f"[{probe_id}] Training LSTM on {len(values)} samples...")
                    success = trainer.train(values)
                    if success:
                        last_train[probe_id] = now
                        model_trained_gauge.labels(probe_id=probe_id).set(1)

                if trainer.is_trained():
                    score, is_anomaly = trainer.score(values)
                    severity = get_severity(score)

                    anomaly_score_gauge.labels(probe_id=probe_id).set(score)
                    log.info(f"[{probe_id}] score={score:.4f} | severity={severity} | anomaly={is_anomaly}")

                    if is_anomaly:
                        anomaly_detected.labels(
                            probe_id=probe_id,
                            severity=severity
                        ).inc()

                        alert = {
                            "probe_id":      probe_id,
                            "latency_ms":    values[-1] if values else 0,
                            "anomaly_score": score,
                            "severity":      severity,
                            "detected_at":   now
                        }
                        r.lpush(f"alerts:{probe_id}", json.dumps(alert))
                        r.ltrim(f"alerts:{probe_id}", 0, 99)
                        log.warning(f"ANOMALY DETECTED [{severity}] probe={probe_id} score={score:.4f}")

        except Exception as e:
            log.error(f"Analysis error: {e}")

        time.sleep(ANALYSIS_INTERVAL)

if __name__ == '__main__':
    run()
