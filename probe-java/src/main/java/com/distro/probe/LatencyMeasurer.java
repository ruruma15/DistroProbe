package com.distro.probe;

import java.net.InetAddress;
import java.net.Socket;
import java.util.List;

// Times TCP connections to target hosts.
// Rotates through hosts round-robin.
public class LatencyMeasurer {

    private final List<String> targetHosts;
    private final int          timeoutMs;
    private       int          hostIndex = 0;

    public LatencyMeasurer(List<String> targetHosts, int timeoutMs) {
        this.targetHosts = targetHosts;
        this.timeoutMs   = timeoutMs;
    }

    // returns ms, -1 if unreachable
    public double measure() {
        String host = targetHosts.get(hostIndex % targetHosts.size());
        hostIndex++;

        long start = System.nanoTime();
        try {
            // TCP connect to port 80, time the handshake
            try (Socket socket = new Socket()) {
                socket.connect(
                    new java.net.InetSocketAddress(host, 80),
                    timeoutMs
                );
            }
            long elapsed = System.nanoTime() - start;
            return elapsed / 1_000_000.0; // ns -> ms
        } catch (Exception e) {
            // port 80 blocked, try ICMP fallback
            try {
                long pingStart = System.nanoTime();
                InetAddress.getByName(host).isReachable(timeoutMs);
                long elapsed = System.nanoTime() - pingStart;
                return elapsed / 1_000_000.0;
            } catch (Exception ex) {
                return -1.0;
            }
        }
    }

    public String currentHost() {
        return targetHosts.get((hostIndex - 1) % targetHosts.size());
    }
}
