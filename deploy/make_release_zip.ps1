$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$DistDir = Join-Path $ProjectRoot "dist"
$StageDir = Join-Path $DistDir "agid-telegram-bot"
$ZipPath = Join-Path $DistDir "agid-telegram-bot-release.zip"

if (Test-Path $StageDir) {
  Remove-Item -LiteralPath $StageDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $StageDir | Out-Null
New-Item -ItemType Directory -Force -Path $DistDir | Out-Null

Copy-Item -Path (Join-Path $ProjectRoot "telegram_ai_commenter") -Destination $StageDir -Recurse
Copy-Item -Path (Join-Path $ProjectRoot "deploy") -Destination $StageDir -Recurse

$RemovePaths = @(
  (Join-Path $StageDir "telegram_ai_commenter\.env"),
  (Join-Path $StageDir "telegram_ai_commenter\__pycache__"),
  (Join-Path $StageDir "telegram_ai_commenter\data"),
  (Join-Path $StageDir "telegram_ai_commenter\sessions")
)

foreach ($Path in $RemovePaths) {
  if (Test-Path $Path) {
    Remove-Item -LiteralPath $Path -Recurse -Force
  }
}

if (Test-Path $ZipPath) {
  Remove-Item -LiteralPath $ZipPath -Force
}

Compress-Archive -Path (Join-Path $StageDir "*") -DestinationPath $ZipPath -Force
Write-Host "Created release archive:"
Write-Host $ZipPath
Write-Host ""
Write-Host "Secrets are not included. Copy .env and sessions/ separately if needed."
