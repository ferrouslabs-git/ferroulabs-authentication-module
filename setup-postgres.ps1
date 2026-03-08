# TrustOS PostgreSQL Docker Setup Script
# Checks Docker, manages ports, runs container, and verifies connection

param(
    [string]$ContainerName = "trustos-postgres",
    [string]$PostgresPassword = "postgres",
    [string]$PostgresUser = "postgres",
    [string]$PostgresDB = "trustos_dev",
    [int]$PreferredPort = 5432
)

Write-Host "================================" -ForegroundColor Cyan
Write-Host " TrustOS PostgreSQL Setup" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Function to check if Docker is running
function Test-DockerRunning {
    Write-Host "Checking Docker status..." -ForegroundColor Yellow
    try {
        $null = docker info 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Docker is running" -ForegroundColor Green
            return $true
        }
    } catch {
        Write-Host "[ERROR] Docker is not running" -ForegroundColor Red
        Write-Host "Please start Docker Desktop and try again" -ForegroundColor Yellow
        return $false
    }
    
    Write-Host "[ERROR] Docker is not running" -ForegroundColor Red
    Write-Host "Please start Docker Desktop and try again" -ForegroundColor Yellow
    return $false
}

# Function to check if port is in use
function Test-PortInUse {
    param([int]$Port)
    
    $connection = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    return ($null -ne $connection)
}

# Function to find next available port
function Get-AvailablePort {
    param([int]$StartPort)
    
    $port = $StartPort
    while (Test-PortInUse -Port $port) {
        Write-Host "[WARN] Port $port is busy, trying next port..." -ForegroundColor Yellow
        $port++
        if ($port -gt ($StartPort + 10)) {
            Write-Host "[ERROR] Could not find available port in range $StartPort-$port" -ForegroundColor Red
            return $null
        }
    }
    return $port
}

# Function to check if container exists
function Test-ContainerExists {
    param([string]$Name)
    
    $container = docker ps -a --filter "name=^/${Name}$" --format "{{.Names}}" 2>$null
    return ($container -eq $Name)
}

# Function to check if container is running
function Test-ContainerRunning {
    param([string]$Name)
    
    $container = docker ps --filter "name=^/${Name}$" --format "{{.Names}}" 2>$null
    return ($container -eq $Name)
}

# Function to wait for Postgres to be ready
function Wait-PostgresReady {
    param(
        [string]$ContainerName,
        [string]$User,
        [int]$MaxAttempts = 30
    )
    
    Write-Host "Waiting for PostgreSQL to be ready..." -ForegroundColor Yellow
    
    for ($i = 1; $i -le $MaxAttempts; $i++) {
        $result = docker exec $ContainerName pg_isready -U $User 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] PostgreSQL is ready!" -ForegroundColor Green
            return $true
        }
        
        Write-Host "  Attempt $i/$MaxAttempts..." -ForegroundColor Gray
        Start-Sleep -Seconds 1
    }
    
    Write-Host "[ERROR] PostgreSQL did not become ready in time" -ForegroundColor Red
    return $false
}

# Main execution
Write-Host ""

# Step 1: Check Docker
if (-not (Test-DockerRunning)) {
    exit 1
}

Write-Host ""

# Step 2: Check if container already exists
$containerExists = Test-ContainerExists -Name $ContainerName

if ($containerExists) {
    Write-Host "Container '$ContainerName' already exists" -ForegroundColor Yellow
    
    $containerRunning = Test-ContainerRunning -Name $ContainerName
    
    if ($containerRunning) {
        Write-Host "[OK] Container is already running" -ForegroundColor Green
        
        # Get the port mapping
        $portMapping = docker port $ContainerName 5432 2>$null
        if ($portMapping -match ':(\d+)$') {
            $currentPort = $matches[1]
            Write-Host "[OK] Using existing container on port $currentPort" -ForegroundColor Green
            $Port = [int]$currentPort
        } else {
            Write-Host "[WARN] Could not determine port, assuming 5432" -ForegroundColor Yellow
            $Port = 5432
        }
    } else {
        Write-Host "Starting existing container..." -ForegroundColor Yellow
        docker start $ContainerName | Out-Null
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Container started successfully" -ForegroundColor Green
            
            # Get the port mapping
            $portMapping = docker port $ContainerName 5432 2>$null
            if ($portMapping -match ':(\d+)$') {
                $Port = [int]$matches[1]
            } else {
                $Port = 5432
            }
        } else {
            Write-Host "[ERROR] Failed to start container" -ForegroundColor Red
            exit 1
        }
    }
} else {
    # Container doesn't exist, create new one
    
    # Step 3: Find available port
    Write-Host "Checking port availability..." -ForegroundColor Yellow
    $Port = Get-AvailablePort -StartPort $PreferredPort
    
    if ($null -eq $Port) {
        exit 1
    }
    
    if ($Port -ne $PreferredPort) {
        Write-Host "[OK] Found available port: $Port" -ForegroundColor Green
    } else {
        Write-Host "[OK] Port $Port is available" -ForegroundColor Green
    }
    
    Write-Host ""
    
    # Step 4: Pull Postgres image if needed
    Write-Host "Checking for postgres:15 image..." -ForegroundColor Yellow
    $imageExists = docker images postgres:15 --format "{{.Repository}}" 2>$null
    
    if (-not $imageExists) {
        Write-Host "Pulling postgres:15 image (this may take a few minutes)..." -ForegroundColor Yellow
        docker pull postgres:15
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Image pulled successfully" -ForegroundColor Green
        } else {
            Write-Host "[ERROR] Failed to pull image" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "[OK] Image already exists" -ForegroundColor Green
    }
    
    Write-Host ""
    
    # Step 5: Run the container
    Write-Host "Starting PostgreSQL container..." -ForegroundColor Yellow
    Write-Host "  Name: $ContainerName" -ForegroundColor Gray
    Write-Host "  Port: $Port" -ForegroundColor Gray
    Write-Host "  Database: $PostgresDB" -ForegroundColor Gray
    
    docker run -d --name $ContainerName -e POSTGRES_PASSWORD=$PostgresPassword -e POSTGRES_USER=$PostgresUser -e POSTGRES_DB=$PostgresDB -p "${Port}:5432" postgres:15
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to start container" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "[OK] Container started successfully" -ForegroundColor Green
}

Write-Host ""

# Step 6: Wait for Postgres to be ready
$postgresReady = Wait-PostgresReady -ContainerName $ContainerName -User $PostgresUser

if (-not $postgresReady) {
    Write-Host "[WARN] Container is running but PostgreSQL may not be ready" -ForegroundColor Yellow
    Write-Host "You can check logs with: docker logs $ContainerName" -ForegroundColor Yellow
}

Write-Host ""

# Step 7: Print connection details
Write-Host "================================" -ForegroundColor Cyan
Write-Host " PostgreSQL is ready!" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Connection Details:" -ForegroundColor Cyan
Write-Host "  Host:     localhost" -ForegroundColor White
Write-Host "  Port:     $Port" -ForegroundColor White
Write-Host "  Database: $PostgresDB" -ForegroundColor White
Write-Host "  User:     $PostgresUser" -ForegroundColor White
Write-Host "  Password: $PostgresPassword" -ForegroundColor White
Write-Host ""
Write-Host "DATABASE_URL:" -ForegroundColor Cyan
$DatabaseURL = "postgresql://${PostgresUser}:${PostgresPassword}@localhost:${Port}/${PostgresDB}"
Write-Host "  $DatabaseURL" -ForegroundColor Yellow
Write-Host ""
Write-Host "Add this to your .env file:" -ForegroundColor Cyan
Write-Host "  DATABASE_URL=$DatabaseURL" -ForegroundColor White
Write-Host ""
Write-Host "Useful Commands:" -ForegroundColor Cyan
Write-Host "  Stop:    docker stop $ContainerName" -ForegroundColor White
Write-Host "  Start:   docker start $ContainerName" -ForegroundColor White
Write-Host "  Logs:    docker logs $ContainerName" -ForegroundColor White
Write-Host "  Shell:   docker exec -it $ContainerName psql -U $PostgresUser -d $PostgresDB" -ForegroundColor White
Write-Host "  Remove:  docker rm -f $ContainerName" -ForegroundColor White
Write-Host ""
