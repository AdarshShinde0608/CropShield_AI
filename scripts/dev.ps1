$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $repoRoot "backend"
$mlService = Join-Path $repoRoot "ml-service"
$frontend = Join-Path $repoRoot "frontend"
$backendPython = Join-Path $backend ".venv\Scripts\python.exe"
$mlPython = Join-Path $mlService ".venv\Scripts\python.exe"

foreach ($path in @($backendPython, $mlPython)) {
    if (-not (Test-Path $path)) {
        throw "Missing component virtual environment interpreter: $path. Follow docs/LOCAL_SETUP.md first."
    }
}
if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    throw "Missing frontend dependencies. Run npm ci in frontend/ first."
}

$env:PYTHONPATH = $repoRoot
$processes = @()
$processes += Start-Process -FilePath $backendPython `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory $backend -PassThru
$processes += Start-Process -FilePath $mlPython `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8001") `
    -WorkingDirectory $mlService -PassThru
$processes += Start-Process -FilePath "cmd.exe" `
    -ArgumentList @("/c", "npm run dev -- --host 127.0.0.1") `
    -WorkingDirectory $frontend -PassThru

Write-Output "Started backend, ML service, and frontend processes:"
$processes | ForEach-Object { Write-Output "PID $($_.Id)" }
Write-Output "Backend: http://127.0.0.1:8000"
Write-Output "ML service: http://127.0.0.1:8001"
Write-Output "Frontend: http://127.0.0.1:5173"
Write-Output "Close the started PowerShell/cmd windows to stop these processes."
