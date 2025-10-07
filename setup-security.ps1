# ==============================================
# Traffic Prediction System - Security Setup Script
# ==============================================
# This script helps set up secure credentials and Docker secrets
# for production deployment
# ==============================================

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Traffic Prediction - Security Setup" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Check if .env exists
if (Test-Path ".env") {
    Write-Host "✅ .env file already exists" -ForegroundColor Green
    $overwrite = Read-Host "Do you want to regenerate secrets? (y/N)"
    if ($overwrite -ne "y") {
        Write-Host "Exiting. No changes made." -ForegroundColor Yellow
        exit 0
    }
} else {
    Write-Host "📝 Creating .env from template..." -ForegroundColor Yellow
    if (Test-Path ".env.template") {
        Copy-Item ".env.template" ".env"
        Write-Host "✅ .env created from template" -ForegroundColor Green
    } else {
        Write-Host "❌ .env.template not found!" -ForegroundColor Red
        exit 1
    }
}

# Function to generate random hex string
function New-RandomHex {
    param([int]$Length = 32)
    $bytes = New-Object byte[] $Length
    $rng = [System.Security.Cryptography.RNGCryptoServiceProvider]::new()
    $rng.GetBytes($bytes)
    return [System.BitConverter]::ToString($bytes).Replace("-", "").ToLower()
}

# Function to generate random password
function New-RandomPassword {
    param([int]$Length = 24)
    $chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-_=+"
    $password = -join ((1..$Length) | ForEach-Object { $chars[(Get-Random -Maximum $chars.Length)] })
    return $password
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Step 1: Generate JWT Secrets" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

$jwtSecret = New-RandomHex -Length 32
$jwtRefreshSecret = New-RandomHex -Length 32

Write-Host "✅ Generated JWT_SECRET_KEY: $($jwtSecret.Substring(0, 16))..." -ForegroundColor Green
Write-Host "✅ Generated JWT_REFRESH_SECRET_KEY: $($jwtRefreshSecret.Substring(0, 16))..." -ForegroundColor Green

# Update .env file
(Get-Content ".env") | ForEach-Object {
    $_ -replace "JWT_SECRET_KEY=.*", "JWT_SECRET_KEY=$jwtSecret"
} | Set-Content ".env.tmp"
Move-Item ".env.tmp" ".env" -Force

(Get-Content ".env") | ForEach-Object {
    $_ -replace "JWT_REFRESH_SECRET_KEY=.*", "JWT_REFRESH_SECRET_KEY=$jwtRefreshSecret"
} | Set-Content ".env.tmp"
Move-Item ".env.tmp" ".env" -Force

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Step 2: Database Password" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

Write-Host "Current POSTGRES_PASSWORD in .env: casa1234 (insecure!)" -ForegroundColor Yellow
$generateDbPassword = Read-Host "Generate new PostgreSQL password? (Y/n)"

if ($generateDbPassword -ne "n") {
    $dbPassword = New-RandomPassword -Length 24
    Write-Host "✅ Generated POSTGRES_PASSWORD: $($dbPassword.Substring(0, 8))..." -ForegroundColor Green
    
    # Update all occurrences in .env
    (Get-Content ".env") | ForEach-Object {
        $_ -replace "POSTGRES_PASSWORD=.*", "POSTGRES_PASSWORD=$dbPassword"
    } | Set-Content ".env.tmp"
    Move-Item ".env.tmp" ".env" -Force
    
    # Update DATABASE_URL and ASYNC_DATABASE_URL
    (Get-Content ".env") | ForEach-Object {
        $_ -replace "postgresql://postgres:casa1234@", "postgresql://postgres:$dbPassword@"
    } | Set-Content ".env.tmp"
    Move-Item ".env.tmp" ".env" -Force
    
    (Get-Content ".env") | ForEach-Object {
        $_ -replace "postgresql\+asyncpg://postgres:casa1234@", "postgresql+asyncpg://postgres:$dbPassword@"
    } | Set-Content ".env.tmp"
    Move-Item ".env.tmp" ".env" -Force
} else {
    Write-Host "⚠️  Keeping existing password (not recommended for production)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Step 3: Hive Metastore Password" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

$hivePassword = New-RandomPassword -Length 16
Write-Host "✅ Generated HIVE_METASTORE_PASSWORD: $($hivePassword.Substring(0, 8))..." -ForegroundColor Green

(Get-Content ".env") | ForEach-Object {
    $_ -replace "HIVE_METASTORE_PASSWORD=.*", "HIVE_METASTORE_PASSWORD=$hivePassword"
} | Set-Content ".env.tmp"
Move-Item ".env.tmp" ".env" -Force

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Step 4: Docker Secrets (Optional)" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

$createSecrets = Read-Host "Create Docker secrets files? (Y/n)"

if ($createSecrets -ne "n") {
    # Create secrets directory
    if (-not (Test-Path "secrets")) {
        New-Item -ItemType Directory -Path "secrets" | Out-Null
        Write-Host "✅ Created secrets/ directory" -ForegroundColor Green
    }
    
    # Read current passwords from .env
    $envContent = Get-Content ".env" | Out-String
    $postgresPassword = ($envContent | Select-String 'POSTGRES_PASSWORD=(.+)').Matches.Groups[1].Value
    $jwtSecretFromEnv = ($envContent | Select-String 'JWT_SECRET_KEY=(.+)').Matches.Groups[1].Value
    $jwtRefreshFromEnv = ($envContent | Select-String 'JWT_REFRESH_SECRET_KEY=(.+)').Matches.Groups[1].Value
    
    # Write secrets to files
    Set-Content "secrets\postgres_password.txt" $postgresPassword -NoNewline
    Set-Content "secrets\jwt_secret_key.txt" $jwtSecretFromEnv -NoNewline
    Set-Content "secrets\jwt_refresh_secret_key.txt" $jwtRefreshFromEnv -NoNewline
    
    Write-Host "✅ Created secrets/postgres_password.txt" -ForegroundColor Green
    Write-Host "✅ Created secrets/jwt_secret_key.txt" -ForegroundColor Green
    Write-Host "✅ Created secrets/jwt_refresh_secret_key.txt" -ForegroundColor Green
    
    Write-Host ""
    Write-Host "⚠️  WARNING: Secrets directory contains sensitive data!" -ForegroundColor Yellow
    Write-Host "   Make sure secrets/ is in .gitignore" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Step 5: Production Settings" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

$isProduction = Read-Host "Configure for production environment? (y/N)"

if ($isProduction -eq "y") {
    Write-Host "📝 Updating production settings..." -ForegroundColor Yellow
    
    (Get-Content ".env") | ForEach-Object {
        $_ -replace "ENVIRONMENT=development", "ENVIRONMENT=production" `
           -replace "DEBUG=True", "DEBUG=False" `
           -replace "LOG_LEVEL=INFO", "LOG_LEVEL=WARNING" `
           -replace "SESSION_COOKIE_SECURE=False", "SESSION_COOKIE_SECURE=True"
    } | Set-Content ".env.tmp"
    Move-Item ".env.tmp" ".env" -Force
    
    Write-Host "✅ Production settings applied" -ForegroundColor Green
    Write-Host ""
    Write-Host "⚠️  IMPORTANT: Production checklist:" -ForegroundColor Yellow
    Write-Host "   1. Enable HTTPS for API (SESSION_COOKIE_SECURE=True requires HTTPS)" -ForegroundColor Yellow
    Write-Host "   2. Update CORS_ORIGINS to production domain" -ForegroundColor Yellow
    Write-Host "   3. Enable PostgreSQL SSL (sslmode=require)" -ForegroundColor Yellow
    Write-Host "   4. Set backend and hadoop networks to internal: true" -ForegroundColor Yellow
    Write-Host "   5. Configure Kafka SASL_SSL authentication" -ForegroundColor Yellow
    Write-Host "   6. Set up monitoring and logging" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Green
Write-Host "  ✅ Security Setup Complete!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Summary:" -ForegroundColor Cyan
Write-Host "   - JWT secrets generated and saved to .env" -ForegroundColor White
Write-Host "   - Database password updated (if selected)" -ForegroundColor White
Write-Host "   - Hive password generated" -ForegroundColor White
if ($createSecrets -ne "n") {
    Write-Host "   - Docker secrets created in secrets/ directory" -ForegroundColor White
}
Write-Host ""
Write-Host "📖 Next Steps:" -ForegroundColor Cyan
Write-Host "   1. Review .env file and customize settings" -ForegroundColor White
Write-Host "   2. Start services with security overlay:" -ForegroundColor White
Write-Host "      docker-compose -f docker-compose.yml -f docker-compose.security.yml up -d" -ForegroundColor Yellow
Write-Host "   3. Verify network isolation:" -ForegroundColor White
Write-Host "      docker network ls | grep traffic" -ForegroundColor Yellow
Write-Host "   4. Check logs for any errors:" -ForegroundColor White
Write-Host "      docker-compose logs -f backend" -ForegroundColor Yellow
Write-Host ""
Write-Host "⚠️  Security Reminder:" -ForegroundColor Yellow
Write-Host "   - NEVER commit .env to version control!" -ForegroundColor Red
Write-Host "   - NEVER commit secrets/ directory!" -ForegroundColor Red
Write-Host "   - Verify .gitignore includes .env and secrets/" -ForegroundColor Yellow
Write-Host ""
