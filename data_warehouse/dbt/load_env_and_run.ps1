# PowerShell script to load .env file and run dbt commands
# Usage: .\load_env_and_run.ps1 [dbt_command]
# Example: .\load_env_and_run.ps1 "dbt run"
# Example: .\load_env_and_run.ps1 "dbt test"

param(
    [Parameter(Mandatory=$false)]
    [string]$Command = "dbt --help"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "dbt Command Runner with .env" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Change to dbt directory
Set-Location $PSScriptRoot

# Path to .env file (in parent directory)
$envFile = Join-Path (Split-Path $PSScriptRoot -Parent) ".env"

if (-not (Test-Path $envFile)) {
    Write-Host "[ERROR] .env file not found at: $envFile" -ForegroundColor Red
    Write-Host ""
    exit 1
}

Write-Host "[INFO] Loading environment variables from .env file..." -ForegroundColor Green

# Load environment variables from .env file
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
    }
}

Write-Host "[OK] Environment variables loaded" -ForegroundColor Green
Write-Host ""
Write-Host "[INFO] Running: $Command" -ForegroundColor Cyan
Write-Host ""

# Run the dbt command
Invoke-Expression $Command

