$ErrorActionPreference = 'Stop'

Write-Host "=== Phase-4 PRs Dry-Run Orchestrator ==="

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
  Write-Host "[Error] GitHub CLI (gh) is not installed or not in PATH."
  Write-Host "        Install from https://cli.github.com/ and run: gh auth login"
  exit 1
}

function Get-PrByHead {
  param(
    [string]$Repo,
    [string]$Branch
  )
  try {
    $obj = gh pr list -R $Repo --head $Branch --json number,state,headRefName,baseRefName,url -q ".[0]"
    return $obj
  } catch {
    return $null
  }
}

function Get-PRsByLabel {
  param(
    [string]$Repo,
    [string]$Label = "phase4",
    [string]$State = "all"  # open|closed|merged|all
  )
  try {
    $query = ('label:"{0}"' -f $Label)
    $json = gh pr list -R $Repo --state $State --search $query --json number,title,state,headRefName,baseRefName,url
    if ([string]::IsNullOrWhiteSpace($json)) { return @() }
    $items = $json | ConvertFrom-Json
    if ($items -is [string]) { return @() }
    return @($items)
  } catch {
    return @()
  }
}

function Invoke-PRDryRun {
  param(
    [string]$Repo,
    [string]$Branch,
    [string]$Labels,
    [string]$Milestone
  )

  $pr = Get-PrByHead -Repo $Repo -Branch $Branch
  if (-not $pr) {
    Write-Host ("[Dry-Run] No PR found for branch {0}" -f $Branch)
    return
  }

  Write-Host ("[Dry-Run] PR #{0} {1} (state={2})" -f $pr.number, $pr.url, $pr.state)

  # 1) Re-run CI (show commands only)
  Write-Host ("[Dry-Run] Would re-run CI for PR #{0}" -f $pr.number)
  Write-Host ("          gh run list -R {0} --json databaseId,status,name,headBranch --limit 5" -f $Repo)
  Write-Host ("          gh run rerun <run_id> -R {0}" -f $Repo)

  # 2) Polling status (simulated)
  Write-Host ("[Dry-Run] Would poll CI status until success/timeout (simulated)")

  # 3) Merge if green (squash)
  Write-Host ("[Dry-Run] If CI green → would merge: gh pr merge {0} -R {1} --squash --delete-branch" -f $pr.number, $Repo)
  if ($Labels) { Write-Host ("[Dry-Run] Would apply labels: {0}" -f $Labels) }
  if ($Milestone) { Write-Host ("[Dry-Run] Would set milestone: {0}" -f $Milestone) }
  Write-Host ("[Dry-Run] Would comment 'Merged ✅ — CI green, Phase-4'")

  # 4) Clean remote branch (if not auto-deleted)
  Write-Host ("[Dry-Run] Would delete remote branch if needed: git push origin --delete {0}" -f $Branch)
  Write-Host ""
}

# Repository
$repo = "daconrilcy/horoscope"

# Target PRs (head branches)
$targets = @(
  @{ Branch="feat/2-retrieval-adapter";     Labels="retrieval,feature,phase4"; Milestone="Phase-4" },
  @{ Branch="feat/3-retrieval-bench";       Labels="bench,feature,phase4";     Milestone="Phase-4" },
  @{ Branch="feat/4-dual-write";            Labels="ingest,feature,phase4";    Milestone="Phase-4" },
  @{ Branch="feat/5-shadow-read-agreement"; Labels="retrieval,feature,phase4"; Milestone="Phase-4" },
  @{ Branch="feat/6-cutover-rollback";      Labels="ops,phase4";               Milestone="Phase-4" },
  @{ Branch="feat/7-contentversion-sql";    Labels="database,feature,phase4";  Milestone="Phase-4" },
  @{ Branch="ci/8-embeddings-workflow";     Labels="ci,phase4";                Milestone="Phase-4" }
)

foreach ($t in $targets) {
  Invoke-PRDryRun -Repo $repo -Branch $t.Branch -Labels $t.Labels -Milestone $t.Milestone
}

Write-Host "=== Optional Project v2 (Dry-Run) ==="
Write-Host "[Dry-Run] Would add PR URLs to project:"
Write-Host "          gh project list --owner daconrilcy"
Write-Host "          gh project item-add --owner daconrilcy --project-number <NUM> --url <PR_URL>"

Write-Host "=== Board/Milestone (Dry-Run) ==="
Write-Host "[Dry-Run] After merging #2→#8, would close milestone 'Phase-4' and move cards → Done"

# Fallback: list existing Phase-4 PRs by label (for visibility)
Write-Host "=== Phase-4 PRs discovered by label (state=all) ==="
$phase4 = Get-PRsByLabel -Repo $repo -Label "phase4" -State "all"
if ($phase4 -and ($phase4 | Measure-Object).Count -gt 0 -and $phase4[0].PSObject.Properties.Name -contains 'number') {
  foreach ($pr in $phase4) { Write-Host ("[#{0}] {1} ({2}) — {3}" -f $pr.number, $pr.title, $pr.state, $pr.url) }
} else {
  Write-Host "No PRs found with label 'phase4'. Listing all PRs (state=all):"
  try {
    $allJson = gh pr list -R $repo --state all --json number,title,state,url
    if (-not [string]::IsNullOrWhiteSpace($allJson)) {
      $all = $allJson | ConvertFrom-Json
      foreach ($pr in @($all)) { Write-Host ("[#{0}] {1} ({2}) — {3}" -f $pr.number, $pr.title, $pr.state, $pr.url) }
    } else { Write-Host "(none)" }
  } catch { Write-Host "(failed to query PRs)" }
}
