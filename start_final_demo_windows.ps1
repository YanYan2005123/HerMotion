$ErrorActionPreference = 'Stop'
$ProjectDir = $PSScriptRoot
Set-Location -LiteralPath $ProjectDir
$Python = Join-Path $ProjectDir '.venv-runtime/Scripts/python.exe'
$Vite = Join-Path $ProjectDir 'node_modules/vite/bin/vite.js'
if (-not (Test-Path -LiteralPath $Python)) { throw '请先按 README 在本工程内安装 Python 依赖。' }
if (-not (Test-Path -LiteralPath $Vite)) { throw '请先按 README 在本工程内安装前端依赖。' }
$Node = (Get-Command node -ErrorAction Stop).Source
$LogDir = Join-Path $ProjectDir '.runtime/logs'
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$env:OMP_NUM_THREADS = '2'
$env:MKL_NUM_THREADS = '2'
$env:PYTHONUNBUFFERED = '1'
$Children = @()
try {
  $Children += Start-Process -FilePath $Python -WorkingDirectory $ProjectDir -WindowStyle Hidden -PassThru -ArgumentList @('-u','yoga_model/runtime/server.py','--checkpoint','models/yoga/best.pt','--config','yoga_model/config/runtime_gate.json','--port','8765') -RedirectStandardOutput (Join-Path $LogDir 'yoga.out.log') -RedirectStandardError (Join-Path $LogDir 'yoga.err.log')
  $Children += Start-Process -FilePath $Python -WorkingDirectory $ProjectDir -WindowStyle Hidden -PassThru -ArgumentList @('-m','uvicorn','tongue_model.service:app','--host','127.0.0.1','--port','8766') -RedirectStandardOutput (Join-Path $LogDir 'tongue.out.log') -RedirectStandardError (Join-Path $LogDir 'tongue.err.log')
  Write-Host '前端将启动于 http://127.0.0.1:3001；模型加载可能需要等待。'
  & $Node $Vite --host 127.0.0.1 --port 3001 --strictPort
  if ($LASTEXITCODE -ne 0) { throw '前端启动失败，请查看终端输出。' }
} finally {
  foreach ($Child in $Children) { if (-not $Child.HasExited) { Stop-Process -Id $Child.Id -ErrorAction SilentlyContinue } }
}
