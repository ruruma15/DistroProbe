FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN go build -o probe-go .

FROM alpine:latest
WORKDIR /app
COPY --from=builder /app/probe-go .
ENV COLLECTOR_HOST=collector
ENV COLLECTOR_PORT=50051
ENV PROBE_ID=go-probe-us-west
ENV REGION=us-west-1
ENV BUFFER_CAPACITY=1024
ENV FLUSH_INTERVAL=50
ENV MEASURE_DELAY_MS=100
ENTRYPOINT ["./probe-go"]
