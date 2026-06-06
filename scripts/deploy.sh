#!/bin/bash
# ============================================================
# Football Analyzer 生产环境部署脚本
# ============================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查依赖
check_dependencies() {
    log_info "检查依赖..."

    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose 未安装"
        exit 1
    fi

    log_success "依赖检查通过"
}

# 检查环境变量
check_env() {
    log_info "检查环境变量..."

    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            log_warning ".env 文件不存在，正在从 .env.example 创建..."
            cp .env.example .env
            log_warning "请编辑 .env 文件配置您的环境变量"
            exit 1
        else
            log_error ".env 文件不存在"
            exit 1
        fi
    fi

    # 加载环境变量
    source .env

    # 检查必要的环境变量
    if [ -z "$FOOTBALL_ADMIN_PASSWORD" ] || [ "$FOOTBALL_ADMIN_PASSWORD" = "change-this-password" ]; then
        log_warning "请设置安全的管理员密码 (FOOTBALL_ADMIN_PASSWORD)"
    fi

    log_success "环境变量检查完成"
}

# 创建必要目录
create_directories() {
    log_info "创建必要目录..."

    mkdir -p data
    mkdir -p data/matches
    mkdir -p data/users
    mkdir -p data/backups
    mkdir -p reports
    mkdir -p logs
    mkdir -p backups
    mkdir -p monitoring

    log_success "目录创建完成"
}

# 构建镜像
build_image() {
    log_info "构建 Docker 镜像..."

    docker-compose -f docker-compose.prod.yml build --no-cache

    log_success "镜像构建完成"
}

# 启动服务
start_services() {
    log_info "启动服务..."

    docker-compose -f docker-compose.prod.yml up -d

    log_success "服务启动完成"
}

# 停止服务
stop_services() {
    log_info "停止服务..."

    docker-compose -f docker-compose.prod.yml down

    log_success "服务已停止"
}

# 重启服务
restart_services() {
    log_info "重启服务..."

    stop_services
    start_services

    log_success "服务重启完成"
}

# 查看日志
view_logs() {
    docker-compose -f docker-compose.prod.yml logs -f
}

# 健康检查
health_check() {
    log_info "执行健康检查..."

    sleep 5

    response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:${FOOTBALL_PORT:-8766}/health || echo "000")

    if [ "$response" = "200" ]; then
        log_success "健康检查通过"
    else
        log_error "健康检查失败 (HTTP $response)"
        return 1
    fi
}

# 备份数据
backup_data() {
    log_info "备份数据..."

    timestamp=$(date +%Y%m%d_%H%M%S)
    backup_dir="backups/backup_${timestamp}"

    mkdir -p "$backup_dir"

    # 备份数据目录
    if [ -d "data" ]; then
        cp -r data "$backup_dir/"
        log_info "数据目录已备份"
    fi

    # 备份报告目录
    if [ -d "reports" ]; then
        cp -r reports "$backup_dir/"
        log_info "报告目录已备份"
    fi

    # 备份配置
    if [ -f ".env" ]; then
        cp .env "$backup_dir/"
        log_info "配置文件已备份"
    fi

    # 压缩备份
    tar -czf "backups/backup_${timestamp}.tar.gz" -C backups "backup_${timestamp}"
    rm -rf "$backup_dir"

    log_success "备份完成: backups/backup_${timestamp}.tar.gz"
}

# 恢复数据
restore_data() {
    if [ -z "$1" ]; then
        log_error "请指定备份文件路径"
        exit 1
    fi

    backup_file="$1"

    if [ ! -f "$backup_file" ]; then
        log_error "备份文件不存在: $backup_file"
        exit 1
    fi

    log_info "恢复数据从: $backup_file"

    # 停止服务
    stop_services

    # 解压备份
    temp_dir=$(mktemp -d)
    tar -xzf "$backup_file" -C "$temp_dir"

    # 恢复数据
    backup_name=$(ls "$temp_dir")
    if [ -d "$temp_dir/$backup_name/data" ]; then
        rm -rf data
        cp -r "$temp_dir/$backup_name/data" .
        log_info "数据目录已恢复"
    fi

    if [ -d "$temp_dir/$backup_name/reports" ]; then
        rm -rf reports
        cp -r "$temp_dir/$backup_name/reports" .
        log_info "报告目录已恢复"
    fi

    # 清理
    rm -rf "$temp_dir"

    # 重启服务
    start_services

    log_success "数据恢复完成"
}

# 更新服务
update_services() {
    log_info "更新服务..."

    # 备份数据
    backup_data

    # 拉取最新代码
    git pull

    # 重新构建和启动
    build_image
    restart_services

    # 健康检查
    health_check

    log_success "更新完成"
}

# 清理资源
cleanup() {
    log_info "清理未使用的 Docker 资源..."

    docker system prune -f
    docker volume prune -f

    log_success "清理完成"
}

# 显示状态
show_status() {
    log_info "服务状态:"
    docker-compose -f docker-compose.prod.yml ps

    echo ""
    log_info "资源使用:"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPU}}\t{{.MemUsage}}"
}

# 显示帮助
show_help() {
    echo "Football Analyzer 部署脚本"
    echo ""
    echo "使用方法: $0 <command>"
    echo ""
    echo "命令:"
    echo "  build          构建 Docker 镜像"
    echo "  start          启动服务"
    echo "  stop           停止服务"
    echo "  restart        重启服务"
    echo "  logs           查看日志"
    echo "  health         健康检查"
    echo "  backup         备份数据"
    echo "  restore <file> 恢复数据"
    echo "  update         更新服务"
    echo "  cleanup        清理 Docker 资源"
    echo "  status         显示状态"
    echo "  help           显示帮助"
    echo ""
}

# 主函数
main() {
    check_dependencies
    check_env
    create_directories

    case "${1:-help}" in
        build)
            build_image
            ;;
        start)
            start_services
            health_check
            ;;
        stop)
            stop_services
            ;;
        restart)
            restart_services
            health_check
            ;;
        logs)
            view_logs
            ;;
        health)
            health_check
            ;;
        backup)
            backup_data
            ;;
        restore)
            restore_data "$2"
            ;;
        update)
            update_services
            ;;
        cleanup)
            cleanup
            ;;
        status)
            show_status
            ;;
        help|*)
            show_help
            ;;
    esac
}

# 执行主函数
main "$@"
