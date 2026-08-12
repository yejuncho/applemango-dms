$originalLocation = Get-Location
$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$repositoryRoot = (Resolve-Path (Join-Path $scriptDirectory "..")).Path
$scriptExitCode = 0

Push-Location $repositoryRoot

try {
    # Verify that Python comes from this repository's virtual environment.
    $expectedPython = [System.IO.Path]::GetFullPath((Join-Path $repositoryRoot ".venv\Scripts\python.exe"))
    $activePythonRaw = & python -c "import sys; print(sys.executable)"

    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($activePythonRaw)) {
        throw "Unable to determine active Python interpreter."
    }

    $activePython = [System.IO.Path]::GetFullPath(($activePythonRaw.Trim() -replace '/', '\'))

    if ($activePython.ToLowerInvariant() -ne $expectedPython.ToLowerInvariant()) {
        throw "Applemango DMS build requires the repository .venv to be active. Expected: $expectedPython | Found: $activePython"
    }

    Write-Host "Python: $activePython"

    # Verify that PyInstaller is available in the active environment.
    $pyInstallerVersion = (& python -m PyInstaller --version).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($pyInstallerVersion)) {
        throw "PyInstaller is not available. Install development dependencies with: python -m pip install -r requirements-dev.txt"
    }

    Write-Host "PyInstaller: $pyInstallerVersion"

    # Verify required build inputs before cleaning/building.
    $requiredPaths = @(
        "assets",
        "demo",
        "assets/logos/hiscom.ico",
        "src/applemango_dms/main.py"
    )

    $missingPaths = @()
    foreach ($requiredPath in $requiredPaths) {
        if (-not (Test-Path $requiredPath)) {
            $missingPaths += $requiredPath
        }
    }

    if ($missingPaths.Count -gt 0) {
        $missingList = ($missingPaths -join ", ")
        throw "Required build input is missing: $missingList"
    }

    # Remove only generated PyInstaller output from previous runs.
    $generatedArtifacts = @("build", "dist", "ApplemangoDMS.spec")
    foreach ($artifactPath in $generatedArtifacts) {
        if (Test-Path $artifactPath) {
            Remove-Item -Recurse -Force $artifactPath
            Write-Host "Removed: $artifactPath"
        }
    }

    # Run the proven onefile build configuration.
    $pyInstallerArguments = @(
        "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name", "ApplemangoDMS",
        "--paths", "src",
        "--add-data", "assets:assets",
        "--add-data", "demo:demo",
        "--icon", "assets/logos/hiscom.ico",
        "src/applemango_dms/main.py"
    )

    & python @pyInstallerArguments
    $pyInstallerExitCode = $LASTEXITCODE

    if ($pyInstallerExitCode -ne 0) {
        $scriptExitCode = $pyInstallerExitCode
        throw "PyInstaller build failed with exit code $pyInstallerExitCode."
    }

    $outputExePath = Join-Path $repositoryRoot "dist\ApplemangoDMS.exe"
    if (-not (Test-Path $outputExePath)) {
        throw "Build reported success but output executable was not found: $outputExePath"
    }

    $outputExeFile = Get-Item $outputExePath
    $outputSizeBytes = $outputExeFile.Length
    $outputSizeMb = [math]::Round($outputSizeBytes / 1MB, 2)

    Write-Host "Build complete"
    Write-Host "Output: $outputExePath"
    Write-Host "Size: $outputSizeMb MB ($outputSizeBytes bytes)"
}
catch {
    if ($scriptExitCode -eq 0) {
        $scriptExitCode = 1
    }

    Write-Error $_.Exception.Message
    Write-Host "Build failed"
}
finally {
    Set-Location $originalLocation
}

if ($scriptExitCode -ne 0) {
    exit $scriptExitCode
}
