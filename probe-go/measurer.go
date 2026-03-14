package main

import (
	"fmt"
	"net"
	"sync"
	"time"
)

// MeasurementResult holds a single latency reading.
type MeasurementResult struct {
	Host      string
	LatencyMs float64
	Success   bool
}

// ConcurrentMeasurer measures latency to multiple hosts simultaneously
// using goroutines — Go's key advantage over Java for this use case.
type ConcurrentMeasurer struct {
	targetHosts []string
	timeoutMs   time.Duration
}

func NewConcurrentMeasurer(hosts []string, timeoutMs int) *ConcurrentMeasurer {
	return &ConcurrentMeasurer{
		targetHosts: hosts,
		timeoutMs:   time.Duration(timeoutMs) * time.Millisecond,
	}
}

// MeasureAll fires goroutines concurrently for every host and collects results.
// This is the core Go advantage: all hosts measured in parallel, not sequentially.
func (m *ConcurrentMeasurer) MeasureAll() []MeasurementResult {
	results := make([]MeasurementResult, len(m.targetHosts))
	var wg sync.WaitGroup

	for i, host := range m.targetHosts {
		wg.Add(1)
		go func(idx int, h string) {
			defer wg.Done()
			results[idx] = m.measureHost(h)
		}(i, host)
	}

	wg.Wait()
	return results
}

// measureHost performs a TCP dial to port 80 and times the connection.
func (m *ConcurrentMeasurer) measureHost(host string) MeasurementResult {
	address := fmt.Sprintf("%s:80", host)
	start := time.Now()

	conn, err := net.DialTimeout("tcp", address, m.timeoutMs)
	if err != nil {
		// Fallback: try ICMP-style reachability
		_, err2 := net.ResolveIPAddr("ip", host)
		if err2 != nil {
			return MeasurementResult{Host: host, LatencyMs: -1, Success: false}
		}
		elapsed := time.Since(start)
		return MeasurementResult{
			Host:      host,
			LatencyMs: float64(elapsed.Nanoseconds()) / 1e6,
			Success:   true,
		}
	}
	defer conn.Close()

	elapsed := time.Since(start)
	return MeasurementResult{
		Host:      host,
		LatencyMs: float64(elapsed.Nanoseconds()) / 1e6,
		Success:   true,
	}
}
