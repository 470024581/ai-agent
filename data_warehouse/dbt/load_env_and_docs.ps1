# PowerShell script to load .env file and generate dbt documentation
# This script loads environment variables from ../.env file

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "dbt Documentation Generator" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Change to dbt directory
Set-Location $PSScriptRoot

# Path to .env file (in parent directory)
$envFile = Join-Path (Split-Path $PSScriptRoot -Parent) ".env"

if (-not (Test-Path $envFile)) {
    Write-Host "[ERROR] .env file not found at: $envFile" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please create .env file with the following variables:" -ForegroundColor Yellow
    Write-Host "  DATABRICKS_SERVER_HOSTNAME=your-hostname" -ForegroundColor Gray
    Write-Host "  DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/your-warehouse-id" -ForegroundColor Gray
    Write-Host "  DATABRICKS_TOKEN=your-token" -ForegroundColor Gray
    Write-Host ""
    exit 1
}

Write-Host "[INFO] Loading environment variables from .env file..." -ForegroundColor Green

# Load environment variables from .env file
$loadedVars = @()
Get-Content $envFile | ForEach-Object {
    # Skip comments and empty lines
    if ($_ -match '^\s*#') { return }
    if ($_ -match '^\s*$') { return }
    
    # Parse KEY=VALUE format
    if ($_ -match '^\s*([^#][^=]*?)\s*=\s*(.*?)\s*$') {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim()
        
        # Remove quotes if present
        if ($value -match '^["''](.*)["'']$') {
            $value = $matches[1]
        }
        
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
        $loadedVars += $name
        Write-Host "  Loaded: $name" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "[INFO] Loaded $($loadedVars.Count) environment variables" -ForegroundColor Green
Write-Host ""

# Check required variables
$requiredVars = @("DATABRICKS_SERVER_HOSTNAME", "DATABRICKS_HTTP_PATH", "DATABRICKS_TOKEN")
$missingVars = @()

foreach ($var in $requiredVars) {
    $value = [Environment]::GetEnvironmentVariable($var, "Process")
    if (-not $value -or $value -eq "") {
        $missingVars += $var
    } else {
        Write-Host "[OK] $var is set" -ForegroundColor Green
    }
}

if ($missingVars.Count -gt 0) {
    Write-Host ""
    Write-Host "[ERROR] Missing required environment variables:" -ForegroundColor Red
    foreach ($var in $missingVars) {
        Write-Host "  - $var" -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "Please add these variables to your .env file:" -ForegroundColor Yellow
    Write-Host "  $envFile" -ForegroundColor Gray
    Write-Host ""
    exit 1
}

Write-Host ""
Write-Host "[1/3] Installing package dependencies..." -ForegroundColor Green
Write-Host ""

# Install package dependencies
dbt deps --profiles-dir .

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[ERROR] Package installation failed!" -ForegroundColor Red
    Write-Host ""
    exit 1
}

Write-Host ""
Write-Host "[SUCCESS] Package dependencies installed!" -ForegroundColor Green
Write-Host ""

Write-Host "[2/3] Generating documentation..." -ForegroundColor Green
Write-Host ""

# Generate documentation
dbt docs generate --profiles-dir .

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[ERROR] Documentation generation failed!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "  1. Check dbt_project.yml syntax" -ForegroundColor Gray
    Write-Host "  2. Verify model files are valid SQL" -ForegroundColor Gray
    Write-Host "  3. Ensure Databricks connection is accessible" -ForegroundColor Gray
    exit 1
}

Write-Host ""
Write-Host "[SUCCESS] Documentation generated successfully!" -ForegroundColor Green
Write-Host ""

Write-Host "[3/3] Starting documentation server..." -ForegroundColor Green
Write-Host ""
Write-Host "Documentation will be available at: http://localhost:8080" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Start the documentation server
dbt docs serve --profiles-dir .

