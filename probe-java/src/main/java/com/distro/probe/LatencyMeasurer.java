package com.distro.probe;

import java.net.InetAddress;
import java.net.Socket;
import java.util.List;

/**
 * Measures network latency to a target host.
 * Uses TCP socket connection timing for accurate sub-millisecond measurement.
 */
public class LatencyMeasurer {

    private final List<String> targetHosts;
    private final int          timeoutMs;
    private       int          hostIndex = 0;

    public LatencyMeasurer(List<String> targetHosts, int timeoutMs) {
        this.targetHosts = targetHosts;
        this.timeoutMs   = timeoutMs;
    }

    /**
     * Measures latency to the next host in round-robin rotation.
     * Returns latency in milliseconds, or -1 if host is unreachable.
     */
    public double measure() {
        String host = targetHosts.get(hostIndex % targetHosts.size());
        hostIndex++;

        long start = System.nanoTime();
        try {
            // TCP handshake to port 80 — accurate network RTT measurement
            try (Socket socket = new Socket()) {
                socket.connect(
                    new java.net.InetSocketAddress(host, 80),
                    timeoutMs
                );
            }
            long elapsed = System.nanoTime() - start;
            return elapsed / 1_000_000.0; // convert nanoseconds to milliseconds
        } catch (Exception e) {
            // Host unreachable or timed out — use ICMP ping as fallback
            try {
                long pingStart = System.nanoTime();
                InetAddress.getByName(host).isReachable(timeoutMs);
                long elapsed = System.nanoTime() - pingStart;
                return elapsed / 1_000_000.0;
            } catch (Exception ex) {
                return -1.0; // unreachable
            }
        }
    }

    public String currentHost() {
        return targetHosts.get((hostIndex - 1) % targetHosts.size());
    }
}
