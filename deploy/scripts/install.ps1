# First-time installation on a Windows shop computer with Docker Desktop.
# Run from the deploy\ folder:  powershell -ExecutionPolicy Bypass -File scripts\install.ps1
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

docker compose version | Out-Null

function New-Secret([int]$length) {
  $bytes = New-Object byte[] 64
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  return (([Convert]::ToBase64String($bytes)) -replace '[/+=]', '').Substring(0, $length)
}

if (-not (Test-Path .env)) {
  $content = Get-Content .env.example -Raw
  $content = $content -replace '(?m)^SECRET_KEY=.*$', ("SECRET_KEY=" + (New-Secret 60))
  $content = $content -replace '(?m)^POSTGRES_PASSWORD=.*$', ("POSTGRES_PASSWORD=" + (New-Secret 32))
  Set-Content -Path .env -Value $content -NoNewline
  Write-Host 'Created deploy\.env with fresh secrets. Review SITE_ADDRESS and ALLOWED_HOSTS, then run this script again.'
  exit 0
}

New-Item -ItemType Directory -Force -Path backups, rclone | Out-Null
docker compose up -d --build

Write-Host 'Waiting for the app to start...'
for ($i = 0; $i -lt 90; $i++) {
  docker compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health/', timeout=3)" 2>$null
  if ($LASTEXITCODE -eq 0) { Write-Host 'ChhapaKhata is running.'; break }
  Start-Sleep -Seconds 2
}

Write-Host ''
Write-Host 'Next: create the owner account:'
Write-Host '  docker compose run --rm api python manage.py create_owner --username <name> --first-name <First>'
Write-Host 'In Docker Desktop settings, turn on "Start Docker Desktop when you sign in".'
