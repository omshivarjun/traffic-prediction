#!/usr/bin/env powershell
<#
.SYNOPSIS
    GitHub Project Size Analysis and Quick Setup Guide
    
.DESCRIPTION
    Quick analysis of project size and readiness for GitHub upload.
    Provides immediate feedback on what needs to be done.
#>

Write-Host "GitHub METR-LA Traffic Prediction - GitHub Readiness Check" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host ""

# Check current project size
function Get-DirectorySize {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return 0 }
    try {
        $size = (Get-ChildItem $Path -Recurse -File -ErrorAction SilentlyContinue | 
                 Measure-Object -Property Length -Sum).Sum
        return [math]::Round($size / 1MB, 2)
    }
    catch { return 0 }
}

Write-Host "CURRENT PROJECT SIZE ANALYSIS:" -ForegroundColor Yellow
Write-Host ""

$directories = @{
    "Virtual Environment (.venv)" = ".venv"
    "Node Modules (node_modules)" = "node_modules" 
    "Next.js Build (.next)" = ".next"
    "Data Files (data/)" = "data"
    "Source Code (src/)" = "src"
    "Documentation (docs/)" = "docs"
    "Scripts" = "scripts"
    "Task Management (.taskmaster)" = ".taskmaster"
}

$totalSize = 0
$canRemove = 0

foreach ($dir in $directories.GetEnumerator()) {
    $size = Get-DirectorySize $dir.Value
    $totalSize += $size
    
    if ($dir.Value -in @(".venv", "node_modules", ".next", ".taskmaster")) {
        $canRemove += $size
        $indicator = "DELETE"
        $color = "Red"
    }
    elseif ($dir.Value -eq "data") {
        $indicator = "WARNING"
        $color = "Yellow" 
    }
    else {
        $indicator = "KEEP"
        $color = "Green"
    }
    
    Write-Host ("{0} {1,-30} {2,8} MB" -f $indicator, $dir.Key, $size) -ForegroundColor $color
}

Write-Host ""
Write-Host "SIZE SUMMARY:" -ForegroundColor Cyan
Write-Host ("   Current Total Size:    {0,8} MB" -f $totalSize) -ForegroundColor White
Write-Host ("   Can Be Removed:        {0,8} MB" -f $canRemove) -ForegroundColor Red  
Write-Host ("   Core Project Size:     {0,8} MB" -f ($totalSize - $canRemove)) -ForegroundColor Green
Write-Host ""

# GitHub recommendations
if ($totalSize -gt 1000) {
    Write-Host "PROJECT TOO LARGE FOR GITHUB!" -ForegroundColor Red
    Write-Host "   Recommended: Run cleanup before uploading" -ForegroundColor Red
}
elseif ($canRemove -gt 100) {
    Write-Host "PROJECT CAN BE OPTIMIZED" -ForegroundColor Yellow
    Write-Host "   Recommended: Run cleanup to reduce size" -ForegroundColor Yellow
}
else {
    Write-Host "PROJECT SIZE IS GITHUB-FRIENDLY" -ForegroundColor Green
}

Write-Host ""
Write-Host "QUICK ACTIONS:" -ForegroundColor Magenta
Write-Host ""
Write-Host "1. Clean up large files:" -ForegroundColor White
Write-Host "   .\optimize-for-github.ps1 -Clean" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Analyze project only:" -ForegroundColor White  
Write-Host "   .\optimize-for-github.ps1 -Analyze" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Complete GitHub setup:" -ForegroundColor White
Write-Host "   .\setup-github-repo.ps1 -GitHubUsername your-username -Clean" -ForegroundColor Gray
Write-Host ""

# Check if .gitignore exists
Write-Host "FILE STATUS:" -ForegroundColor Yellow
Write-Host ""

$files = @{
    "README.md" = "Comprehensive project documentation"
    ".gitignore" = "Excludes large files and dependencies"
    ".dockerignore" = "Optimizes Docker container size"  
    "docker-compose.yml" = "Container orchestration"
    "package.json" = "Node.js dependencies"
    "requirements.txt" = "Python dependencies"
}

foreach ($file in $files.GetEnumerator()) {
    if (Test-Path $file.Key) {
        Write-Host ("FOUND {0,-20} - {1}" -f $file.Key, $file.Value) -ForegroundColor Green
    }
    else {
        Write-Host ("MISSING {0,-20} - {1}" -f $file.Key, $file.Value) -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "GITHUB REPOSITORY HIGHLIGHTS:" -ForegroundColor Cyan
Write-Host ""
Write-Host "- Real-time traffic prediction system" -ForegroundColor Gray
Write-Host "- 99.96% ML accuracy (Random Forest)" -ForegroundColor Gray
Write-Host "- Big Data pipeline: Kafka -> Spark -> Hadoop" -ForegroundColor Gray  
Write-Host "- Interactive dashboard with 207 LA traffic sensors" -ForegroundColor Gray
Write-Host "- Production-ready with Docker Compose" -ForegroundColor Gray
Write-Host "- Real-time processing: <5 second latency" -ForegroundColor Gray
Write-Host ""

Write-Host "Perfect for showcasing in your portfolio!" -ForegroundColor Green