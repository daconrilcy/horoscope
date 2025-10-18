<#
PowerShell dev script to run FastAPI with reload.
- Resolves repo root from script location
- Loads .env into $env:*
- Ensures PYTHONPATH includes backend
- Defaults HOST/PORT, pass-through extra args to uvicorn
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Resolve repo root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir '..\..')
Set-Location $RepoRoot

# Auto-activate virtualenv if present
$venvActivate = Join-Path $RepoRoot '.venv\\Scripts\\Activate.ps1'
if (Test-Path $venvActivate) {
  try { . $venvActivate } catch { Write-Verbose "Venv activation failed: $_" }
}

# Helpers
function Strip-InlineComment([string]$s) {
  if (-not $s) { return $s }
  $sb = New-Object System.Text.StringBuilder
  $inS = $false; $inD = $false
  for ($i=0; $i -lt $s.Length; $i++) {
    $ch = $s[$i]
    if (-not $inD -and $ch -eq [char]39) { $inS = -not $inS; [void]$sb.Append($ch); continue }
    if (-not $inS -and $ch -eq [char]34) { $inD = -not $inD; [void]$sb.Append($ch); continue }
    if (-not $inS -and -not $inD -and $ch -eq '#') { break }
    [void]$sb.Append($ch)
  }
  return $sb.ToString().Trim()
}

# Load .env if present
$envPath = Join-Path $RepoRoot '.env'
if (Test-Path $envPath) {
  Get-Content $envPath | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith('#')) { return }
    if ($line.StartsWith('export ')) { $line = $line.Substring(7).Trim() }
    $idx = $line.IndexOf('=')
    if ($idx -lt 1) { return }
    $key = $line.Substring(0, $idx).Trim()
    $val = $line.Substring($idx + 1)
    $val = Strip-InlineComment $val
    $val = $val.Trim()
    if ($val.Length -ge 2) {
      $dq = [char]34  # "
      $sq = [char]39  # '
      if ((($val[0] -eq $dq) -and ($val[-1] -eq $dq)) -or (($val[0] -eq $sq) -and ($val[-1] -eq $sq))) {
        $val = $val.Substring(1, $val.Length - 2)
      }
    }
    if ($key) { Set-Item -Path Env:$key -Value $val }
  }
}

# Ensure backend on PYTHONPATH (Windows uses ';' as separator)
$backendPath = Join-Path $RepoRoot 'backend'
if (-not $env:PYTHONPATH -or [string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
  $env:PYTHONPATH = $backendPath
} else {
  $parts = $env:PYTHONPATH -split ';'
  if (-not ($parts -contains $backendPath)) { $env:PYTHONPATH = "$backendPath;$env:PYTHONPATH" }
}

# Defaults
if (-not $env:HOST -or [string]::IsNullOrWhiteSpace($env:HOST)) { $env:HOST = '0.0.0.0' }
if (-not $env:PORT -or [string]::IsNullOrWhiteSpace($env:PORT)) { $env:PORT = '8000' }

# Build args
$uvArgs = @('app.main:app', '--host', $env:HOST, '--port', $env:PORT, '--reload') + $args

# Prefer uvicorn binary; fallback to python -m uvicorn
$uvicornCmd = (Get-Command uvicorn -ErrorAction SilentlyContinue)
if ($uvicornCmd) {
  & $uvicornCmd.Path @uvArgs
} else {
  & python '-m' 'uvicorn' @uvArgs
}
