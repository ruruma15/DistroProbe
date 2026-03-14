package main

import (
	"fmt"
	"os"
	"strconv"
	"time"
)

// ── Configuration from environment variables ──────────────────────────────
var (
	collectorHost  = getEnv("COLLECTOR_HOST",   "localhost")
	collectorPort  = getEnvInt("COLLECTOR_PORT", 50051)
	probeID        = getEnv("PROBE_ID",          "go-probe-us-west")
	region         = getEnv("REGION",            "us-west-1")
	bufferCapacity = getEnvInt("BUFFER_CAPACITY", 1024)
	flushInterval  = getEnvInt("FLUSH_INTERVAL",  50)
	measureDelayMs = getEnvInt("MEASURE_DELAY_MS", 100)
)

var targetHosts = []string{
	"8.8.4.4",       // Google DNS secondary
	"9.9.9.9",       // Quad9 DNS
	"1.0.0.1",       // Cloudflare secondary
}

func main() {
	fmt.Println("╔══════════════════════════════════════╗")
	fmt.Println("║      DistroProbe - Go Probe          ║")
	fmt.Println("╚══════════════════════════════════════╝")
	fmt.Printf("  Probe ID  : %s\n", probeID)
	fmt.Printf("  Region    : %s\n", region)
	fmt.Printf("  Collector : %s:%d\n", collectorHost, collectorPort)
	fmt.Printf("  Buffer    : %d slots\n", bufferCapacity)
	fmt.Printf("  Targets   : %v\n", targetHosts)
	fmt.Println("  Starting concurrent measurement loop...\n")

	// Initialize components
	buffer   := NewCircularBuffer(int64(bufferCapacity))
	measurer := NewConcurrentMeasurer(targetHosts, 3000)
	client, err := NewGrpcProbeClient(collectorHost, collectorPort, probeID, region)
	if err != nil {
		fmt.Printf("[Go Probe] Failed to connect to collector: %v\n", err)
		fmt.Println("[Go Probe] Will retry on first flush...")
	}
	if client != nil {
		defer client.Close()
	}

	measurementCount := 0

	// ── Main measurement loop ──────────────────────────────────────────────
	for {
		// Measure ALL hosts concurrently in parallel goroutines
		results := measurer.MeasureAll()

		for _, result := range results {
			if result.Success {
				buffer.Write(result.LatencyMs)
				measurementCount++
				fmt.Printf("[Go Probe] #%d | host=%-15s | latency=%.2f ms | buffer=%d/%d\n",
					measurementCount, result.Host, result.LatencyMs,
					buffer.Size(), buffer.Capacity())
			} else {
				fmt.Printf("[Go Probe] host=%-15s | UNREACHABLE\n", result.Host)
			}
		}

		// Flush to collector every flushInterval measurements
		if measurementCount > 0 && measurementCount%flushInterval == 0 {
			fmt.Println("[Go Probe] Flushing buffer to collector...")
			if client == nil {
				// Retry connection
				client, err = NewGrpcProbeClient(collectorHost, collectorPort, probeID, region)
				if err != nil {
					fmt.Printf("[Go Probe] Reconnect failed: %v\n", err)
					continue
				}
			}
			stored, err := client.StreamMetrics(results)
			if err != nil {
				fmt.Printf("[Go Probe] Stream error: %v\n", err)
			} else {
				fmt.Printf("[Go Probe] Flushed → collector stored %d\n\n", stored)
			}
		}

		time.Sleep(time.Duration(measureDelayMs) * time.Millisecond)
	}
}

func getEnv(key, defaultVal string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return defaultVal
}

func getEnvInt(key string, defaultVal int) int {
	if val := os.Getenv(key); val != "" {
		if i, err := strconv.Atoi(val); err == nil {
			return i
		}
	}
	return defaultVal
}
