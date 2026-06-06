# ============================================================
# Football Analyzer 前端构建脚本 (Windows)
# ============================================================

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Football Analyzer 前端构建" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 进入前端目录
Set-Location "$PSScriptRoot\..\frontend"

# 检查 Node.js
try {
    $nodeVersion = node --version
    Write-Host "Node.js 版本: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "错误: Node.js 未安装" -ForegroundColor Red
    Write-Host "请访问 https://nodejs.org/ 下载安装" -ForegroundColor Yellow
    exit 1
}

# 安装依赖
Write-Host ""
Write-Host "安装依赖..." -ForegroundColor Yellow
npm install

if ($LASTEXITCODE -ne 0) {
    Write-Host "依赖安装失败" -ForegroundColor Red
    exit 1
}

# 构建生产版本
Write-Host ""
Write-Host "构建生产版本..." -ForegroundColor Yellow
npm run build

if ($LASTEXITCODE -ne 0) {
    Write-Host "构建失败" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  构建完成!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "静态文件已生成到: src\football_sim\static\" -ForegroundColor Cyan
Write-Host ""
Write-Host "启动服务后访问: http://localhost:8766" -ForegroundColor Cyan
