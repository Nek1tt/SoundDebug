param([string]$Branch = "release/mvp-2026-08-23")
$ErrorActionPreference = "Stop"

git rev-parse --is-inside-work-tree | Out-Null
if ((git branch --show-current) -ne $Branch) {
    git show-ref --verify --quiet "refs/heads/$Branch"
    if ($LASTEXITCODE -eq 0) { git switch $Branch } else { git switch -c $Branch }
}
git add -A
git status --short
Write-Host "Review the list above, then run:"
Write-Host 'git commit -m "feat: add evidence-based SoundDebug analysis v2"'
Write-Host "git push -u origin $Branch"
Write-Host "Then open a pull request from $Branch into main."
