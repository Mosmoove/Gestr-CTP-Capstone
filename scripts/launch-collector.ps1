$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $env:LOCALAPPDATA 'GestrRuntime'
$toolsRoot = Join-Path $runtimeRoot 'tools'
$uvPath = Join-Path $toolsRoot 'bin/uv.exe'
$environmentRoot = Join-Path $runtimeRoot 'venv'
$pythonPath = Join-Path $environmentRoot 'Scripts/python.exe'
$pythonWindowPath = Join-Path $environmentRoot 'Scripts/pythonw.exe'
$requirementsPath = Join-Path $projectRoot 'requirements-collector.txt'
$stampPath = Join-Path $runtimeRoot 'collector-requirements.sha256'

try {
    New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
    if (-not (Test-Path -LiteralPath $uvPath)) {
        Write-Host 'First launch: downloading the Python setup tool...'
        $uvVersion = '0.13.8'
        $downloadPath = Join-Path $runtimeRoot "uv-$uvVersion.zip"
        $extractPath = Join-Path $runtimeRoot "uv-$uvVersion"
        Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/astral-sh/uv/releases/download/$uvVersion/uv-x86_64-pc-windows-msvc.zip" -OutFile $downloadPath
        Expand-Archive -LiteralPath $downloadPath -DestinationPath $extractPath -Force
        $downloadedUv = @(Get-ChildItem -LiteralPath $extractPath -Filter uv.exe -File -Recurse)
        if ($downloadedUv.Count -ne 1) { throw 'The setup download did not contain uv.exe.' }
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $uvPath) | Out-Null
        Copy-Item -LiteralPath $downloadedUv[0].FullName -Destination $uvPath
    }
    if (-not (Test-Path -LiteralPath $pythonPath)) {
        Write-Host 'First launch: setting up an isolated Python 3.12 environment...'
        & $uvPath --system-certs venv $environmentRoot --python 3.12
        if ($LASTEXITCODE -ne 0) { throw 'Python setup failed. Check your internet connection and try again.' }
    }
    $hasher = [System.Security.Cryptography.SHA256]::Create()
    try {
        $requirementsHash = [BitConverter]::ToString($hasher.ComputeHash([IO.File]::ReadAllBytes($requirementsPath))).Replace('-', '')
    } finally {
        $hasher.Dispose()
    }
    $installedHash = if (Test-Path -LiteralPath $stampPath) { (Get-Content -LiteralPath $stampPath -Raw).Trim() } else { '' }
    if ($requirementsHash -ne $installedHash) {
        Write-Host 'Installing the camera libraries. The first launch can take a few minutes...'
        & $uvPath --system-certs pip install --python $pythonPath -r $requirementsPath
        if ($LASTEXITCODE -ne 0) { throw 'Library installation failed. Check your internet connection and try again.' }
        Set-Content -LiteralPath $stampPath -Value $requirementsHash
    }
    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'hand_landmarker.task'))) {
        throw 'hand_landmarker.task is missing from the project folder. Restore it from Git.'
    }
    $launchId = [guid]::NewGuid().ToString('N')
    $readyPath = Join-Path $runtimeRoot "collector-ready-$launchId.txt"
    $stdoutPath = Join-Path $runtimeRoot "collector-$launchId.stdout.log"
    $stderrPath = Join-Path $runtimeRoot "collector-$launchId.stderr.log"
    Write-Host 'Opening the gesture collector...'
    $collectorArguments = @('-m', 'collector.app', '--ready-file', ('"' + $readyPath + '"'))
    $collectorProcess = Start-Process -FilePath $pythonWindowPath -ArgumentList $collectorArguments -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -PassThru
    $deadline = (Get-Date).AddSeconds(60)
    while (-not (Test-Path -LiteralPath $readyPath)) {
        $collectorProcess.Refresh()
        if ($collectorProcess.HasExited) {
            $details = if (Test-Path -LiteralPath $stderrPath) { Get-Content -LiteralPath $stderrPath -Raw } else { '' }
            throw "The collector closed before opening. $details"
        }
        if ((Get-Date) -gt $deadline) {
            throw "The collector is taking longer than expected. Check whether its window has opened. Diagnostic log: $stderrPath"
        }
        Start-Sleep -Milliseconds 200
    }
    # Temporary launch handshake; collection CSVs are never removed by the launcher.
    Remove-Item -LiteralPath $readyPath
    exit 0
} catch {
    Write-Host ''
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host "Setup and diagnostic files: $runtimeRoot"
    exit 1
}
