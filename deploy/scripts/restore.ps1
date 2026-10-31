# Restore a backup set on Windows. THIS REPLACES ALL CURRENT DATA.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\restore.ps1 backups\sets\chhapakhata-db-YYYYMMDD-HHMMSS.dump
param([Parameter(Mandatory = $true)][string]$Dump)
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

if (-not (Test-Path $Dump)) { throw "Backup file not found: $Dump" }
$DumpPath = (Resolve-Path $Dump).Path
$Folder = Split-Path $DumpPath
$Media = Join-Path $Folder ((Split-Path $DumpPath -Leaf) -replace 'chhapakhata-db-', 'chhapakhata-media-' -replace '\.dump$', '.tar.gz')
$Checksum = $DumpPath -replace '\.dump$', '.sha256'

if (Test-Path $Checksum) {
  $expected = (Get-Content $Checksum).Split(' ')[0]
  $actual = (Get-FileHash $DumpPath -Algorithm SHA256).Hash.ToLower()
  if ($expected -ne $actual) { throw 'Checksum mismatch: the backup file is damaged.' }
}

Write-Host "This will REPLACE all current data with: $DumpPath"
$answer = Read-Host 'Type RESTORE to continue'
if ($answer -ne 'RESTORE') { Write-Host 'Cancelled.'; exit 1 }

docker compose stop api worker web
docker compose exec -T db sh -c 'dropdb -U chhapakhata --if-exists chhapakhata && createdb -U chhapakhata chhapakhata'
Get-Content $DumpPath -AsByteStream -ReadCount 0 | docker compose exec -T db pg_restore -U chhapakhata -d chhapakhata --no-owner --exit-on-error
# Restored as the superuser: hand the tables back to the app's own role.
Get-Content db\app-role.sql -Raw | docker compose exec -T db psql -X -q -U chhapakhata -d chhapakhata -v app_role=chhapakhata_app -f -

if (Test-Path $Media) {
  docker compose run --rm -T -v "${Folder}:/restore:ro" --entrypoint sh api -c "rm -rf /data/media/* && tar -xzf /restore/$(Split-Path $Media -Leaf) -C /data"
}

docker compose up -d
Write-Host 'Restore finished. Sign in and check recent orders and balances.'
