# PowerShell script to register Debezium connector
# 注册 Debezium connector 的 PowerShell 脚本

$CONNECTOR_NAME = "postgres-transport-cdc"
$CONNECT_URL = "http://localhost:8083"
$CONFIG_FILE = "..\debezium\postgres.json"

Write-Host "Registering Debezium connector: $CONNECTOR_NAME" -ForegroundColor Green

# Check if connector exists
try {
    $response = Invoke-WebRequest -Uri "$CONNECT_URL/connectors/$CONNECTOR_NAME" -Method Get -ErrorAction SilentlyContinue
    if ($response.StatusCode -eq 200) {
        Write-Host "Connector already exists. Updating..." -ForegroundColor Yellow
        $body = Get-Content $CONFIG_FILE -Raw
        $response = Invoke-RestMethod -Uri "$CONNECT_URL/connectors/$CONNECTOR_NAME/config" -Method Put -Body $body -ContentType "application/json"
        Write-Host "Connector updated successfully!" -ForegroundColor Green
        $response | ConvertTo-Json -Depth 10
    }
} catch {
    Write-Host "Creating new connector..." -ForegroundColor Yellow
    $body = Get-Content $CONFIG_FILE -Raw
    $response = Invoke-RestMethod -Uri "$CONNECT_URL/connectors" -Method Post -Body $body -ContentType "application/json"
    Write-Host "Connector created successfully!" -ForegroundColor Green
    $response | ConvertTo-Json -Depth 10
}

Write-Host ""
Write-Host "Connector status:" -ForegroundColor Cyan
try {
    $status = Invoke-RestMethod -Uri "$CONNECT_URL/connectors/$CONNECTOR_NAME/status" -Method Get
    $status | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Error getting connector status: $_" -ForegroundColor Red
}


