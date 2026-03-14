package main

import (
	"context"
	"fmt"
	"time"

	pb "github.com/ruruma15/distro-probe/probe-go/proto"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// GrpcProbeClient streams metrics to the Python collector.
type GrpcProbeClient struct {
	conn          *grpc.ClientConn
	client        pb.TelemetryServiceClient
	probeID       string
	region        string
	sequenceNum   int32
}

func NewGrpcProbeClient(host string, port int, probeID, region string) (*GrpcProbeClient, error) {
	addr := fmt.Sprintf("%s:%d", host, port)
	conn, err := grpc.NewClient(addr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return nil, fmt.Errorf("failed to connect to collector: %w", err)
	}
	return &GrpcProbeClient{
		conn:    conn,
		client:  pb.NewTelemetryServiceClient(conn),
		probeID: probeID,
		region:  region,
	}, nil
}

// StreamMetrics sends a batch of latency readings to the collector.
func (g *GrpcProbeClient) StreamMetrics(results []MeasurementResult) (int32, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	stream, err := g.client.StreamMetrics(ctx)
	if err != nil {
		return 0, fmt.Errorf("failed to open stream: %w", err)
	}

	sent := 0
	for _, result := range results {
		if !result.Success || result.LatencyMs < 0 {
			continue
		}
		metric := &pb.LatencyMetric{
			ProbeId:        g.probeID,
			TargetHost:     result.Host,
			LatencyMs:      result.LatencyMs,
			TimestampUnix:  time.Now().Unix(),
			Region:         g.region,
			ProbeType:      "go",
			SequenceNumber: g.sequenceNum,
		}
		g.sequenceNum++
		if err := stream.Send(metric); err != nil {
			return 0, fmt.Errorf("failed to send metric: %w", err)
		}
		sent++
	}

	ack, err := stream.CloseAndRecv()
	if err != nil {
		return 0, fmt.Errorf("failed to receive ack: %w", err)
	}

	fmt.Printf("[Go Probe] Collector ACK: %s | stored=%d\n", ack.Message, ack.MetricsStored)
	return ack.MetricsStored, nil
}

func (g *GrpcProbeClient) Close() error {
	return g.conn.Close()
}
