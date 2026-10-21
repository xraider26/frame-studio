param([switch]$BackendOnly)
$ErrorActionPreference = 'Stop'
$studioRoot = $PSScriptRoot
$studioPython = Join-Path $studioRoot 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $studioPython)) { throw 'Install backend requirements using uv first. See docs/MCP.md.' }
try { $studioHealth = Invoke-RestMethod 'http://127.0.0.1:8010/health' -TimeoutSec 2 } catch { $studioHealth = $null }
if ($studioHealth.service -ne 'frame-studio') {
    $studioBackendArgs = @('-m', 'uvicorn', 'studio.api:app_factory', '--factory', '--host', '127.0.0.1', '--port', '8010')
    Start-Process -FilePath $studioPython -ArgumentList $studioBackendArgs -WorkingDirectory (Join-Path $studioRoot 'backend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $studioRoot 'studio-backend.log') -RedirectStandardError (Join-Path $studioRoot 'studio-backend-error.log')
}
if (-not $BackendOnly) {
    try { $studioFrontend = Invoke-WebRequest 'http://127.0.0.1:3000/studio' -UseBasicParsing -TimeoutSec 2 } catch { $studioFrontend = $null }
    if (-not $studioFrontend) {
        $studioNode = (Get-Command node.exe).Source
        $studioNext = Join-Path $studioRoot 'frontend\node_modules\next\dist\bin\next'
        $studioMode = if (Test-Path -LiteralPath (Join-Path $studioRoot 'frontend\.next\BUILD_ID')) { 'start' } else { 'dev' }
        Start-Process -FilePath $studioNode -ArgumentList @($studioNext, $studioMode, '--hostname', '127.0.0.1', '--port', '3000') -WorkingDirectory (Join-Path $studioRoot 'frontend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $studioRoot 'studio-frontend.log') -RedirectStandardError (Join-Path $studioRoot 'studio-frontend-error.log')
    }
}
Write-Host 'Frame Studio: http://127.0.0.1:3000/studio'
Write-Host 'MCP command: backend/.venv/Scripts/python.exe backend/studio_mcp.py'
Write-Host 'Local files, database and connection credentials: studio_data (keep private).'
