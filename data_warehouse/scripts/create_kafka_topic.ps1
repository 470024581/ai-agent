# Create Kafka topic for unified CDC events
# 创建统一的CDC事件Kafka topic

$KAFKA_CONTAINER = "kafka"
$TOPIC_NAME = "transport_dw.cdc_events"
$PARTITIONS = 5
$REPLICATION_FACTOR = 1

Write-Host "============================================================"
Write-Host "Creating Kafka Topic for Unified CDC Events"
Write-Host "创建统一的CDC事件Kafka Topic"
Write-Host "============================================================"
Write-Host ""
Write-Host "Topic: $TOPIC_NAME"
Write-Host "Partitions: $PARTITIONS"
Write-Host "Replication Factor: $REPLICATION_FACTOR"
Write-Host ""

# Check if topic already exists
Write-Host "Checking if topic exists..."
$existingTopics = docker exec $KAFKA_CONTAINER kafka-topics --list --bootstrap-server localhost:9092 2>&1

if ($existingTopics -match $TOPIC_NAME) {
    Write-Host "⚠ Topic '$TOPIC_NAME' already exists" -ForegroundColor Yellow
    Write-Host "Deleting existing topic..."
    docker exec $KAFKA_CONTAINER kafka-topics --delete --bootstrap-server localhost:9092 --topic $TOPIC_NAME 2>&1 | Out-Null
    Start-Sleep -Seconds 2
}

# Create topic
Write-Host "Creating topic..."
$result = docker exec $KAFKA_CONTAINER kafka-topics --create `
    --bootstrap-server localhost:9092 `
    --topic $TOPIC_NAME `
    --partitions $PARTITIONS `
    --replication-factor $REPLICATION_FACTOR `
    --config retention.ms=604800000 `
    --config cleanup.policy=delete 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Topic created successfully!" -ForegroundColor Green
} else {
    if ($result -match "already exists") {
        Write-Host "⚠ Topic already exists (may have been created by another process)" -ForegroundColor Yellow
    } else {
        Write-Host "✗ Error creating topic: $result" -ForegroundColor Red
        exit 1
    }
}

# Verify topic creation
Write-Host ""
Write-Host "Verifying topic..."
$topicInfo = docker exec $KAFKA_CONTAINER kafka-topics --describe --bootstrap-server localhost:9092 --topic $TOPIC_NAME 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Topic details:" -ForegroundColor Green
    Write-Host $topicInfo
} else {
    Write-Host "⚠ Could not verify topic: $topicInfo" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "============================================================"
Write-Host "Topic creation completed"
Write-Host "============================================================"

