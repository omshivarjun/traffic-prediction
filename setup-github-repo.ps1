#!/usr/bin/env powershell
<#
.SYNOPSIS
    Complete GitHub Setup and Deployment Script
    
.DESCRIPTION
    Automates the complete process of preparing and uploading the traffic prediction project to GitHub:
    - Project optimization and cleanup
    - Git repository initialization
    - GitHub repository creation assistance
    - Automated commit and push process
    
.PARAMETER GitHubUsername
    Your GitHub username (required for remote setup)
    
.PARAMETER RepositoryName
    Name for the GitHub repository (default: traffic-prediction)
    
.PARAMETER Clean
    Perform aggressive cleanup before git operations
    
.PARAMETER SkipCleanup
    Skip the cleanup phase and proceed directly to git operations
    
.EXAMPLE
    .\setup-github-repo.ps1 -GitHubUsername "myusername" -Clean
    .\setup-github-repo.ps1 -GitHubUsername "myusername" -RepositoryName "my-traffic-project"
#>

param(
    [Parameter(Mandatory=$false)]
    [string]$GitHubUsername,
    
    [string]$RepositoryName = "traffic-prediction",
    
    [switch]$Clean,
    
    [switch]$SkipCleanup
)

$ErrorActionPreference = "Stop"
$startTime = Get-Date

# Colors for output
$colors = @{
    Header = "Magenta"
    Success = "Green" 
    Warning = "Yellow"
    Error = "Red"
    Info = "Cyan"
    Gray = "Gray"
}

function Write-Header {
    param([string]$Text)
    Write-Host ""
    Write-Host $Text -ForegroundColor $colors.Header
    Write-Host ("=" * $Text.Length) -ForegroundColor $colors.Header
}

function Write-Step {
    param([string]$Text, [string]$Color = "Info")
    Write-Host "🔸 $Text" -ForegroundColor $colors[$Color]
}

function Write-Success {
    param([string]$Text)
    Write-Host "✅ $Text" -ForegroundColor $colors.Success
}

function Write-Warning {
    param([string]$Text)
    Write-Host "⚠️  $Text" -ForegroundColor $colors.Warning
}

function Write-Error {
    param([string]$Text)
    Write-Host "❌ $Text" -ForegroundColor $colors.Error
}

function Test-Command {
    param([string]$Command)
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Initialize-GitRepository {
    Write-Header "INITIALIZING GIT REPOSITORY"
    
    if (Test-Path ".git") {
        Write-Warning "Git repository already exists"
        return $true
    }
    
    try {
        Write-Step "Initializing Git repository..."
        git init
        
        Write-Step "Setting default branch to 'main'..."
        git branch -M main
        
        Write-Success "Git repository initialized successfully"
        return $true
    }
    catch {
        Write-Error "Failed to initialize Git repository: $_"
        return $false
    }
}

function Add-FilesToGit {
    Write-Header "ADDING FILES TO GIT"
    
    try {
        Write-Step "Adding all files to staging area..."
        git add .
        
        # Check what's being added
        $stagedFiles = git diff --cached --name-only
        $fileCount = ($stagedFiles | Measure-Object).Count
        
        Write-Success "$fileCount files staged for commit"
        
        # Show some key files being added
        Write-Step "Key files included:"
        $keyFiles = @("README.md", "docker-compose.yml", "package.json", "requirements.txt")
        foreach ($file in $keyFiles) {
            if (Test-Path $file) {
                Write-Host "   ✅ $file" -ForegroundColor $colors.Success
            }
            else {
                Write-Host "   ❌ $file (missing)" -ForegroundColor $colors.Error
            }
        }
        
        return $true
    }
    catch {
        Write-Error "Failed to add files to Git: $_"
        return $false
    }
}

function Create-InitialCommit {
    Write-Header "CREATING INITIAL COMMIT"
    
    try {
        $commitMessage = "Initial commit: METR-LA Traffic Prediction System

🚦 Complete real-time traffic prediction pipeline featuring:
• Machine Learning: 99.96% accuracy traffic forecasting
• Big Data: Kafka + Spark + Hadoop ecosystem
• Real-time Dashboard: Next.js with interactive maps
• Production Ready: Docker Compose with 10+ services
• Monitoring: Comprehensive observability suite

Technologies: Next.js 15, FastAPI, Apache Kafka, Spark MLlib, Hadoop HDFS
Dataset: METR-LA (207 traffic sensors, Los Angeles area)
Performance: <5 second end-to-end latency, 5-8 records/sec throughput"

        Write-Step "Creating initial commit..."
        git commit -m $commitMessage
        
        Write-Success "Initial commit created successfully"
        return $true
    }
    catch {
        Write-Error "Failed to create initial commit: $_"
        return $false
    }
}

function Add-GitHubRemote {
    param([string]$Username, [string]$RepoName)
    
    Write-Header "CONFIGURING GITHUB REMOTE"
    
    if (-not $Username) {
        Write-Error "GitHub username is required for remote setup"
        Write-Step "Please run: .\setup-github-repo.ps1 -GitHubUsername 'your-username'"
        return $false
    }
    
    $remoteUrl = "https://github.com/$Username/$RepoName.git"
    
    try {
        # Check if remote already exists
        $existingRemote = git remote get-url origin 2>$null
        if ($existingRemote) {
            Write-Warning "Remote 'origin' already exists: $existingRemote"
            
            Write-Step "Updating remote URL..."
            git remote set-url origin $remoteUrl
        }
        else {
            Write-Step "Adding GitHub remote..."
            git remote add origin $remoteUrl
        }
        
        Write-Success "GitHub remote configured: $remoteUrl"
        return $true
    }
    catch {
        Write-Error "Failed to configure GitHub remote: $_"
        return $false
    }
}

function Show-GitHubInstructions {
    param([string]$Username, [string]$RepoName)
    
    Write-Header "GITHUB REPOSITORY CREATION"
    
    if ($Username) {
        $repoUrl = "https://github.com/$Username/$RepoName"
        Write-Step "Repository will be created at: $repoUrl"
    }
    
    Write-Host ""
    Write-Host "📝 STEP-BY-STEP GITHUB SETUP:" -ForegroundColor $colors.Info
    Write-Host ""
    
    Write-Host "1. 🌐 Create Repository on GitHub:" -ForegroundColor White
    Write-Host "   • Go to: https://github.com/new" -ForegroundColor $colors.Gray
    Write-Host "   • Repository name: $RepoName" -ForegroundColor $colors.Gray
    Write-Host "   • Description: Real-time traffic prediction using ML and big data" -ForegroundColor $colors.Gray
    Write-Host "   • Visibility: Public (recommended for portfolio)" -ForegroundColor $colors.Gray
    Write-Host "   • ❌ DO NOT initialize with README (we have our own)" -ForegroundColor $colors.Gray
    Write-Host "   • ❌ DO NOT add .gitignore (we have optimized one)" -ForegroundColor $colors.Gray
    Write-Host ""
    
    Write-Host "2. 📤 Push to GitHub (run after creating repository):" -ForegroundColor White
    Write-Host "   git push -u origin main" -ForegroundColor $colors.Gray
    Write-Host ""
    
    Write-Host "3. 🏷️  Add Repository Topics (in GitHub settings):" -ForegroundColor White
    Write-Host "   machine-learning, big-data, kafka, apache-spark, hadoop, traffic-prediction," -ForegroundColor $colors.Gray
    Write-Host "   real-time-analytics, nextjs, fastapi, docker, streaming-data" -ForegroundColor $colors.Gray
    Write-Host ""
    
    Write-Host "4. 📋 Repository Settings (recommended):" -ForegroundColor White
    Write-Host "   • Enable Issues and Projects" -ForegroundColor $colors.Gray
    Write-Host "   • Enable Discussions for community" -ForegroundColor $colors.Gray
    Write-Host "   • Set up branch protection rules for main branch" -ForegroundColor $colors.Gray
    Write-Host ""
}

function Push-ToGitHub {
    param([string]$Username, [string]$RepoName)
    
    Write-Header "PUSHING TO GITHUB"
    
    if (-not $Username) {
        Write-Warning "Cannot push without GitHub username"
        Show-GitHubInstructions $Username $RepoName
        return $false
    }
    
    Write-Step "Attempting to push to GitHub..."
    Write-Host "   Remote: https://github.com/$Username/$RepoName.git" -ForegroundColor $colors.Gray
    Write-Host ""
    
    try {
        # Test if repository exists by trying to fetch
        git ls-remote origin HEAD 2>$null | Out-Null
        $repoExists = $LASTEXITCODE -eq 0
        
        if (-not $repoExists) {
            Write-Warning "GitHub repository does not exist yet"
            Write-Step "Please create the repository first:"
            Show-GitHubInstructions $Username $RepoName
            
            Write-Host ""
            Write-Host "🎯 QUICK CREATION LINK:" -ForegroundColor $colors.Info
            Write-Host "https://github.com/new?name=$RepoName&description=Real-time+traffic+prediction+using+ML+and+big+data" -ForegroundColor $colors.Gray
            
            return $false
        }
        
        Write-Step "Repository exists, pushing to main branch..."
        git push -u origin main
        
        Write-Success "Successfully pushed to GitHub!"
        Write-Host "   Repository: https://github.com/$Username/$RepoName" -ForegroundColor $colors.Info
        
        return $true
    }
    catch {
        Write-Error "Failed to push to GitHub: $_"
        Write-Warning "This might be because:"
        Write-Host "   • Repository doesn't exist on GitHub" -ForegroundColor $colors.Gray
        Write-Host "   • Authentication issues (check GitHub credentials)" -ForegroundColor $colors.Gray
        Write-Host "   • Network connectivity problems" -ForegroundColor $colors.Gray
        
        return $false
    }
}

function Show-PostSetupTasks {
    param([string]$Username, [string]$RepoName)
    
    Write-Header "POST-SETUP TASKS"
    
    if ($Username) {
        $repoUrl = "https://github.com/$Username/$RepoName"
        Write-Host "🌐 Repository URL: $repoUrl" -ForegroundColor $colors.Info
        Write-Host ""
    }
    
    Write-Host "🎯 IMMEDIATE NEXT STEPS:" -ForegroundColor $colors.Success
    Write-Host ""
    
    Write-Host "1. 📝 Update Repository Description and Topics" -ForegroundColor White
    Write-Host "2. 🖼️  Add social preview image (repository settings)" -ForegroundColor White
    Write-Host "3. 📄 Create GitHub Pages (optional) for project documentation" -ForegroundColor White
    Write-Host "4. 🔗 Add repository link to your portfolio/LinkedIn" -ForegroundColor White
    Write-Host ""
    
    Write-Host "🚀 OPTIONAL ENHANCEMENTS:" -ForegroundColor $colors.Info
    Write-Host ""
    Write-Host "• 🏷️  Create release tags for major versions" -ForegroundColor $colors.Gray
    Write-Host "• 🤖 Set up GitHub Actions for CI/CD" -ForegroundColor $colors.Gray
    Write-Host "• 📊 Add code quality badges (CodeCov, etc.)" -ForegroundColor $colors.Gray
    Write-Host "• 🐛 Configure issue templates" -ForegroundColor $colors.Gray
    Write-Host "• 👥 Add contributing guidelines" -ForegroundColor $colors.Gray
    Write-Host "• 📜 Add license file" -ForegroundColor $colors.Gray
    Write-Host ""
    
    Write-Host "💡 PROJECT SHOWCASE TIPS:" -ForegroundColor $colors.Warning
    Write-Host ""
    Write-Host "• Include live demo screenshots in README" -ForegroundColor $colors.Gray
    Write-Host "• Create architecture diagrams" -ForegroundColor $colors.Gray  
    Write-Host "• Add performance metrics and benchmarks" -ForegroundColor $colors.Gray
    Write-Host "• Document installation and setup process clearly" -ForegroundColor $colors.Gray
    Write-Host "• Include technology stack explanations" -ForegroundColor $colors.Gray
}

function Show-ProjectSummary {
    Write-Header "PROJECT SUMMARY"
    
    Write-Host "📊 TRAFFIC PREDICTION SYSTEM HIGHLIGHTS:" -ForegroundColor $colors.Info
    Write-Host ""
    Write-Host "🎯 Business Impact:" -ForegroundColor White
    Write-Host "   • Real-time traffic prediction for Los Angeles (207 sensors)" -ForegroundColor $colors.Gray
    Write-Host "   • 99.96% ML prediction accuracy (Random Forest)" -ForegroundColor $colors.Gray
    Write-Host "   • <5 second end-to-end processing latency" -ForegroundColor $colors.Gray
    Write-Host ""
    
    Write-Host "🔧 Technical Architecture:" -ForegroundColor White
    Write-Host "   • Big Data Pipeline: Kafka → Spark → Hadoop → Dashboard" -ForegroundColor $colors.Gray
    Write-Host "   • Real-time Processing: 5-8 records/second sustained throughput" -ForegroundColor $colors.Gray
    Write-Host "   • Container Orchestration: 10+ services with Docker Compose" -ForegroundColor $colors.Gray
    Write-Host "   • Modern Stack: Next.js 15, FastAPI, React 19, TailwindCSS 4.0" -ForegroundColor $colors.Gray
    Write-Host ""
    
    Write-Host "🚀 Production Features:" -ForegroundColor White
    Write-Host "   • Interactive dashboard with real-time map visualization" -ForegroundColor $colors.Gray
    Write-Host "   • Comprehensive monitoring suite (6 different UIs)" -ForegroundColor $colors.Gray
    Write-Host "   • Automated deployment scripts and health checks" -ForegroundColor $colors.Gray
    Write-Host "   • Complete documentation and setup guides" -ForegroundColor $colors.Gray
    Write-Host ""
}

# Main execution starts here
Clear-Host

Write-Host "🚀 GITHUB SETUP & DEPLOYMENT TOOL" -ForegroundColor $colors.Header
Write-Host "====================================" -ForegroundColor $colors.Header
Write-Host ""
Write-Host "🎯 Preparing METR-LA Traffic Prediction System for GitHub" -ForegroundColor $colors.Info
Write-Host ("⏰ Start Time: {0}" -f $startTime.ToString("yyyy-MM-dd HH:mm:ss")) -ForegroundColor $colors.Gray
Write-Host ""

# Prerequisites check
Write-Header "CHECKING PREREQUISITES"

if (-not (Test-Command "git")) {
    Write-Error "Git is not installed or not in PATH"
    Write-Host "Please install Git from: https://git-scm.com/download/windows" -ForegroundColor $colors.Info
    exit 1
}
Write-Success "Git is available"

# Cleanup phase
if (-not $SkipCleanup) {
    if ($Clean) {
        Write-Step "Running project optimization with cleanup..."
        .\optimize-for-github.ps1 -Clean
    }
    else {
        Write-Step "Running project analysis (use -Clean for cleanup)..."
        .\optimize-for-github.ps1 -Analyze
    }
    Write-Host ""
}

# Git operations
$gitSuccess = $true

$gitSuccess = $gitSuccess -and (Initialize-GitRepository)
$gitSuccess = $gitSuccess -and (Add-FilesToGit)
$gitSuccess = $gitSuccess -and (Create-InitialCommit)

if ($GitHubUsername) {
    $gitSuccess = $gitSuccess -and (Add-GitHubRemote $GitHubUsername $RepositoryName)
}

# GitHub instructions and push
if ($gitSuccess) {
    if ($GitHubUsername) {
        $pushSuccess = Push-ToGitHub $GitHubUsername $RepositoryName
        if (-not $pushSuccess) {
            Show-GitHubInstructions $GitHubUsername $RepositoryName
        }
    }
    else {
        Show-GitHubInstructions $GitHubUsername $RepositoryName
        Write-Warning "Run with -GitHubUsername parameter to automatically configure remote"
    }
    
    Show-PostSetupTasks $GitHubUsername $RepositoryName
    Show-ProjectSummary
    
    Write-Header "SETUP COMPLETED"
    Write-Success "Your traffic prediction system is ready for GitHub!"
}
else {
    Write-Header "SETUP INCOMPLETE"
    Write-Error "Some steps failed. Please review the errors above and retry."
}

$endTime = Get-Date
$duration = $endTime - $startTime
Write-Host ""
Write-Host ("⏱️  Total execution time: {0:mm\:ss}" -f $duration) -ForegroundColor $colors.Gray
Write-Host ("🏁 End Time: {0}" -f $endTime.ToString("yyyy-MM-dd HH:mm:ss")) -ForegroundColor $colors.Gray