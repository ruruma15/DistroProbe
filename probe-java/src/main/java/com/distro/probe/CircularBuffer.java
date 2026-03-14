package com.distro.probe;

import java.util.concurrent.atomic.AtomicInteger;

/**
 * Lock-free circular buffer using a pre-allocated array.
 * Avoids heap allocation at runtime = zero GC pressure.
 * This is the same pattern used in HFT (High Frequency Trading) systems.
 */
public class CircularBuffer {

    // Pre-allocated slots — memory is claimed once at startup, never again
    private final double[] buffer;
    private final int capacity;

    // Atomic counters for thread-safe head/tail without locks
    private final AtomicInteger writeIndex = new AtomicInteger(0);
    private final AtomicInteger size       = new AtomicInteger(0);

    public CircularBuffer(int capacity) {
        this.capacity = capacity;
        this.buffer   = new double[capacity]; // single allocation at startup
    }

    /**
     * Write a latency value into the buffer.
     * If full, overwrites the oldest entry (ring behavior).
     */
    public void write(double latencyMs) {
        int idx = writeIndex.getAndIncrement() % capacity;
        buffer[idx] = latencyMs;
        if (size.get() < capacity) {
            size.incrementAndGet();
        }
    }

    /**
     * Read the most recently written latency value.
     */
    public double readLatest() {
        int idx = (writeIndex.get() - 1 + capacity) % capacity;
        return buffer[idx];
    }

    /**
     * Drain all current values into a new array for batch gRPC streaming.
     */
    public double[] drainAll() {
        int count = size.get();
        double[] snapshot = new double[count];
        int startIdx = (writeIndex.get() - count + capacity * 2) % capacity;
        for (int i = 0; i < count; i++) {
            snapshot[i] = buffer[(startIdx + i) % capacity];
        }
        return snapshot;
    }

    public int size()     { return size.get(); }
    public int capacity() { return capacity;   }
}
