#!/usr/bin/env python3
"""
DistroProbe Benchmark Harness
Measures latency reduction from Redis pipeline caching vs direct writes.
Run with: docker compose up -d redis collector && python benchmark.py
"""

import sys
import os
import time
import json
import random
import statistics
import argparse

import redis
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'generated', 'python'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'generated'))

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
ITERATIONS = int(os.getenv('ITERATIONS', '1000'))
BATCH_SIZE  = int(os.getenv('BATCH_SIZE',  '50'))

def connect_redis():
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT,
                    decode_responses=True, socket_connect_timeout=5)
    r.ping()
    print(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
    return r

def make_metric(i):
    return {
        "probe_id":        random.choice(["java-probe-us-east", "go-probe-us-west"]),
        "target_host":     random.choice(["8.8.8.8", "1.1.1.1", "208.67.222.222"]),
        "latency_ms":      random.uniform(5.0, 150.0),
        "timestamp_unix":  int(time.time()),
        "region":          random.choice(["us-east-1", "us-west-1"]),
        "probe_type":      random.choice(["java", "go"]),
        "sequence_number": i
    }

# ── Baseline: individual Redis SET per metric (no pipeline) ───────────────
def benchmark_direct_writes(r, iterations, batch_size):
    latencies = []
    for i in range(iterations):
        batch = [make_metric(i * batch_size + j) for j in range(batch_size)]
        start = time.perf_counter()
        for metric in batch:
            key = f"bench:direct:{metric['probe_id']}"
            r.set(key, json.dumps(metric))
            ts_key = f"bench:ts:direct:{metric['probe_id']}"
            r.lpush(ts_key, json.dumps(metric))
            r.ltrim(ts_key, 0, 999)
        elapsed = (time.perf_counter() - start) * 1000
        latencies.append(elapsed)
        if (i + 1) % 100 == 0:
            print(f"  Direct writes: {i+1}/{iterations} batches done")
    return latencies

# ── Optimized: Redis pipeline (batches all commands in one round trip) ────
def benchmark_pipeline_writes(r, iterations, batch_size):
    latencies = []
    for i in range(iterations):
        batch = [make_metric(i * batch_size + j) for j in range(batch_size)]
        start = time.perf_counter()
        pipe = r.pipeline()
        for metric in batch:
            key = f"bench:pipeline:{metric['probe_id']}"
            pipe.setex(key, 3600, json.dumps(metric))
            ts_key = f"bench:ts:pipeline:{metric['probe_id']}"
            pipe.lpush(ts_key, json.dumps(metric))
            pipe.ltrim(ts_key, 0, 999)
        pipe.execute()
        elapsed = (time.perf_counter() - start) * 1000
        latencies.append(elapsed)
        if (i + 1) % 100 == 0:
            print(f"  Pipeline writes: {i+1}/{iterations} batches done")
    return latencies

def compute_stats(latencies):
    arr = np.array(latencies)
    return {
        "mean":   float(np.mean(arr)),
        "median": float(np.median(arr)),
        "p50":    float(np.percentile(arr, 50)),
        "p95":    float(np.percentile(arr, 95)),
        "p99":    float(np.percentile(arr, 99)),
        "min":    float(np.min(arr)),
        "max":    float(np.max(arr)),
        "stdev":  float(np.std(arr))
    }

def print_report(direct_stats, pipeline_stats, iterations, batch_size):
    p50_reduction = ((direct_stats['p50'] - pipeline_stats['p50']) / direct_stats['p50']) * 100
    p95_reduction = ((direct_stats['p95'] - pipeline_stats['p95']) / direct_stats['p95']) * 100
    p99_reduction = ((direct_stats['p99'] - pipeline_stats['p99']) / direct_stats['p99']) * 100
    mean_reduction = ((direct_stats['mean'] - pipeline_stats['mean']) / direct_stats['mean']) * 100

    print("\n" + "═" * 60)
    print("  DistroProbe Benchmark Results")
    print("═" * 60)
    print(f"  Iterations : {iterations}")
    print(f"  Batch size : {batch_size} metrics/batch")
    print(f"  Total ops  : {iterations * batch_size:,} metric writes")
    print("─" * 60)
    print(f"  {'Metric':<12} {'Direct (ms)':>14} {'Pipeline (ms)':>14} {'Reduction':>10}")
    print("─" * 60)
    print(f"  {'p50':<12} {direct_stats['p50']:>14.3f} {pipeline_stats['p50']:>14.3f} {p50_reduction:>9.1f}%")
    print(f"  {'p95':<12} {direct_stats['p95']:>14.3f} {pipeline_stats['p95']:>14.3f} {p95_reduction:>9.1f}%")
    print(f"  {'p99':<12} {direct_stats['p99']:>14.3f} {pipeline_stats['p99']:>14.3f} {p99_reduction:>9.1f}%")
    print(f"  {'mean':<12} {direct_stats['mean']:>14.3f} {pipeline_stats['mean']:>14.3f} {mean_reduction:>9.1f}%")
    print(f"  {'min':<12} {direct_stats['min']:>14.3f} {pipeline_stats['min']:>14.3f}")
    print(f"  {'max':<12} {direct_stats['max']:>14.3f} {pipeline_stats['max']:>14.3f}")
    print("═" * 60)
    print(f"\n  p99 latency reduced by {p99_reduction:.1f}% using Redis pipeline caching")
    print(f"  p50 latency reduced by {p50_reduction:.1f}% using Redis pipeline caching")
    print()

    return {
        "p50_reduction_pct":  round(p50_reduction, 2),
        "p95_reduction_pct":  round(p95_reduction, 2),
        "p99_reduction_pct":  round(p99_reduction, 2),
        "mean_reduction_pct": round(mean_reduction, 2)
    }

def main():
    print("╔══════════════════════════════════════╗")
    print("║   DistroProbe Benchmark Harness      ║")
    print("╚══════════════════════════════════════╝\n")

    r = connect_redis()

    # Warm up Redis connection
    print("Warming up Redis connection...")
    for _ in range(10):
        r.set("bench:warmup", "1")
    r.delete("bench:warmup")
    print("Warmup complete.\n")

    print(f"Running {ITERATIONS} iterations with batch_size={BATCH_SIZE}...")
    print(f"Total metric writes per method: {ITERATIONS * BATCH_SIZE:,}\n")

    print("[ 1/2 ] Benchmarking direct Redis writes (no pipeline)...")
    direct_latencies = benchmark_direct_writes(r, ITERATIONS, BATCH_SIZE)
    direct_stats = compute_stats(direct_latencies)
    print("  Done.\n")

    print("[ 2/2 ] Benchmarking Redis pipeline writes...")
    pipeline_latencies = benchmark_pipeline_writes(r, ITERATIONS, BATCH_SIZE)
    pipeline_stats = compute_stats(pipeline_latencies)
    print("  Done.\n")

    reductions = print_report(direct_stats, pipeline_stats, ITERATIONS, BATCH_SIZE)

    # Save results to JSON for README and interview reference
    results = {
        "timestamp":     time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "iterations":    ITERATIONS,
        "batch_size":    BATCH_SIZE,
        "total_writes":  ITERATIONS * BATCH_SIZE,
        "direct":        direct_stats,
        "pipeline":      pipeline_stats,
        "reductions":    reductions
    }

    output_path = os.path.join(os.path.dirname(__file__), 'results.json')
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"  Results saved to benchmark/results.json")

    # Clean up benchmark keys
    for key in r.scan_iter("bench:*"):
        r.delete(key)

if __name__ == '__main__':
    main()
