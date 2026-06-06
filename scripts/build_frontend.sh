#!/bin/bash
# ============================================================
# Football Analyzer 前端构建脚本
# ============================================================

set -e

echo "=========================================="
echo "  Football Analyzer 前端构建"
echo "=========================================="

# 进入前端目录
cd "$(dirname "$0")/../frontend"

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "错误: Node.js 未安装"
    echo "请访问 https://nodejs.org/ 下载安装"
    exit 1
fi

echo "Node.js 版本: $(node --version)"
echo "npm 版本: $(npm --version)"

# 安装依赖
echo ""
echo "安装依赖..."
npm install

# 构建生产版本
echo ""
echo "构建生产版本..."
npm run build

echo ""
echo "=========================================="
echo "  构建完成!"
echo "=========================================="
echo ""
echo "静态文件已生成到: src/football_sim/static/"
echo ""
echo "启动服务后访问: http://localhost:8766"
