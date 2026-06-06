# ============================================================
# Football Analyzer 生产环境部署脚本 (Windows)
# ============================================================

param(
    [Parameter(Position=0)]
    [string]$Command = "help"
)

# 颜色函数
function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

# 检查依赖
function Test-Dependencies {
    Write-Info "检查依赖..."

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Error "Docker 未安装"
        exit 1
    }

    if (-not (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
        Write-Error "Docker Compose 未安装"
        exit 1
    }

    Write-Success "依赖检查通过"
}

# 检查环境变量
function Test-Environment {
    Write-Info "检查环境变量..."

    if (-not (Test-Path ".env")) {
        if (Test-Path ".env.example") {
            Write-Warning ".env 文件不存在，正在从 .env.example 创建..."
            Copy-Item ".env.example" ".env"
            Write-Warning "请编辑 .env 文件配置您的环境变量"
            exit 1
        } else {
            Write-Error ".env 文件不存在"
            exit 1
        }
    }

    # 加载环境变量
    Get-Content ".env" | ForEach-Object {
        if ($_ -match "^([^=]+)=(.*)$") {
            [Environment]::SetEnvironmentVariable($matches[1], $matches[2])
        }
    }

    Write-Success "环境变量检查完成"
}

# 创建必要目录
function New-Directories {
    Write-Info "创建必要目录..."

    $dirs = @("data", "data\matches", "data\users", "data\backups", "reports", "logs", "backups", "monitoring")

    foreach ($dir in $dirs) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
    }

    Write-Success "目录创建完成"
}

# 构建镜像
function Build-Image {
    Write-Info "构建 Docker 镜像..."

    docker-compose -f docker-compose.prod.yml build --no-cache

    Write-Success "镜像构建完成"
}

# 启动服务
function Start-Services {
    Write-Info "启动服务..."

    docker-compose -f docker-compose.prod.yml up -d

    Write-Success "服务启动完成"
}

# 停止服务
function Stop-Services {
    Write-Info "停止服务..."

    docker-compose -f docker-compose.prod.yml down

    Write-Success "服务已停止"
}

# 重启服务
function Restart-Services {
    Write-Info "重启服务..."

    Stop-Services
    Start-Services

    Write-Success "服务重启完成"
}

# 查看日志
function Show-Logs {
    docker-compose -f docker-compose.prod.yml logs -f
}

# 健康检查
function Test-Health {
    Write-Info "执行健康检查..."

    Start-Sleep -Seconds 5

    try {
        $port = [Environment]::GetEnvironmentVariable("FOOTBALL_PORT") ?? "8766"
        $response = Invoke-WebRequest -Uri "http://localhost:$port/health" -UseBasicParsing -TimeoutSec 10
        if ($response.StatusCode -eq 200) {
            Write-Success "健康检查通过"
        } else {
            Write-Error "健康检查失败 (HTTP $($response.StatusCode))"
        }
    } catch {
        Write-Error "健康检查失败: $_"
    }
}

# 备份数据
function Backup-Data {
    Write-Info "备份数据..."

    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backupDir = "backups\backup_$timestamp"

    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

    # 备份数据目录
    if (Test-Path "data") {
        Copy-Item -Path "data" -Destination "$backupDir\" -Recurse
        Write-Info "数据目录已备份"
    }

    # 备份报告目录
    if (Test-Path "reports") {
        Copy-Item -Path "reports" -Destination "$backupDir\" -Recurse
        Write-Info "报告目录已备份"
    }

    # 备份配置
    if (Test-Path ".env") {
        Copy-Item -Path ".env" -Destination "$backupDir\"
        Write-Info "配置文件已备份"
    }

    # 压缩备份
    Compress-Archive -Path $backupDir -DestinationPath "backups\backup_$timestamp.zip"
    Remove-Item -Path $backupDir -Recurse -Force

    Write-Success "备份完成: backups\backup_$timestamp.zip"
}

# 恢复数据
function Restore-Data {
    param([string]$BackupFile)

    if (-not $BackupFile) {
        Write-Error "请指定备份文件路径"
        exit 1
    }

    if (-not (Test-Path $BackupFile)) {
        Write-Error "备份文件不存在: $BackupFile"
        exit 1
    }

    Write-Info "恢复数据从: $BackupFile"

    # 停止服务
    Stop-Services

    # 解压备份
    $tempDir = New-Item -ItemType Directory -Path "$env:TEMP\football_restore_$(Get-Date -Format 'yyyyMMddHHmmss')" -Force
    Expand-Archive -Path $BackupFile -DestinationPath $tempDir.FullName

    # 恢复数据
    $backupName = Get-ChildItem -Path $tempDir.FullName | Select-Object -First 1

    if (Test-Path "$($backupName.FullName)\data") {
        Remove-Item -Path "data" -Recurse -Force -ErrorAction SilentlyContinue
        Copy-Item -Path "$($backupName.FullName)\data" -Destination "." -Recurse
        Write-Info "数据目录已恢复"
    }

    if (Test-Path "$($backupName.FullName)\reports") {
        Remove-Item -Path "reports" -Recurse -Force -ErrorAction SilentlyContinue
        Copy-Item -Path "$($backupName.FullName)\reports" -Destination "." -Recurse
        Write-Info "报告目录已恢复"
    }

    # 清理
    Remove-Item -Path $tempDir.FullName -Recurse -Force

    # 重启服务
    Start-Services

    Write-Success "数据恢复完成"
}

# 更新服务
function Update-Services {
    Write-Info "更新服务..."

    # 备份数据
    Backup-Data

    # 拉取最新代码
    git pull

    # 重新构建和启动
    Build-Image
    Restart-Services

    # 健康检查
    Test-Health

    Write-Success "更新完成"
}

# 清理资源
function Remove-UnusedResources {
    Write-Info "清理未使用的 Docker 资源..."

    docker system prune -f
    docker volume prune -f

    Write-Success "清理完成"
}

# 显示状态
function Show-Status {
    Write-Info "服务状态:"
    docker-compose -f docker-compose.prod.yml ps

    Write-Host ""
    Write-Info "资源使用:"
    docker stats --no-stream --format "table {{.Name}}`t{{.CPU}}`t{{.MemUsage}}"
}

# 显示帮助
function Show-Help {
    Write-Host "Football Analyzer 部署脚本"
    Write-Host ""
    Write-Host "使用方法: .\scripts\deploy.ps1 <command>"
    Write-Host ""
    Write-Host "命令:"
    Write-Host "  build          构建 Docker 镜像"
    Write-Host "  start          启动服务"
    Write-Host "  stop           停止服务"
    Write-Host "  restart        重启服务"
    Write-Host "  logs           查看日志"
    Write-Host "  health         健康检查"
    Write-Host "  backup         备份数据"
    Write-Host "  restore <file> 恢复数据"
    Write-Host "  update         更新服务"
    Write-Host "  cleanup        清理 Docker 资源"
    Write-Host "  status         显示状态"
    Write-Host "  help           显示帮助"
    Write-Host ""
}

# 主函数
function Main {
    Test-Dependencies
    Test-Environment
    New-Directories

    switch ($Command.ToLower()) {
        "build" {
            Build-Image
        }
        "start" {
            Start-Services
            Test-Health
        }
        "stop" {
            Stop-Services
        }
        "restart" {
            Restart-Services
            Test-Health
        }
        "logs" {
            Show-Logs
        }
        "health" {
            Test-Health
        }
        "backup" {
            Backup-Data
        }
        "restore" {
            Restore-Data -BackupFile $args[0]
        }
        "update" {
            Update-Services
        }
        "cleanup" {
            Remove-UnusedResources
        }
        "status" {
            Show-Status
        }
        default {
            Show-Help
        }
    }
}

# 执行主函数
Main
