package com.distro.probe;

import java.util.Arrays;
import java.util.List;

/**
 * DistroProbe - Java Probe Entry Point
 *
 * Flow:
 *   1. Measure latency → write into CircularBuffer
 *   2. Every FLUSH_INTERVAL measurements → drain buffer → stream via gRPC
 *   3. Repeat forever
 */
public class ProbeMain {

    // ── Configuration (overridable via environment variables) ──────────────
    private static final String COLLECTOR_HOST  = getEnv("COLLECTOR_HOST",  "localhost");
    private static final int    COLLECTOR_PORT  = Integer.parseInt(getEnv("COLLECTOR_PORT", "50051"));
    private static final String PROBE_ID        = getEnv("PROBE_ID",        "java-probe-us-east");
    private static final String REGION          = getEnv("REGION",          "us-east-1");
    private static final int    BUFFER_CAPACITY = Integer.parseInt(getEnv("BUFFER_CAPACITY", "1024"));
    private static final int    FLUSH_INTERVAL  = Integer.parseInt(getEnv("FLUSH_INTERVAL",  "50"));
    private static final int    MEASURE_DELAY_MS= Integer.parseInt(getEnv("MEASURE_DELAY_MS","100"));

    // ── Target hosts to measure latency against ────────────────────────────
    private static final List<String> TARGET_HOSTS = Arrays.asList(
        "8.8.8.8",        // Google DNS
        "1.1.1.1",        // Cloudflare DNS
        "208.67.222.222"  // OpenDNS
    );

    public static void main(String[] args) throws Exception {
        System.out.println("╔══════════════════════════════════════╗");
        System.out.println("║     DistroProbe - Java Probe         ║");
        System.out.println("╚══════════════════════════════════════╝");
        System.out.printf("  Probe ID  : %s%n", PROBE_ID);
        System.out.printf("  Region    : %s%n", REGION);
        System.out.printf("  Collector : %s:%d%n", COLLECTOR_HOST, COLLECTOR_PORT);
        System.out.printf("  Buffer    : %d slots%n", BUFFER_CAPACITY);
        System.out.printf("  Targets   : %s%n", TARGET_HOSTS);
        System.out.println("  Starting measurement loop...\n");

        // Initialize core components
        CircularBuffer  buffer   = new CircularBuffer(BUFFER_CAPACITY);
        LatencyMeasurer measurer = new LatencyMeasurer(TARGET_HOSTS, 3000);
        GrpcProbeClient client   = new GrpcProbeClient(
                COLLECTOR_HOST, COLLECTOR_PORT, PROBE_ID, REGION);

        // Add shutdown hook for clean exit
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            try {
                client.shutdown();
                System.out.println("\n[Java Probe] Shutdown complete.");
            } catch (Exception e) {
                System.err.println("[Java Probe] Shutdown error: " + e.getMessage());
            }
        }));

        int measurementCount = 0;

        // ── Main measurement loop ──────────────────────────────────────────
        while (true) {
            // 1. Measure latency
            double latency = measurer.measure();
            String host    = measurer.currentHost();

            if (latency > 0) {
                // 2. Write into circular buffer (zero allocation)
                buffer.write(latency);
                measurementCount++;
                System.out.printf("[Java Probe] #%d | host=%-15s | latency=%.2f ms | buffer=%d/%d%n",
                        measurementCount, host, latency, buffer.size(), buffer.capacity());
            } else {
                System.out.printf("[Java Probe] #%d | host=%-15s | UNREACHABLE%n",
                        measurementCount, host);
            }

            // 3. Flush buffer to collector every FLUSH_INTERVAL measurements
            if (measurementCount > 0 && measurementCount % FLUSH_INTERVAL == 0) {
                System.out.println("[Java Probe] Flushing buffer to collector...");
                double[] batch = buffer.drainAll();
                try {
                    int stored = client.streamMetrics(batch, host);
                    System.out.printf("[Java Probe] Flushed %d metrics → collector stored %d%n%n",
                            batch.length, stored);
                } catch (Exception e) {
                    System.err.println("[Java Probe] Failed to stream: " + e.getMessage());
                    System.err.println("[Java Probe] Will retry on next flush.");
                }
            }

            // 4. Small delay between measurements
            Thread.sleep(MEASURE_DELAY_MS);
        }
    }

    private static String getEnv(String key, String defaultValue) {
        String val = System.getenv(key);
        return (val != null && !val.isEmpty()) ? val : defaultValue;
    }
}
