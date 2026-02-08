param(
    [switch]$Clean,
    [switch]$UseZig
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
        $pythonVersion = python --version 2>&1
        Write-Success "Python found: $pythonVersion"

        # Extract version number
        if ($pythonVersion -match "Python (\d+\.\d+)") {
            $version = [version]$matches[1]

            if ($version -ge [version]"3.13") {
                Write-Info "Python 3.13+ detected - using Zig compiler"
                $script:UseZigCompiler = $true
            } elseif ($version -ge [version]"3.12") {
                Write-Success "Python version is compatible"
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
        python -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) {
            Write-Error-Custom "Failed to install requirements.txt"
            exit 1
        }
        Write-Success "requirements.txt installed"

        Write-Info "Installing additional packages for MAICA..."
        python -m pip install python-magic-bin packaging
        if ($LASTEXITCODE -ne 0) {
            Write-Error-Custom "Failed to install additional packages"
            exit 1
        }
        Write-Success "Additional packages installed"

        Write-Info "Installing requirements_2.txt..."
        python -m pip install -r requirements_2.txt
        if ($LASTEXITCODE -ne 0) {
            Write-Error-Custom "Failed to install requirements_2.txt"
            exit 1
        }
        Write-Success "requirements_2.txt installed"

        Write-Info "Installing Nuitka..."
        python -m pip install nuitka
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
        $nuitkaInfo = python -m pip show nuitka 2>&1
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
            "python", "-m", "nuitka",
            "--onefile",
            "--include-package=websockets",
            "--include-package=magic",
            "--include-package=packaging",
            "--include-package-data=magic",
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
            "python", "-m", "nuitka",
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

    if ($Clean) {
        Write-Info "Clean build requested"
        Clean-BuildArtifacts
    }

    Install-Dependencies
    Verify-Nuitka
    Build-MAICA
    Build-Register
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
