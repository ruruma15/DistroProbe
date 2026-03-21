package com.distro.probe;

import java.util.concurrent.atomic.AtomicInteger;

// Pre-allocated ring buffer. Fixed size array claimed at startup,
// never reallocated. Keeps GC out of the hot path.
public class CircularBuffer {

    // claim memory once, never again
    private final double[] buffer;
    private final int capacity;

    // atomic so multiple threads can write without locking
    private final AtomicInteger writeIndex = new AtomicInteger(0);
    private final AtomicInteger size       = new AtomicInteger(0);

    public CircularBuffer(int capacity) {
        this.capacity = capacity;
        this.buffer   = new double[capacity];
    }

    // write next value, wrap around if full
    public void write(double latencyMs) {
        int idx = writeIndex.getAndIncrement() % capacity;
        buffer[idx] = latencyMs;
        if (size.get() < capacity) {
            size.incrementAndGet();
        }
    }

    // latest value written
    public double readLatest() {
        int idx = (writeIndex.get() - 1 + capacity) % capacity;
        return buffer[idx];
    }

    // snapshot everything currently in the buffer
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
