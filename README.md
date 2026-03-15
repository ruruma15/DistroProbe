# DistroProbe — Distributed Network Telemetry & AI Analytics

A high-performance distributed telemetry system that continuously measures network latency across multiple probes, streams metrics via gRPC, detects anomalies using an LSTM neural network, and visualizes everything in a live Grafana dashboard.

---

## Architecture
```
[Java Probe] ──┐
               ├──► [gRPC Collector] ──► [Redis] ──► [LSTM Analytics]
[Go Probe]  ──┘           │                                  │
                           └──► [Prometheus] ──► [Grafana Dashboard]
```

- **Java Probe** — measures latency using a pre-allocated Circular Buffer (zero GC pressure), streams metrics via gRPC client-side streaming
- **Go Probe** — measures latency to multiple hosts concurrently using goroutines, streams via gRPC
- **Python Collector** — gRPC server that receives metric streams and writes to Redis using pipeline batching
- **Redis** — stores latest metric per probe + time-series of last 1000 readings per probe
- **LSTM Analytics** — PyTorch LSTM Autoencoder that learns normal latency patterns and flags anomalies
- **Prometheus + Grafana** — live observability dashboard with p50/p95/p99 latency panels and anomaly score gauges

---

## Benchmark Results

Redis pipeline caching vs direct writes — 1000 iterations, 50,000 total metric writes:

| Metric | Direct (ms) | Pipeline (ms) | Reduction |
|--------|-------------|---------------|-----------|
| p50    | 121.820     | 3.930         | **96.8%** |
| p95    | 162.158     | 7.295         | **95.5%** |
| p99    | 229.403     | 9.080         | **96.0%** |

Full results in `benchmark/results.json`.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Probe (JVM) | Java 17, gRPC-Java, Protobuf |
| Probe (Systems) | Go 1.24, goroutines, gRPC-Go |
| Transport | gRPC, Protocol Buffers |
| Collector | Python 3.11, grpcio |
| Cache | Redis 7, pipeline batching |
| ML | PyTorch, LSTM Autoencoder |
| Observability | Prometheus, Grafana |
| Infrastructure | Docker Compose, Kubernetes, HPA |

---

## Quick Start

### Prerequisites
- Docker Desktop running
- Java 17+, Go 1.24+, Python 3.11+, Maven

### Run locally
```bash
git clone https://github.com/ruruma15/DistroProbe.git
cd DistroProbe
docker compose up --build
```

| Service | URL |
|---------|-----|
| Grafana Dashboard | http://localhost:3000 (admin / distro123) |
| Prometheus | http://localhost:9090 |
| Collector gRPC | localhost:50051 |
| Redis | localhost:6379 |

### Run benchmark
```bash
docker compose up -d redis
cd benchmark && python3 benchmark.py
```

---

## Project Structure
```
DistroProbe/
├── proto/                  # Protobuf service definition
├── probe-java/             # Java probe with Circular Buffer
├── probe-go/               # Go probe with concurrent goroutines
├── collector/              # Python gRPC collector + Redis writer
├── analytics/              # LSTM anomaly detection
├── benchmark/              # Latency benchmark harness
├── grafana/                # Dashboard + datasource provisioning
├── k8s/                    # Kubernetes manifests + HPA
├── prometheus.yml          # Prometheus scrape config
└── docker-compose.yml      # Full local stack
```

---

## Kubernetes Deployment
```bash
kubectl apply -f k8s/namespace.yml
kubectl apply -f k8s/configmap.yml
kubectl apply -f k8s/redis.yml
kubectl apply -f k8s/collector.yml
kubectl apply -f k8s/probe-java.yml
kubectl apply -f k8s/probe-go.yml
kubectl apply -f k8s/analytics.yml
kubectl apply -f k8s/hpa.yml
```

The Horizontal Pod Autoscaler scales the collector from 1 to 5 replicas when CPU exceeds 60% or memory exceeds 70%.

---

## Key Design Decisions

**Why a Circular Buffer in Java?**
Pre-allocated fixed-size array avoids heap allocation during the measurement loop. No GC pauses = consistent sub-millisecond write latency. Same pattern used in HFT systems.

**Why Go for the second probe?**
Go's goroutines let us measure all target hosts concurrently in parallel rather than sequentially. The Java probe measures one host at a time; the Go probe measures all three simultaneously.

**Why LSTM over simpler models?**
Latency anomalies are time-dependent — a spike only makes sense in context of the preceding pattern. LSTM captures this temporal dependency. Linear regression cannot.

**Why Redis pipeline?**
Each metric write involves 3 Redis commands (SET, LPUSH, LTRIM). Without pipelining, each command is a separate network round trip. Pipelining batches all commands into one round trip — benchmark shows 96% p99 reduction.
