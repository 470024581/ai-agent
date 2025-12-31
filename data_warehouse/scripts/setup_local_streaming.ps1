# Setup Local Streaming Environment
# 配置本地流计算环境依赖

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Setting up Local Streaming Environment" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Check Python version
Write-Host "Checking Python version..." -ForegroundColor Yellow
python --version
Write-Host ""

# Install/Upgrade dependencies
Write-Host "Installing/Upgrading Python dependencies..." -ForegroundColor Yellow
pip install --upgrade `
    pyspark==3.5.0 `
    delta-spark==3.1.0 `
    databricks-sql-connector==3.3.0 `
    python-dotenv==1.0.0 `
    pandas==2.2.0

Write-Host ""
Write-Host "✅ Dependencies installed successfully!" -ForegroundColor Green
Write-Host ""

# Verify installations
Write-Host "Verifying installations..." -ForegroundColor Yellow
python -c "import pyspark; print(f'PySpark: {pyspark.__version__}')"
python -c "import delta; print(f'Delta Lake: {delta.__version__}')"
python -c "from databricks import sql; print('Databricks SQL Connector: OK')"
Write-Host ""

# Create checkpoint directories
Write-Host "Creating checkpoint directories..." -ForegroundColor Yellow
$checkpointDirs = @(
    ".\checkpoints\bronze_streaming",
    ".\checkpoints\silver_streaming\users",
    ".\checkpoints\silver_streaming\routes",
    ".\checkpoints\silver_streaming\stations",
    ".\checkpoints\silver_streaming\topups",
    ".\checkpoints\silver_streaming\transactions",
    ".\checkpoints\gold_streaming\daily_active_users",
    ".\checkpoints\gold_streaming\station_activity",
    ".\checkpoints\gold_streaming\route_usage",
    ".\checkpoints\gold_streaming\topup_summary",
    ".\checkpoints\gold_streaming\transaction_summary"
)

foreach ($dir in $checkpointDirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "  Created: $dir" -ForegroundColor Gray
    }
}
Write-Host ""

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "✅ Setup Complete!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Ensure Kafka is running with data in topic: transport_dw.cdc_events" -ForegroundColor White
Write-Host "2. Configure Databricks credentials in .env file:" -ForegroundColor White
Write-Host "   - DATABRICKS_SERVER_HOSTNAME" -ForegroundColor Gray
Write-Host "   - DATABRICKS_HTTP_PATH" -ForegroundColor Gray
Write-Host "   - DATABRICKS_TOKEN" -ForegroundColor Gray
Write-Host "3. Run Bronze streaming (if not already running):" -ForegroundColor White
Write-Host "   python bronze_streaming.py" -ForegroundColor Gray
Write-Host "4. Run Silver streaming:" -ForegroundColor White
Write-Host "   python silver_streaming.py" -ForegroundColor Gray
Write-Host "5. Run Gold streaming:" -ForegroundColor White
Write-Host "   python gold_streaming.py" -ForegroundColor Gray
Write-Host ""

