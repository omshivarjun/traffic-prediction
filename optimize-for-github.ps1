#!/usr/bin/env powershell
<#
.SYNOPSIS
    GitHub Project Optimization Script
    
.DESCRIPTION
    Optimizes the traffic prediction project for GitHub by:
    - Removing large datasets and build artifacts
    - Cleaning up Docker volumes and containers
    - Displaying project size analysis
    - Preparing the project for Git repository upload
    
.PARAMETER Clean
    Performs aggressive cleanup (removes all data files)
    
.PARAMETER Analyze
    Only analyzes project size without making changes
    
.EXAMPLE
    .\optimize-for-github.ps1 -Analyze
    .\optimize-for-github.ps1 -Clean
#>

param(
    [switch]$Clean,
    [switch]$Analyze
)

# Set error handling
$ErrorActionPreference = "Continue"
$startTime = Get-Date

Write-Host "🚀 GitHub Project Optimization Tool" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
Write-Host ""

function Get-FolderSize {
    param([string]$Path)
    
    if (-not (Test-Path $Path)) { return 0 }
    
    try {
        $size = (Get-ChildItem $Path -Recurse -File -ErrorAction SilentlyContinue | 
                 Measure-Object -Property Length -Sum).Sum
        return [math]::Round($size / 1MB, 2)
    }
    catch {
        return 0
    }
}

function Show-ProjectAnalysis {
    Write-Host "📊 PROJECT SIZE ANALYSIS" -ForegroundColor Yellow
    Write-Host "=========================" -ForegroundColor Yellow
    
    $analysis = @(
        @{Name="Python Virtual Env (.venv)"; Path=".venv"; Removable=$true},
        @{Name="Node.js Dependencies (node_modules)"; Path="node_modules"; Removable=$true},
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
    
    foreach ($item in $analysis) {
        $paths = $item.Path -split ","
        $itemSize = 0
        
        foreach ($path in $paths) {
            $itemSize += Get-FolderSize $path.Trim()
        }
        
        $totalSize += $itemSize
        if ($item.Removable) { $removableSize += $itemSize }
        
        $status = if ($item.Removable) { "🗑️ Can Remove" } else { "✅ Keep" }
        $color = if ($item.Removable) { "Red" } else { "Green" }
        
        Write-Host ("{0,-35} {1,8} MB  {2}" -f $item.Name, $itemSize, $status) -ForegroundColor $color
    }
    
    Write-Host ""
    Write-Host "📈 SUMMARY:" -ForegroundColor Cyan
    Write-Host ("   Total Project Size:  {0,8} MB" -f $totalSize) -ForegroundColor White
    Write-Host ("   Removable Content:   {0,8} MB" -f $removableSize) -ForegroundColor Red
    Write-Host ("   Core Project Size:   {0,8} MB" -f ($totalSize - $removableSize)) -ForegroundColor Green
    Write-Host ""
    
    return @{Total=$totalSize; Removable=$removableSize; Core=($totalSize - $removableSize)}
}

function Remove-LargeFiles {
    Write-Host "🧹 CLEANING UP LARGE FILES" -ForegroundColor Yellow
    Write-Host "===========================" -ForegroundColor Yellow
    
    $itemsToRemove = @(
        @{Path=".venv"; Description="Python Virtual Environment"},
        @{Path="node_modules"; Description="Node.js Dependencies"},
        @{Path=".next"; Description="Next.js Build Files"},
        @{Path=".taskmaster/tasks"; Description="Task Files"},
        @{Path=".taskmaster/reports"; Description="Task Reports"},
        @{Path=".trae"; Description="AI Assistant Rules"},
        @{Path=".cursor"; Description="Cursor AI Rules"},
        @{Path=".kilocode"; Description="Kilocode Rules"},
        @{Path=".roo"; Description="Roo Rules"},
        @{Path=".windsurf"; Description="Windsurf Rules"},
        @{Path="logs"; Description="Log Files"},
        @{Path="data/processed/*.csv"; Description="Large Processed Data Files"},
        @{Path="data/raw/metr-la/*.pkl"; Description="Large Pickle Files"}
    )
    
    $removedSize = 0
    
    foreach ($item in $itemsToRemove) {
        if (Test-Path $item.Path) {
            $size = Get-FolderSize $item.Path
            
            try {
                if ($item.Path -like "*.*") {
                    # It's a file pattern
                    Remove-Item $item.Path -Force -ErrorAction SilentlyContinue
                }
                else {
                    # It's a directory
                    Remove-Item $item.Path -Recurse -Force -ErrorAction SilentlyContinue
                }
                
                Write-Host ("✅ Removed: {0,-30} ({1} MB)" -f $item.Description, $size) -ForegroundColor Green
                $removedSize += $size
            }
            catch {
                Write-Host ("❌ Failed to remove: {0}" -f $item.Description) -ForegroundColor Red
            }
        }
        else {
            Write-Host ("⏭️  Not found: {0}" -f $item.Description) -ForegroundColor Gray
        }
    }
    
    Write-Host ""
    Write-Host ("💾 Total space freed: {0} MB" -f $removedSize) -ForegroundColor Cyan
    return $removedSize
}

function Clean-DockerResources {
    Write-Host "🐳 CLEANING DOCKER RESOURCES" -ForegroundColor Yellow
    Write-Host "=============================" -ForegroundColor Yellow
    
    try {
        # Stop all containers
        $containers = docker ps -q
        if ($containers) {
            Write-Host "🛑 Stopping running containers..."
            docker stop $containers 2>&1 | Out-Null
        }
        
        # Remove containers
        Write-Host "🗑️  Removing containers..."
        docker container prune -f 2>&1 | Out-Null
        
        # Remove unused volumes
        Write-Host "📦 Removing unused volumes..."
        docker volume prune -f 2>&1 | Out-Null
        
        # Remove unused images
        Write-Host "🖼️  Removing unused images..."
        docker image prune -f 2>&1 | Out-Null
        
        # System cleanup
        Write-Host "🧹 System cleanup..."
        docker system prune -f 2>&1 | Out-Null
        
        Write-Host "✅ Docker cleanup completed!" -ForegroundColor Green
    }
    catch {
        Write-Host "⚠️  Docker not available or error during cleanup" -ForegroundColor Yellow
    }
    Write-Host ""
}

function Show-GitIgnoreStatus {
    Write-Host "📝 GIT IGNORE STATUS" -ForegroundColor Yellow
    Write-Host "====================" -ForegroundColor Yellow
    
    if (Test-Path ".gitignore") {
        Write-Host "✅ .gitignore file exists and is optimized" -ForegroundColor Green
        
        # Check key exclusions
        $gitignoreContent = Get-Content ".gitignore" -Raw
        $keyExclusions = @(
            "node_modules/",
            ".venv/",
            "data/processed/*.csv",
            "*.pkl",
            "*.joblib",
            "logs/"
        )
        
        foreach ($exclusion in $keyExclusions) {
            if ($gitignoreContent -like "*$exclusion*") {
                Write-Host ("   ✅ Excludes: {0}" -f $exclusion) -ForegroundColor Green
            }
            else {
                Write-Host ("   ❌ Missing: {0}" -f $exclusion) -ForegroundColor Red
            }
        }
    }
    else {
        Write-Host "❌ .gitignore file not found!" -ForegroundColor Red
    }
    
    if (Test-Path ".dockerignore") {
        Write-Host "✅ .dockerignore file exists for container optimization" -ForegroundColor Green
    }
    else {
        Write-Host "⚠️  .dockerignore file not found (recommended for Docker optimization)" -ForegroundColor Yellow
    }
    
    Write-Host ""
}

function Show-GitReadyChecklist {
    Write-Host "✅ GITHUB READY CHECKLIST" -ForegroundColor Green
    Write-Host "==========================" -ForegroundColor Green
    
    $checklist = @(
        @{Task="README.md comprehensive and up-to-date"; Check=(Test-Path "README.md")},
        @{Task=".gitignore excludes large files"; Check=(Test-Path ".gitignore")},
        @{Task=".dockerignore optimizes container size"; Check=(Test-Path ".dockerignore")},
        @{Task="Large datasets excluded"; Check=(-not (Test-Path "data/processed/metr_la_processed_data.csv"))},
        @{Task="Virtual environment excluded"; Check=(-not (Test-Path ".venv"))},
        @{Task="Node modules excluded"; Check=(-not (Test-Path "node_modules"))},
        @{Task="Build files excluded"; Check=(-not (Test-Path ".next"))},
        @{Task="Environment files secured"; Check=(Test-Path ".env.example")},
        @{Task="Docker compose configuration"; Check=(Test-Path "docker-compose.yml")},
        @{Task="Essential scripts included"; Check=(Test-Path "scripts")}
    )
    
    foreach ($item in $checklist) {
        $status = if ($item.Check) { "✅" } else { "❌" }
        $color = if ($item.Check) { "Green" } else { "Red" }
        Write-Host ("   {0} {1}" -f $status, $item.Task) -ForegroundColor $color
    }
    
    Write-Host ""
    
    # Calculate readiness score
    $completedTasks = ($checklist | Where-Object { $_.Check }).Count
    $totalTasks = $checklist.Count
    $readinessScore = [math]::Round(($completedTasks / $totalTasks) * 100, 1)
    
    Write-Host ("📊 GitHub Readiness Score: {0}% ({1}/{2} tasks completed)" -f $readinessScore, $completedTasks, $totalTasks) -ForegroundColor Cyan
}

function Show-NextSteps {
    Write-Host "🚀 NEXT STEPS FOR GITHUB" -ForegroundColor Magenta
    Write-Host "=========================" -ForegroundColor Magenta
    
    Write-Host "1. 🔧 Initialize Git Repository:" -ForegroundColor White
    Write-Host "   git init" -ForegroundColor Gray
    Write-Host "   git add ." -ForegroundColor Gray
    Write-Host '   git commit -m "Initial commit: METR-LA Traffic Prediction System"' -ForegroundColor Gray
    Write-Host ""
    
    Write-Host "2. 🌐 Create GitHub Repository:" -ForegroundColor White
    Write-Host "   - Go to github.com/new" -ForegroundColor Gray
    Write-Host "   - Repository name: traffic-prediction" -ForegroundColor Gray
    Write-Host "   - Add description: Real-time traffic prediction using ML and big data" -ForegroundColor Gray
    Write-Host "   - Make it public (or private)" -ForegroundColor Gray
    Write-Host ""
    
    Write-Host "3. 📤 Push to GitHub:" -ForegroundColor White
    Write-Host "   git remote add origin https://github.com/yourusername/traffic-prediction.git" -ForegroundColor Gray
    Write-Host "   git branch -M main" -ForegroundColor Gray
    Write-Host "   git push -u origin main" -ForegroundColor Gray
    Write-Host ""
    
    Write-Host "4. 📝 Add Repository Topics (GitHub):" -ForegroundColor White
    Write-Host "   machine-learning, big-data, kafka, spark, hadoop, traffic-prediction, real-time" -ForegroundColor Gray
    Write-Host ""
    
    Write-Host "5. 🏷️  Create Release (Optional):" -ForegroundColor White
    Write-Host "   - Tag: v1.0.0" -ForegroundColor Gray
    Write-Host "   - Title: Initial Release - Complete Traffic Prediction System" -ForegroundColor Gray
    Write-Host ""
}

# Main execution
Write-Host ("Start Time: {0}" -f $startTime.ToString("yyyy-MM-dd HH:mm:ss")) -ForegroundColor Gray
Write-Host ""

# Always show analysis
$sizeAnalysis = Show-ProjectAnalysis

if ($Analyze) {
    # Only analysis mode
    Show-GitIgnoreStatus
    Show-GitReadyChecklist
}
elseif ($Clean) {
    # Cleanup mode
    $freedSpace = Remove-LargeFiles
    Clean-DockerResources
    Show-GitIgnoreStatus
    Show-GitReadyChecklist
    
    Write-Host "🎉 CLEANUP COMPLETED!" -ForegroundColor Green
    Write-Host ("   Space freed: {0} MB" -f $freedSpace) -ForegroundColor Cyan
    Write-Host ("   Final project size: ~{0} MB" -f ($sizeAnalysis.Total - $freedSpace)) -ForegroundColor Cyan
}
else {
    # Default mode - show analysis and checklist
    Show-GitIgnoreStatus
    Show-GitReadyChecklist
    
    Write-Host "💡 USAGE:" -ForegroundColor Yellow
    Write-Host "   .\optimize-for-github.ps1 -Clean     # Perform cleanup" -ForegroundColor Gray
    Write-Host "   .\optimize-for-github.ps1 -Analyze   # Analysis only" -ForegroundColor Gray
}

Show-NextSteps

$endTime = Get-Date
$duration = $endTime - $startTime
Write-Host ""
Write-Host ("⏱️  Execution time: {0:mm\:ss} minutes" -f $duration) -ForegroundColor Gray
Write-Host ("End Time: {0}" -f $endTime.ToString("yyyy-MM-dd HH:mm:ss")) -ForegroundColor Gray