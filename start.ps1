# Starts TalentFlow AI: MCP servers, API and UI, each in its own window.
# Usage:  powershell -ExecutionPolicy Bypass -File .\start.ps1
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Error "Create the virtualenv first (see README)."; exit 1 }
if (-not (Test-Path (Join-Path $root "data\runtime\talentflow.db"))) {
  Write-Host "First run: generating data and loading all stores (about 5 minutes)..."
  & $py (Join-Path $root "data\generate_seed.py")
  & $py (Join-Path $root "backend\scripts\bootstrap.py")
}
$env:PYTHONIOENCODING = "utf-8"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle='TalentFlow MCP'; & '$py' '$root\backend\scripts\run_mcp_servers.py'"
Start-Sleep -Seconds 6
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle='TalentFlow API'; Set-Location '$root\backend'; & '$py' -m uvicorn app.main:app --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle='TalentFlow UI'; Set-Location '$root\frontend'; if (-not (Test-Path node_modules)) { npm install }; npm run dev"
Start-Sleep -Seconds 8
Start-Process "http://localhost:5173"
Write-Host "TalentFlow AI starting: UI http://localhost:5173  API http://localhost:8000/docs  (password Demo@123)"
