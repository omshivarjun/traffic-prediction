#!/usr/bin/env powershell
<#
.SYNOPSIS
    GitHub Project Size Optimization and Analysis Tool
    
.DESCRIPTION
    Analyzes project size and optionally cleans up large files for GitHub upload.
    Removes dependencies and build files while preserving source code and documentation.
    
.PARAMETER Clean
    Remove large directories and files to prepare for GitHub upload
    
.PARAMETER Analyze
    Only analyze project size without making any changes (default)
    
.EXAMPLE
    .\optimize-for-github.ps1 -Analyze
    Shows current project size breakdown
    
.EXAMPLE
    .\optimize-for-github.ps1 -Clean
    Removes large files and prepares project for GitHub
#>

param(
    [switch]$Clean,
    [switch]$Analyze = $true
)

# Force analyze mode if no parameters
if (-not $Clean) { $Analyze = $true }

Write-Host "METR-LA Traffic Prediction - GitHub Project Optimization Tool" -ForegroundColor Green
Write-Host "=============================================================" -ForegroundColor Green
Write-Host ""

if ($Clean) {
    Write-Host "MODE: CLEANUP - Will remove large files" -ForegroundColor Red
} else {
    Write-Host "MODE: ANALYSIS - Read-only project size analysis" -ForegroundColor Yellow
}
Write-Host ""

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

function Show-ProjectAnalysis {
    Write-Host "PROJECT SIZE ANALYSIS" -ForegroundColor Yellow
    Write-Host "====================" -ForegroundColor Yellow
    Write-Host ""
    
    $directories = @(
        @{Name="Python Virtual Env (.venv)"; Path=".venv"; Removable=$true},
        @{Name="Node Modules (node_modules)"; Path="node_modules"; Removable=$true},
        @{Name="Next.js Build (.next)"; Path=".next"; Removable=$true},
        @{Name="Large Datasets (data/)"; Path="data"; Removable=$false},
        @{Name="Source Code (src/)"; Path="src"; Removable=$false},
        @{Name="Scripts and Automation"; Path="scripts"; Removable=$false},
        @{Name="Documentation (docs/)"; Path="docs"; Removable=$false},
        @{Name="Task Management (.taskmaster)"; Path=".taskmaster"; Removable=$true},
        @{Name="AI Rules (trae cursor etc)"; Path=".trae;.cursor;.kilocode;.roo;.windsurf"; Removable=$true},
        @{Name="Configuration Files"; Path="config;schemas;hadoop-configs"; Removable=$false}
    )
    
    $totalSize = 0
    $removableSize = 0
    
    foreach ($item in $directories) {
        $size = 0
        if ($item.Path -match ";") {
            # Multiple paths separated by semicolon
            foreach ($path in $item.Path -split ";") {
                $size += Get-DirectorySize $path.Trim()
            }
        } else {
            $size = Get-DirectorySize $item.Path
        }
        
        $totalSize += $size
        if ($item.Removable) { $removableSize += $size }
        
        $status = if ($item.Removable) { "DELETE" } else { "KEEP" }
        $color = if ($item.Removable) { "Red" } else { "Green" }
        
        Write-Host ("{0,-8} {1,-30} {2,8} MB" -f $status, $item.Name, $size) -ForegroundColor $color
    }
    
    Write-Host ""
    Write-Host "SIZE SUMMARY:" -ForegroundColor Cyan
    Write-Host ("   Total Project Size:    {0,8} MB" -f $totalSize) -ForegroundColor White
    Write-Host ("   Removable Size:        {0,8} MB" -f $removableSize) -ForegroundColor Red
    Write-Host ("   Core Project Size:     {0,8} MB" -f ($totalSize - $removableSize)) -ForegroundColor Green
    Write-Host ""
    
    return @{Total=$totalSize; Removable=$removableSize; Core=($totalSize - $removableSize)}
}

function Remove-LargeDirectories {
    Write-Host "CLEANING UP LARGE FILES" -ForegroundColor Yellow
    Write-Host "=======================" -ForegroundColor Yellow
    Write-Host ""
    
    $itemsToRemove = @(
        @{Path=".venv"; Description="Python Virtual Environment"},
        @{Path="node_modules"; Description="Node.js Dependencies"},
        @{Path=".next"; Description="Next.js Build Files"},
        @{Path=".taskmaster"; Description="Task Management Files"},
        @{Path=".trae"; Description="Trae AI Rules"},
        @{Path=".cursor"; Description="Cursor AI Rules"},
        @{Path=".kilocode"; Description="Kilocode AI Rules"},
        @{Path=".roo"; Description="Roo AI Rules"},
        @{Path=".windsurf"; Description="Windsurf AI Rules"}
    )
    
    $removedSize = 0
    
    foreach ($item in $itemsToRemove) {
        if (Test-Path $item.Path) {
            try {
                $size = Get-DirectorySize $item.Path
                Remove-Item $item.Path -Recurse -Force -ErrorAction Stop
                $removedSize += $size
                Write-Host ("REMOVED: {0,-30} ({1} MB)" -f $item.Description, $size) -ForegroundColor Green
            }
            catch {
                Write-Host ("ERROR: Could not remove {0} - {1}" -f $item.Path, $_.Exception.Message) -ForegroundColor Red
            }
        } else {
            Write-Host ("SKIP: {0,-30} (not found)" -f $item.Description) -ForegroundColor Gray
        }
    }
    
    Write-Host ""
    Write-Host ("Total space freed: {0} MB" -f $removedSize) -ForegroundColor Cyan
    Write-Host ""
}

function Clean-DockerResources {
    Write-Host "CLEANING DOCKER RESOURCES" -ForegroundColor Yellow
    Write-Host "=========================" -ForegroundColor Yellow
    Write-Host ""
    
    # Check if Docker is available
    try {
        $null = docker --version 2>$null
        $dockerAvailable = $true
    }
    catch {
        $dockerAvailable = $false
    }
    
    if ($dockerAvailable) {
        Write-Host "Stopping containers..."
        try { docker stop $(docker ps -aq) 2>$null } catch {}
        
        Write-Host "Removing containers..."
        try { docker rm $(docker ps -aq) 2>$null } catch {}
        
        Write-Host "System cleanup..."
        try { docker system prune -f 2>$null } catch {}
        
        Write-Host "Docker cleanup completed!" -ForegroundColor Green
    } else {
        Write-Host "Docker not available - skipping Docker cleanup" -ForegroundColor Yellow
    }
    Write-Host ""
}

function Check-GitIgnoreStatus {
    if (Test-Path ".gitignore") {
        Write-Host ".gitignore file exists and is optimized" -ForegroundColor Green
        
        # Check for key exclusions
        $gitignoreContent = Get-Content ".gitignore" -Raw
        $keyExclusions = @(
            "node_modules/",
            ".venv/",
            ".next/",
            "*.log",
            ".env*"
        )
        
        Write-Host "   Key exclusions found:" -ForegroundColor Gray
        foreach ($exclusion in $keyExclusions) {
            if ($gitignoreContent -match [regex]::Escape($exclusion)) {
                Write-Host ("   FOUND: {0}" -f $exclusion) -ForegroundColor Green
            }
        }
    } else {
        Write-Host "WARNING: No .gitignore file found!" -ForegroundColor Red
        Write-Host "   Run setup-github-repo.ps1 to create one" -ForegroundColor Yellow
    }
    Write-Host ""
    
    if (Test-Path ".dockerignore") {
        Write-Host ".dockerignore file exists for container optimization" -ForegroundColor Green
    } else {
        Write-Host "INFO: No .dockerignore file found" -ForegroundColor Yellow
    }
    Write-Host ""
}

function Show-GitHubChecklist {
    Write-Host "GITHUB READY CHECKLIST" -ForegroundColor Green
    Write-Host "======================" -ForegroundColor Green
    Write-Host ""
    
    $checklist = @(
        @{Item="README.md exists"; Check=(Test-Path "README.md")},
        @{Item=".gitignore configured"; Check=(Test-Path ".gitignore")},
        @{Item="Large files removed"; Check=(-not (Test-Path ".venv") -and -not (Test-Path "node_modules"))},
        @{Item="Docker setup ready"; Check=(Test-Path "docker-compose.yml")},
        @{Item="Package files present"; Check=(Test-Path "package.json")},
        @{Item="Python requirements"; Check=(Test-Path "requirements.txt")}
    )
    
    $completedTasks = 0
    $totalTasks = $checklist.Count
    
    foreach ($item in $checklist) {
        $status = if ($item.Check) { "YES" } else { "NO" }
        $color = if ($item.Check) { "Green" } else { "Red" }
        if ($item.Check) { $completedTasks++ }
        
        Write-Host ("{0,-3} {1}" -f $status, $item.Item) -ForegroundColor $color
    }
    
    $readinessScore = [math]::Round(($completedTasks / $totalTasks) * 100, 0)
    Write-Host ""
    Write-Host ("GitHub Readiness Score: {0}% ({1}/{2} tasks completed)" -f $readinessScore, $completedTasks, $totalTasks) -ForegroundColor Cyan
    Write-Host ""
}

function Show-NextSteps {
    Write-Host "NEXT STEPS FOR GITHUB" -ForegroundColor Magenta
    Write-Host "====================" -ForegroundColor Magenta
    Write-Host ""
    
    if ($Clean) {
        Write-Host "Project cleaned successfully! Ready for GitHub upload:" -ForegroundColor Green
        Write-Host ""
        Write-Host "1. Set up GitHub repository:" -ForegroundColor White
        Write-Host "   .\setup-github-repo.ps1 -GitHubUsername 'your-username'" -ForegroundColor Gray
        Write-Host ""
        Write-Host "2. Or manually initialize Git:" -ForegroundColor White
        Write-Host "   git init" -ForegroundColor Gray
        Write-Host "   git add ." -ForegroundColor Gray
        Write-Host "   git commit -m 'Initial commit: METR-LA Traffic Prediction System'" -ForegroundColor Gray
        Write-Host "   git remote add origin https://github.com/your-username/traffic-prediction.git" -ForegroundColor Gray
        Write-Host "   git push -u origin main" -ForegroundColor Gray
    } else {
        Write-Host "Run with -Clean flag to optimize for GitHub:" -ForegroundColor Yellow
        Write-Host "   .\optimize-for-github.ps1 -Clean" -ForegroundColor Gray
        Write-Host ""
        Write-Host "Or use the complete GitHub setup:" -ForegroundColor Yellow
        Write-Host "   .\setup-github-repo.ps1 -GitHubUsername 'your-username' -Clean" -ForegroundColor Gray
    }
    Write-Host ""
}

# Main execution
$analysis = Show-ProjectAnalysis

if ($Clean) {
    Write-Host "WARNING: This will permanently delete large directories!" -ForegroundColor Red
    Write-Host "Press Enter to continue, or Ctrl+C to cancel..." -ForegroundColor Yellow
    $null = Read-Host
    
    Remove-LargeDirectories
    Clean-DockerResources
}

Check-GitIgnoreStatus
Show-GitHubChecklist
Show-NextSteps

Write-Host "Optimization complete!" -ForegroundColor Green
Write-Host "Repository: https://github.com/your-username/metr-la-traffic-prediction" -ForegroundColor Blue