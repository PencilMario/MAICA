param(
    [switch]$Clean,
    [switch]$UseZig,
    [string]$PythonPath
)

# Color output functions
function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

function Write-Info {
    param([string]$Message)
    Write-Host "ℹ $Message" -ForegroundColor Cyan
}

function Write-Warning-Custom {
    param([string]$Message)
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

# Check Python installation
function Check-Python {
    Write-Info "Checking Python installation..."

    try {
        if (-not $PythonPath) {
            $candidates = @(
                (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
                (Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"),
                "python"
            )
            $PythonPath = $candidates | Where-Object {
                if ($_ -eq "python") { $true } else { Test-Path $_ }
            } | Select-Object -First 1
        }

        if (-not $PythonPath) {
            throw "Python 3.12+ was not found"
        }

        $resolvedPython = (Get-Command $PythonPath -ErrorAction SilentlyContinue).Source
        if (-not $resolvedPython -and (Test-Path $PythonPath)) {
            $resolvedPython = (Resolve-Path $PythonPath).Path
        }
        if (-not $resolvedPython) {
            throw "Python executable not found: $PythonPath"
        }
        $script:PythonPath = $resolvedPython

        $pythonVersion = & $script:PythonPath --version 2>&1
        Write-Success "Python found: $pythonVersion"

        # Extract version number
        if ($pythonVersion -match "Python (\d+\.\d+)") {
            $version = [version]$matches[1]

            if ($version -ge [version]"3.13") {
                Write-Warning-Custom "Python 3.13+ is not the recommended Nuitka onefile runtime for MAICA; prefer Python 3.12"
                $script:UseZigCompiler = $true
            } elseif ($version -ge [version]"3.12") {
                Write-Success "Python version is compatible"
                $script:UseZigCompiler = $true
            } else {
                Write-Warning-Custom "Python version may not be 3.12+: $pythonVersion"
            }
        }
        return $true
    }
    catch {
        Write-Error-Custom "Python not found or not in PATH"
        exit 1
    }
}

# Install dependencies
function Install-Dependencies {
    Write-Info "Installing dependencies..."

    try {
        Write-Info "Installing requirements.txt..."
        & $script:PythonPath -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) {
            Write-Error-Custom "Failed to install requirements.txt"
            exit 1
        }
        Write-Success "requirements.txt installed"

        Write-Info "Installing additional packages for MAICA..."
        & $script:PythonPath -m pip install python-magic-bin packaging pymilvus
        if ($LASTEXITCODE -ne 0) {
            Write-Error-Custom "Failed to install additional packages"
            exit 1
        }
        Write-Success "Additional packages installed"

        Write-Info "Installing requirements_2.txt..."
        & $script:PythonPath -m pip install -r requirements_2.txt
        if ($LASTEXITCODE -ne 0) {
            Write-Error-Custom "Failed to install requirements_2.txt"
            exit 1
        }
        Write-Success "requirements_2.txt installed"

        Write-Info "Installing Nuitka..."
        & $script:PythonPath -m pip install nuitka
        if ($LASTEXITCODE -ne 0) {
            Write-Error-Custom "Failed to install Nuitka"
            exit 1
        }
        Write-Success "Nuitka installed"
    }
    catch {
        Write-Error-Custom "Error during dependency installation: $_"
        exit 1
    }
}

# Verify Nuitka installation
function Verify-Nuitka {
    Write-Info "Verifying Nuitka installation..."

    try {
        $nuitkaInfo = & $script:PythonPath -m pip show nuitka 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Nuitka is installed and ready"
        } else {
            Write-Error-Custom "Nuitka verification failed"
            exit 1
        }
    }
    catch {
        Write-Error-Custom "Nuitka verification failed"
        exit 1
    }
}

# Clean build artifacts
function Clean-BuildArtifacts {
    Write-Info "Cleaning previous build artifacts..."

    if (Test-Path "build") {
        Remove-Item -Path "build" -Recurse -Force
        Write-Success "Removed build directory"
    }

    if (Test-Path "maica_starter.build") {
        Remove-Item -Path "maica_starter.build" -Recurse -Force
        Write-Success "Removed maica_starter.build directory"
    }

    if (Test-Path "create_account.build") {
        Remove-Item -Path "create_account.build" -Recurse -Force
        Write-Success "Removed create_account.build directory"
    }
}

# Build MAICA executable
function Build-MAICA {
    Write-Info "Building MAICA executable..."

    try {
        $nuitkaCmd = @(
            $script:PythonPath, "-m", "nuitka",
            "--onefile",
            "--include-package=websockets",
            "--include-package=magic",
            "--include-package=packaging",
            "--include-package=lancedb",
            "--include-package=lance_namespace",
            "--include-package=pyarrow",
            "--include-package=pymilvus",
            "--include-package-data=magic",
            "--include-data-files=maica/env_basis=env_basis",
            "--nofollow-import-to=maica.Lib",
            "--nofollow-import-to=maica.test_module",
            "--assume-yes-for-downloads",
            "--output-dir=build"
        )

        # Add --zig if needed
        if ($UseZig -or $script:UseZigCompiler) {
            Write-Info "Using Zig compiler..."
            $nuitkaCmd += "--zig"
        }

        $nuitkaCmd += "maica/maica_starter.py"

        & $nuitkaCmd[0] $nuitkaCmd[1..($nuitkaCmd.Length-1)]

        if ($LASTEXITCODE -ne 0) {
            Write-Error-Custom "Failed to build MAICA executable"
            exit 1
        }
        Write-Success "MAICA executable built successfully"
    }
    catch {
        Write-Error-Custom "Error building MAICA: $_"
        exit 1
    }
}

# Build Register executable
function Build-Register {
    Write-Info "Building Register executable..."

    try {
        $nuitkaCmd = @(
            $script:PythonPath, "-m", "nuitka",
            "--onefile",
            "--output-dir=build"
        )

        # Add --zig if needed
        if ($UseZig -or $script:UseZigCompiler) {
            Write-Info "Using Zig compiler..."
            $nuitkaCmd += "--zig"
        }

        $nuitkaCmd += "maica/create_account.py"

        & $nuitkaCmd[0] $nuitkaCmd[1..($nuitkaCmd.Length-1)]

        if ($LASTEXITCODE -ne 0) {
            Write-Error-Custom "Failed to build Register executable"
            exit 1
        }
        Write-Success "Register executable built successfully"
    }
    catch {
        Write-Error-Custom "Error building Register: $_"
        exit 1
    }
}

# Prepare files that MAICA intentionally keeps next to the executable.
function Prepare-RuntimeFiles {
    Write-Info "Preparing runtime files..."
    $runtimeDir = Join-Path (Get-Location).Path "build"
    $envSource = Join-Path (Get-Location).Path "maica\env_basis"
    $envTarget = Join-Path $runtimeDir "env_basis"

    if (-not (Test-Path $envSource)) {
        Write-Error-Custom "Runtime file not found: $envSource"
        exit 1
    }
    Copy-Item -LiteralPath $envSource -Destination $envTarget -Force
    Write-Success "Prepared runtime file: $envTarget"
}

# Verify executables
function Verify-Executables {
    Write-Info "Verifying build outputs..."

    $maicaExe = "build/maica_starter.exe"
    $registerExe = "build/create_account.exe"

    $maicaExists = Test-Path $maicaExe
    $registerExists = Test-Path $registerExe

    if ($maicaExists) {
        $maicaSize = (Get-Item $maicaExe).Length / 1MB
        Write-Success "MAICA executable found: $maicaExe ($('{0:F2}' -f $maicaSize) MB)"
    } else {
        Write-Error-Custom "MAICA executable not found: $maicaExe"
        exit 1
    }

    if ($registerExists) {
        $registerSize = (Get-Item $registerExe).Length / 1MB
        Write-Success "Register executable found: $registerExe ($('{0:F2}' -f $registerSize) MB)"
    } else {
        Write-Error-Custom "Register executable not found: $registerExe"
        exit 1
    }

    Write-Info "Running MAICA startup smoke test in an isolated distribution directory..."
    $smokeDir = Join-Path $env:TEMP "maica-starter-smoke-$PID"
    $smokeOut = Join-Path $smokeDir "stdout.txt"
    $smokeErr = Join-Path $smokeDir "stderr.txt"
    Remove-Item $smokeDir -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Path $smokeDir | Out-Null
    Copy-Item -LiteralPath (Resolve-Path $maicaExe).Path -Destination (Join-Path $smokeDir "maica_starter.exe")
    Copy-Item -LiteralPath (Join-Path (Get-Location).Path "build\env_basis") -Destination (Join-Path $smokeDir "env_basis")
    $smoke = Start-Process -FilePath (Join-Path $smokeDir "maica_starter.exe") -ArgumentList "-t", "print" `
        -WorkingDirectory $smokeDir -RedirectStandardOutput $smokeOut `
        -RedirectStandardError $smokeErr -PassThru
    if (-not $smoke.WaitForExit(30000)) {
        Stop-Process -Id $smoke.Id -Force -ErrorAction SilentlyContinue
        Write-Error-Custom "MAICA startup smoke test timed out"
        exit 1
    }
    if ($smoke.ExitCode -ne 0) {
        Write-Error-Custom "MAICA startup smoke test failed (exit $($smoke.ExitCode))"
        if (Test-Path $smokeOut) { Get-Content -Raw $smokeOut }
        if (Test-Path $smokeErr) { Get-Content -Raw $smokeErr }
        exit 1
    }
    Write-Success "MAICA startup smoke test passed"

    Write-Success "All executables verified successfully"
}

# Main execution
function Main {
    Write-Host "========================================" -ForegroundColor Magenta
    Write-Host "MAICA Local Build Script" -ForegroundColor Magenta
    Write-Host "========================================" -ForegroundColor Magenta
    Write-Host ""

    # Check if running from project root
    if (-not (Test-Path "requirements.txt") -or -not (Test-Path "maica/maica_starter.py")) {
        Write-Error-Custom "Script must be run from project root directory"
        exit 1
    }

    Check-Python
    Write-Info "Using build interpreter: $script:PythonPath"

    if ($Clean) {
        Write-Info "Clean build requested"
        Clean-BuildArtifacts
    }

    Install-Dependencies
    Verify-Nuitka
    Build-MAICA
    Build-Register
    Prepare-RuntimeFiles
    Verify-Executables

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Magenta
    Write-Success "Build completed successfully!"
    Write-Host "========================================" -ForegroundColor Magenta
    Write-Host ""
    Write-Info "Output files:"
    Write-Host "  - build/maica_starter.exe"
    Write-Host "  - build/create_account.exe"
}

# Run main function
Main
