$ErrorActionPreference = "Stop"

# ============================================================
# Retail Banking Copilot Release Script
# ============================================================

$ChartDir   = ".\charts\retail-banking-copilot"
$ChartFile  = Join-Path $ChartDir "Chart.yaml"
$ValuesFile = Join-Path $ChartDir "values.yaml"
$DistDir    = ".\dist"

$DockerRepo = "vinchar/retail-banking-copilot"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Retail Banking Copilot Release" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ------------------------------------------------------------
# Check prerequisites
# ------------------------------------------------------------

Write-Host "[1/8] Checking prerequisites..." -ForegroundColor Yellow

if (-not (Test-Path $ChartFile)) {
    throw "Chart.yaml not found: $ChartFile"
}

if (-not (Test-Path $ValuesFile)) {
    throw "values.yaml not found: $ValuesFile"
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is not installed or not available in PATH."
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is not installed or not available in PATH."
}

if (-not (Get-Command tar -ErrorAction SilentlyContinue)) {
    throw "tar is not available. Windows 10/11 normally includes tar."
}

# ------------------------------------------------------------
# Check Git working tree
# ------------------------------------------------------------

Write-Host "[2/8] Checking Git working tree..." -ForegroundColor Yellow

$gitStatus = git status --porcelain

if ($gitStatus) {
    Write-Host ""
    Write-Host "WARNING: You have uncommitted changes:" -ForegroundColor Red
    Write-Host $gitStatus
    Write-Host ""

    $answer = Read-Host "Continue and include these changes in the release? (y/N)"

    if ($answer -ne "y" -and $answer -ne "Y") {
        Write-Host "Release cancelled."
        exit 1
    }
}

# ------------------------------------------------------------
# Read current version
# ------------------------------------------------------------

Write-Host "[3/8] Reading current version..." -ForegroundColor Yellow

$chartContent = Get-Content $ChartFile -Raw

$versionMatch = [regex]::Match(
    $chartContent,
    '(?m)^version:\s*(\d+)\.(\d+)\.(\d+)\s*$'
)

if (-not $versionMatch.Success) {
    throw "Could not find a valid Chart.yaml version."
}

$major = [int]$versionMatch.Groups[1].Value
$minor = [int]$versionMatch.Groups[2].Value
$patch = [int]$versionMatch.Groups[3].Value

$currentVersion = "$major.$minor.$patch"

# Increment PATCH
$newPatch = $patch + 1
$newVersion = "$major.$minor.$newPatch"

Write-Host ""
Write-Host "Current version : $currentVersion" -ForegroundColor Gray
Write-Host "New version     : $newVersion" -ForegroundColor Green
Write-Host ""

$answer = Read-Host "Release version $newVersion? (Y/n)"

if ($answer -eq "n" -or $answer -eq "N") {
    Write-Host "Release cancelled."
    exit 0
}

# ------------------------------------------------------------
# Update Chart.yaml
# ------------------------------------------------------------

Write-Host "[4/8] Updating version files..." -ForegroundColor Yellow

$chartContent = $chartContent -replace `
    "(?m)^version:\s*\d+\.\d+\.\d+\s*$", `
    "version: $newVersion"

$chartContent = $chartContent -replace `
    '(?m)^appVersion:\s*["'']?\d+\.\d+\.\d+["'']?\s*$', `
    "appVersion: `"$newVersion`""

Set-Content -Path $ChartFile -Value $chartContent -NoNewline

# Update Docker image tag in values.yaml
$valuesContent = Get-Content $ValuesFile -Raw

$valuesContent = $valuesContent -replace `
    '(?m)^(\s*tag:\s*)\d+\.\d+\.\d+\s*$', `
    "`${1}$newVersion"

Set-Content -Path $ValuesFile -Value $valuesContent -NoNewline

Write-Host "Updated:" -ForegroundColor Green
Write-Host "  Chart.yaml  -> $newVersion"
Write-Host "  values.yaml -> image tag $newVersion"

# ------------------------------------------------------------
# Build Docker image
# ------------------------------------------------------------

Write-Host ""
Write-Host "[5/8] Building Docker image..." -ForegroundColor Yellow

$dockerImage = "${DockerRepo}:${newVersion}"

docker build -t $dockerImage .

if ($LASTEXITCODE -ne 0) {
    throw "Docker build failed."
}

# ------------------------------------------------------------
# Push Docker image
# ------------------------------------------------------------

Write-Host ""
Write-Host "[6/8] Pushing Docker image..." -ForegroundColor Yellow

docker push $dockerImage

if ($LASTEXITCODE -ne 0) {
    throw "Docker push failed."
}

Write-Host ""
Write-Host "Docker image pushed:" -ForegroundColor Green
Write-Host "  $dockerImage"

# ------------------------------------------------------------
# Create Helm chart package WITHOUT Helm
# ------------------------------------------------------------

Write-Host ""
Write-Host "[7/8] Creating Helm chart package..." -ForegroundColor Yellow

New-Item -ItemType Directory -Force -Path $DistDir | Out-Null

$packageFile = Join-Path $DistDir "retail-banking-copilot-$newVersion.tgz"

# Remove package if it already exists
if (Test-Path $packageFile) {
    Remove-Item $packageFile -Force
}

tar -czf $packageFile -C ".\charts" "retail-banking-copilot"

if ($LASTEXITCODE -ne 0) {
    throw "Failed to create chart package."
}

Write-Host "Created:" -ForegroundColor Green
Write-Host "  $packageFile"

# ------------------------------------------------------------
# Verify package structure
# ------------------------------------------------------------

Write-Host ""
Write-Host "Verifying package structure..." -ForegroundColor Yellow

$archiveContents = tar -tzf $packageFile

if ($LASTEXITCODE -ne 0) {
    throw "Could not read generated chart package."
}

if ($archiveContents -notmatch "^retail-banking-copilot/Chart.yaml") {
    throw "Chart package structure is invalid."
}

if ($archiveContents -notmatch "^retail-banking-copilot/values.yaml") {
    throw "Chart package is missing values.yaml."
}

Write-Host "Package structure OK." -ForegroundColor Green

# ------------------------------------------------------------
# Git diff
# ------------------------------------------------------------

Write-Host ""
Write-Host "[8/8] Preparing Git release..." -ForegroundColor Yellow

Write-Host ""
Write-Host "Changed files:" -ForegroundColor Cyan

git status --short

Write-Host ""
Write-Host "Version changes:" -ForegroundColor Cyan

git diff -- `
    $ChartFile `
    $ValuesFile

Write-Host ""
git diff --check

if ($LASTEXITCODE -ne 0) {
    throw "Git diff --check failed."
}

# ------------------------------------------------------------
# Commit
# ------------------------------------------------------------

Write-Host ""
$answer = Read-Host "Commit and push release $newVersion to main? (Y/n)"

if ($answer -eq "n" -or $answer -eq "N") {
    Write-Host ""
    Write-Host "Release files are ready but NOT committed." -ForegroundColor Yellow
    Write-Host ""
    exit 0
}

git add $ChartFile
git add $ValuesFile
git add $packageFile

git commit -m "Release $newVersion"

if ($LASTEXITCODE -ne 0) {
    throw "Git commit failed."
}

git push origin main

if ($LASTEXITCODE -ne 0) {
    throw "Git push failed."
}

# ------------------------------------------------------------
# Done
# ------------------------------------------------------------

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host " RELEASE $newVersion COMPLETE" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Docker image:"
Write-Host "  $dockerImage"
Write-Host ""
Write-Host "Helm package:"
Write-Host "  $packageFile"
Write-Host ""
Write-Host "Git:"
Write-Host "  Pushed to origin/main"
Write-Host ""