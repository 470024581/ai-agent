# Reset Debezium connector to trigger snapshot
# 重置 Debezium connector 以触发 snapshot

$CONNECTOR_NAME = "postgres-transport-cdc"
$CONNECT_URL = "http://localhost:8083"
$SLOT_NAME = "debezium_transport_slot"

Write-Host "============================================================"
Write-Host "Resetting Debezium Connector to Trigger Snapshot"
Write-Host "重置 Debezium Connector 以触发 Snapshot"
Write-Host "============================================================"
Write-Host ""

# Step 1: Stop and delete connector
Write-Host "Step 1: Stopping and deleting connector..."
try {
    Invoke-RestMethod -Uri "$CONNECT_URL/connectors/$CONNECTOR_NAME" -Method Delete -ErrorAction Stop
    Write-Host "✓ Connector deleted"
} catch {
    if ($_.Exception.Response.StatusCode -eq 404) {
        Write-Host "⚠ Connector not found (already deleted)"
    } else {
        Write-Host "✗ Error deleting connector: $($_.Exception.Message)"
        exit 1
    }
}

# Step 2: Delete replication slot in PostgreSQL
Write-Host ""
Write-Host "Step 2: Deleting replication slot in PostgreSQL..."
Write-Host "  Slot name: $SLOT_NAME"
Write-Host ""
Write-Host "  Executing: SELECT pg_drop_replication_slot('$SLOT_NAME');"

$dropSlotSQL = "SELECT pg_drop_replication_slot('$SLOT_NAME');"
$result = docker exec postgres psql -U dbuser -d transport_dw -c $dropSlotSQL 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Replication slot deleted"
} else {
    if ($result -match "does not exist") {
        Write-Host "⚠ Replication slot not found (already deleted)"
    } else {
        Write-Host "⚠ Error deleting replication slot: $result"
        Write-Host "  You may need to delete it manually:"
        Write-Host "    docker exec -it postgres psql -U dbuser -d transport_dw -c `"SELECT pg_drop_replication_slot('$SLOT_NAME');`""
    }
}

# Step 3: Wait a bit for cleanup
Write-Host ""
Write-Host "Step 3: Waiting 5 seconds for cleanup..."
Start-Sleep -Seconds 5

# Step 4: Re-register connector
Write-Host ""
Write-Host "Step 4: Re-registering connector (this will trigger snapshot)..."
Write-Host ""

$CONFIG_FILE = "debezium/postgres.json"
$configJson = Get-Content -Raw -Path (Join-Path (Split-Path $MyInvocation.MyCommand.Path) "..\$CONFIG_FILE")

try {
    $response = Invoke-RestMethod -Uri "$CONNECT_URL/connectors" -Method Post -Body $configJson -ContentType "application/json"
    Write-Host "✓ Connector registered successfully"
    Write-Host ""
    Write-Host "Connector status:"
    Start-Sleep -Seconds 2
    $status = Invoke-RestMethod -Uri "$CONNECT_URL/connectors/$CONNECTOR_NAME/status" -Method Get
    $status | ConvertTo-Json -Depth 10
} catch {
    Write-Host "✗ Error registering connector: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "  Response: $responseBody"
    }
    exit 1
}

Write-Host ""
Write-Host "============================================================"
Write-Host "✓ Reset complete!"
Write-Host ""
Write-Host "The connector will now:"
Write-Host "  1. Create a new replication slot"
Write-Host "  2. Execute snapshot (copy all existing data)"
Write-Host "  3. Continue with CDC (capture new changes)"
Write-Host ""
Write-Host "Check Kafka topics to verify snapshot data:"
Write-Host "  docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic transport_dw.public.users --from-beginning --max-messages 1"
Write-Host "============================================================"

