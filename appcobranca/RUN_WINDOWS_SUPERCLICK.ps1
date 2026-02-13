param(
  [int]$StartPort = 8000,
  [int]$MaxTries = 10
)

$ErrorActionPreference = "Stop"

function Test-Port($port) {
  try {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port)
    $listener.Start()
    $listener.Stop()
    return $true
  } catch {
    return $false
  }
}

function Find-FreePort($startPort, $maxTries) {
  for ($i=0; $i -lt $maxTries; $i++) {
    $p = $startPort + $i
    if (Test-Port $p) { return $p }
  }
  throw "Nenhuma porta livre encontrada entre $startPort e " + ($startPort + $maxTries - 1)
}

Write-Host "=========================================="
Write-Host "Portal Moveis - App de Cobranca (MVP v2)"
Write-Host "=========================================="
Write-Host ""

# Check Python
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
  Write-Host "ERRO: Python nao encontrado no Windows." -ForegroundColor Red
  Write-Host "Instale Python 3.11+ e marque 'Add python to PATH'." -ForegroundColor Yellow
  Write-Host "Depois rode de novo este arquivo." -ForegroundColor Yellow
  Pause
  exit 1
}

# Create venv
if (-not (Test-Path ".venv")) {
  python -m venv .venv
}

# Activate venv
& .\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip | Out-Host
pip install -r requirements.txt | Out-Host

$port = Find-FreePort $StartPort $MaxTries
Write-Host ""
Write-Host "Iniciando servidor na porta $port ..." -ForegroundColor Cyan
Write-Host "Login: admin@portalmoveis.local  Senha: admin123"
Write-Host ""

# Open browser after a short delay
Start-Job -ScriptBlock {
  param($p)
  Start-Sleep -Seconds 2
  Start-Process "http://localhost:$p"
} -ArgumentList $port | Out-Null

# Run uvicorn (no reload to reduce issues)
uvicorn app.main:app --host 127.0.0.1 --port $port
