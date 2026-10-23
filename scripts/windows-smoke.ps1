# Windows 兼容性冒烟（发布前人工执行，不属于 WSL 测试套件）
param(
  [string]$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"
Write-Host "Repo: $Repo"
node --version
npm --version

Push-Location $Repo
try {
  npm run build --silent
  if ($LASTEXITCODE -ne 0) { throw "build failed" }

  $Root = Join-Path ([System.IO.Path]::GetTempPath()) ("sage-kit-windows-smoke-" + [guid]::NewGuid().ToString("N"))
  New-Item -ItemType Directory -Path $Root | Out-Null
  Push-Location $Root
  try {
    git init -q
    git config user.email "windows-smoke@example.com"
    git config user.name "windows-smoke"
    "hello" | Out-File -Encoding utf8 README.md
    git add README.md
    git commit -qm initial

    node (Join-Path $Repo "dist\cli.js") init --host dsh --scope project --no-instructions
    if (-not (Test-Path (Join-Path $Root ".dsh\skills\sage-kit\SKILL.md"))) { throw "DSH skill was not installed" }
    if (-not (Test-Path (Join-Path $Root ".sage-kit\config.json"))) { throw "config was not written" }

    $doctor = node (Join-Path $Repo "dist\cli.js") doctor --json | ConvertFrom-Json
    if (-not $doctor.ok) { throw "doctor failed: $($doctor | ConvertTo-Json -Compress)" }

    node (Join-Path $Repo "dist\cli.js") task create --title "Windows smoke" --acceptance "paths work"
    $id = (node (Join-Path $Repo "dist\cli.js") task list --json | ConvertFrom-Json).tasks[0].id
    node (Join-Path $Repo "dist\cli.js") task status $id running
    node (Join-Path $Repo "dist\cli.js") task status $id review
    node (Join-Path $Repo "dist\cli.js") task status $id done --evidence "windows-smoke.ps1"

    node (Join-Path $Repo "dist\cli.js") uninstall
    if (Test-Path (Join-Path $Root ".sage-kit\config.json")) { throw "uninstall did not remove config" }

    Write-Host "WINDOWS_SMOKE_PASS"
  } finally {
    Pop-Location
    Remove-Item -Recurse -Force $Root -ErrorAction SilentlyContinue
  }
} finally {
  Pop-Location
}
