FROM maven:3.9-eclipse-temurin-17 AS builder
WORKDIR /app
COPY pom.xml .
COPY src ./src
COPY proto ./proto
RUN mvn generate-sources package -q -DskipTests

FROM eclipse-temurin:17-jre-jammy
WORKDIR /app
COPY --from=builder /app/target/probe-java-1.0-SNAPSHOT.jar app.jar
ENV COLLECTOR_HOST=collector
ENV COLLECTOR_PORT=50051
ENV PROBE_ID=java-probe-us-east
ENV REGION=us-east-1
ENV BUFFER_CAPACITY=1024
ENV FLUSH_INTERVAL=50
ENV MEASURE_DELAY_MS=100
ENTRYPOINT ["java", "-jar", "app.jar"]
