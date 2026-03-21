package com.distro.probe;

import com.distro.proto.CollectorAck;
import com.distro.proto.LatencyMetric;
import com.distro.proto.TelemetryServiceGrpc;
import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import io.grpc.stub.StreamObserver;

import java.time.Instant;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

// Streams latency metrics to the collector over gRPC.
// Opens one stream per batch, sends all metrics, waits for ack.
public class GrpcProbeClient {

    private final ManagedChannel                          channel;
    private final TelemetryServiceGrpc.TelemetryServiceStub stub;
    private final String                                  probeId;
    private final String                                  region;
    private final AtomicInteger                           sequenceNumber = new AtomicInteger(0);

    public GrpcProbeClient(String collectorHost, int collectorPort,
                           String probeId, String region) {
        this.channel = ManagedChannelBuilder
                .forAddress(collectorHost, collectorPort)
                .usePlaintext() // no TLS in dev
                .build();
        this.stub    = TelemetryServiceGrpc.newStub(channel);
        this.probeId = probeId;
        this.region  = region;
    }

    public int streamMetrics(double[] latencies, String targetHost) throws InterruptedException {
        CountDownLatch latch    = new CountDownLatch(1);
        int[]          stored   = {0};
        boolean[]      success  = {false};

        StreamObserver<CollectorAck> responseObserver = new StreamObserver<>() {
            @Override
            public void onNext(CollectorAck ack) {
                stored[0]  = ack.getMetricsStored();
                success[0] = ack.getReceived();
                System.out.printf("[Java Probe] Collector ACK: %s | stored=%d%n",
                        ack.getMessage(), ack.getMetricsStored());
            }
            @Override
            public void onError(Throwable t) {
                System.err.println("[Java Probe] Stream error: " + t.getMessage());
                latch.countDown();
            }
            @Override
            public void onCompleted() {
                latch.countDown();
            }
        };

        StreamObserver<LatencyMetric> requestObserver = stub.streamMetrics(responseObserver);

        try {
            for (double latency : latencies) {
                if (latency < 0) continue;
                LatencyMetric metric = LatencyMetric.newBuilder()
                        .setProbeId(probeId)
                        .setTargetHost(targetHost)
                        .setLatencyMs(latency)
                        .setTimestampUnix(Instant.now().getEpochSecond())
                        .setRegion(region)
                        .setProbeType("java")
                        .setSequenceNumber(sequenceNumber.getAndIncrement())
                        .build();
                requestObserver.onNext(metric);
            }
            requestObserver.onCompleted();
        } catch (Exception e) {
            requestObserver.onError(e);
            throw e;
        }

        latch.await(10, TimeUnit.SECONDS);
        return stored[0];
    }

    public void shutdown() throws InterruptedException {
        channel.shutdown().awaitTermination(5, TimeUnit.SECONDS);
    }
}
