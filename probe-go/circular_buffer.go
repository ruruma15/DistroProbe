package main

import (
	"sync/atomic"
	"unsafe"
)

// CircularBuffer is a lock-free ring buffer using atomic operations.
// Pre-allocated at startup — zero heap allocation during measurement loop.
type CircularBuffer struct {
	buffer     []float64
	capacity   int64
	writeIndex atomic.Int64
	size       atomic.Int64
}

func NewCircularBuffer(capacity int64) *CircularBuffer {
	return &CircularBuffer{
		buffer:   make([]float64, capacity), // single allocation at startup
		capacity: capacity,
	}
}

// Write stores a latency value. Overwrites oldest entry when full.
func (cb *CircularBuffer) Write(latencyMs float64) {
	idx := cb.writeIndex.Add(1) - 1
	// Direct memory write using unsafe for zero-allocation path
	*(*float64)(unsafe.Pointer(
		uintptr(unsafe.Pointer(&cb.buffer[0])) +
			uintptr(idx%cb.capacity)*8,
	)) = latencyMs

	if cb.size.Load() < cb.capacity {
		cb.size.Add(1)
	}
}

// ReadLatest returns the most recently written value.
func (cb *CircularBuffer) ReadLatest() float64 {
	idx := (cb.writeIndex.Load() - 1 + cb.capacity) % cb.capacity
	return cb.buffer[idx]
}

// DrainAll returns a snapshot of all current values.
func (cb *CircularBuffer) DrainAll() []float64 {
	count := cb.size.Load()
	if count == 0 {
		return []float64{}
	}
	snapshot := make([]float64, count)
	startIdx := (cb.writeIndex.Load() - count + cb.capacity*2) % cb.capacity
	for i := int64(0); i < count; i++ {
		snapshot[i] = cb.buffer[(startIdx+i)%cb.capacity]
	}
	return snapshot
}

func (cb *CircularBuffer) Size() int64     { return cb.size.Load() }
func (cb *CircularBuffer) Capacity() int64 { return cb.capacity }
