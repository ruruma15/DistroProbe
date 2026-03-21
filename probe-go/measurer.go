package main

import (
	"fmt"
	"net"
	"sync"
	"time"
)

// one latency reading
type MeasurementResult struct {
	Host      string
	LatencyMs float64
	Success   bool
}

// fires all host measurements at once using goroutines
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

// measure all hosts at the same time, collect when done
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

// TCP connect to port 80, return elapsed time
func (m *ConcurrentMeasurer) measureHost(host string) MeasurementResult {
	address := fmt.Sprintf("%s:80", host)
	start := time.Now()

	conn, err := net.DialTimeout("tcp", address, m.timeoutMs)
	if err != nil {
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
