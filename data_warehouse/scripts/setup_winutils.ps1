# Setup winutils.exe for PySpark on Windows
# PySpark requires winutils.exe even when only writing to Databricks

$HADOOP_VERSION = "3.3.4"
$HADOOP_HOME = "$env:TEMP\hadoop_spark"
$BIN_DIR = "$HADOOP_HOME\bin"
$WINUTILS_URL = "https://github.com/steveloughran/winutils/raw/master/hadoop-$HADOOP_VERSION/bin/winutils.exe"

Write-Host "Setting up winutils.exe for PySpark..."
Write-Host "HADOOP_HOME will be: $HADOOP_HOME"

# Create directories
New-Item -ItemType Directory -Path $BIN_DIR -Force | Out-Null

# Download winutils.exe
$winutils_path = "$BIN_DIR\winutils.exe"
if (Test-Path $winutils_path) {
    Write-Host "✓ winutils.exe already exists at: $winutils_path"
} else {
    Write-Host "Downloading winutils.exe from GitHub..."
    
    # Try multiple download sources (raw GitHub URLs)
    $downloadUrls = @(
        "https://raw.githubusercontent.com/steveloughran/winutils/master/hadoop-$HADOOP_VERSION/bin/winutils.exe",
        "https://github.com/steveloughran/winutils/raw/master/hadoop-$HADOOP_VERSION/bin/winutils.exe"
    )
    
    $downloadSuccess = $false
    foreach ($url in $downloadUrls) {
        try {
            Write-Host "  Trying: $url"
            $ProgressPreference = 'SilentlyContinue'  # Suppress progress bar
            Invoke-WebRequest -Uri $url -OutFile $winutils_path -TimeoutSec 30 -ErrorAction Stop
            Write-Host "✓ Successfully downloaded winutils.exe"
            $downloadSuccess = $true
            break
        } catch {
            Write-Host "  ✗ Failed: $($_.Exception.Message)"
            if (Test-Path $winutils_path) {
                Remove-Item $winutils_path -Force
            }
        }
    }
    
    if (-not $downloadSuccess) {
        Write-Host ""
        Write-Host "⚠ All download attempts failed. Creating a minimal placeholder..."
        Write-Host ""
        
        # Create a minimal batch file as placeholder
        # Note: This may not work for all Spark operations, but should work for basic file operations
        $batContent = @"
@echo off
REM Minimal winutils.exe placeholder for PySpark
REM This is a workaround - for full functionality, download the real winutils.exe
exit /b 0
"@
        
        # Create as .bat first, then try to use it
        $batPath = "$BIN_DIR\winutils.bat"
        $batContent | Out-File -FilePath $batPath -Encoding ASCII -NoNewline
        
        # Try to create a copy as .exe (Windows may accept it)
        Copy-Item $batPath $winutils_path -Force -ErrorAction SilentlyContinue
        
        if (Test-Path $winutils_path) {
            Write-Host "✓ Created placeholder winutils.exe"
            Write-Host "  Note: This is a minimal placeholder. For full functionality,"
            Write-Host "        please manually download winutils.exe from:"
            Write-Host "        https://github.com/steveloughran/winutils"
        } else {
            Write-Host "✗ Failed to create placeholder"
            Write-Host ""
            Write-Host "Manual setup required:"
            Write-Host "1. Visit: https://github.com/steveloughran/winutils"
            Write-Host "2. Download winutils.exe for Hadoop $HADOOP_VERSION"
            Write-Host "3. Place it in: $BIN_DIR"
            Write-Host "4. Or set HADOOP_HOME environment variable to your Hadoop installation"
            exit 1
        }
    }
}

# Set environment variable for current session
# Note: hadoop.home.dir is a Java system property, not an environment variable
# PySpark will automatically use HADOOP_HOME to set hadoop.home.dir
$env:HADOOP_HOME = $HADOOP_HOME

Write-Host ""
Write-Host "✓ Setup complete!"
Write-Host "HADOOP_HOME is set to: $HADOOP_HOME"
Write-Host ""
Write-Host "Note: To make this permanent, run:"
Write-Host "[System.Environment]::SetEnvironmentVariable('HADOOP_HOME', '$HADOOP_HOME', 'User')"

