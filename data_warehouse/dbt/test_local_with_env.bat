@echo off
setlocal enabledelayedexpansion

echo ========================================
echo dbt Local Testing
echo ========================================
echo.

cd /d %~dp0

REM Load environment variables from .env file
set ENV_FILE=..\.env

if not exist "%ENV_FILE%" (
    echo ERROR: .env file not found
    pause
    exit /b 1
)

for /f "usebackq tokens=1,* delims==" %%a in ("%ENV_FILE%") do (
    set "line=%%a"
    if not "!line:~0,1!"=="#" (
        if not "!line!"=="" (
            set "%%a=%%b"
        )
    )
)
echo.

echo [1/8] Testing connection...
dbt debug --profiles-dir .
if errorlevel 1 (
    echo ERROR: Connection test failed!
    echo.
    echo Please check:
    echo   1. SQL Warehouse is running in Databricks
    echo   2. Token is valid
    echo   3. Environment variables are correct
    pause
    exit /b 1
)
echo.

echo [2/8] Installing dependencies...
dbt deps
if errorlevel 1 (
    echo ERROR: Package installation failed!
    pause
    exit /b 1
)
echo.

echo [3/8] Compiling project...
dbt compile --no-partial-parse
if errorlevel 1 (
    echo ERROR: Compilation failed!
    pause
    exit /b 1
)
echo.

echo [4/8] Running staging models...
dbt run --select staging.* --no-partial-parse
if errorlevel 1 (
    echo ERROR: Staging models failed!
    pause
    exit /b 1
)
echo.

echo [5/8] Running dimension models...
dbt run --select dimensions.*
if errorlevel 1 (
    echo ERROR: Dimension models failed!
    pause
    exit /b 1
)
echo.

echo [6/8] Running fact models...
dbt run --select facts.*
if errorlevel 1 (
    echo ERROR: Fact models failed!
    pause
    exit /b 1
)
echo.

echo [7/8] Running marts models...
dbt run --select marts.*
if errorlevel 1 (
    echo ERROR: Marts models failed!
    pause
    exit /b 1
)
echo.

echo [8/8] Running tests...
dbt test
if errorlevel 1 (
    echo WARNING: Some tests failed! Check the output above.
)
echo.

echo ========================================
echo All steps completed!
echo ========================================
echo.
echo To view documentation, run:
echo   dbt docs generate
echo   dbt docs serve
echo.

pause
endlocal

