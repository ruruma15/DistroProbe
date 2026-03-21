package com.distro.probe;

import java.util.Arrays;
import java.util.List;

// measure -> buffer -> flush to collector, repeat
public class ProbeMain {

    // config — all overridable via env vars
    private static final String COLLECTOR_HOST  = getEnv("COLLECTOR_HOST",  "localhost");
    private static final int    COLLECTOR_PORT  = Integer.parseInt(getEnv("COLLECTOR_PORT", "50051"));
    private static final String PROBE_ID        = getEnv("PROBE_ID",        "java-probe-us-east");
    private static final String REGION          = getEnv("REGION",          "us-east-1");
    private static final int    BUFFER_CAPACITY = Integer.parseInt(getEnv("BUFFER_CAPACITY", "1024"));
    private static final int    FLUSH_INTERVAL  = Integer.parseInt(getEnv("FLUSH_INTERVAL",  "50"));
    private static final int    MEASURE_DELAY_MS= Integer.parseInt(getEnv("MEASURE_DELAY_MS","100"));

    // hosts to ping
    private static final List<String> TARGET_HOSTS = Arrays.asList(
        "8.8.8.8",
        "1.1.1.1",
        "208.67.222.222"
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

        CircularBuffer  buffer   = new CircularBuffer(BUFFER_CAPACITY);
        LatencyMeasurer measurer = new LatencyMeasurer(TARGET_HOSTS, 3000);
        GrpcProbeClient client   = new GrpcProbeClient(
                COLLECTOR_HOST, COLLECTOR_PORT, PROBE_ID, REGION);

        // clean shutdown on ctrl+c
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            try {
                client.shutdown();
                System.out.println("\n[Java Probe] Shutdown complete.");
            } catch (Exception e) {
                System.err.println("[Java Probe] Shutdown error: " + e.getMessage());
            }
        }));

        int measurementCount = 0;

        // main loop
        while (true) {
            // measure
            double latency = measurer.measure();
            String host    = measurer.currentHost();

            if (latency > 0) {
                // write to buffer
                buffer.write(latency);
                measurementCount++;
                System.out.printf("[Java Probe] #%d | host=%-15s | latency=%.2f ms | buffer=%d/%d%n",
                        measurementCount, host, latency, buffer.size(), buffer.capacity());
            } else {
                System.out.printf("[Java Probe] #%d | host=%-15s | UNREACHABLE%n",
                        measurementCount, host);
            }

            // flush when batch is ready
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

            // pace the loop
            Thread.sleep(MEASURE_DELAY_MS);
        }
    }

    private static String getEnv(String key, String defaultValue) {
        String val = System.getenv(key);
        return (val != null && !val.isEmpty()) ? val : defaultValue;
    }
}
