# Football Analyzer - 足球赛事数据分析系统

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Vue.js](https://img.shields.io/badge/Vue.js-3.x-brightgreen.svg)](https://vuejs.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

独立的足球赛事数据分析与 LLM 智能预测系统。从竞彩 API 抓取实时赛事数据，通过赔率分析和机器学习模型生成赛事预测，支持 Web 仪表盘可视化展示。

![Dashboard Preview](docs/images/dashboard.png)

## ✨ 功能特性

### 核心功能
- 🏟️ **赛事数据抓取** - 从竞彩 API 实时获取赛事列表和比赛结果
- 📊 **赔率深度分析** - 欧赔隐含概率计算、亚盘/大小球方向判定、异常波动检测
- 🤖 **LLM 智能分析** - 基于 OpenAI 兼容 API 的赛事智能分析和预测
- 📈 **技能预测器** - 基于本地赔率数据的简化预测模型
- 📋 **命中率追踪** - 自动计算预测命中率（胜平负、比分、进球数）

### Web 仪表盘
- 🌐 **Vue 3 现代化前端** - 基于 Element Plus + ECharts 的响应式界面
- 📱 **移动端适配** - 完整的响应式设计，支持手机和平板
- 🔄 **实时进度显示** - SSE 实时推送任务进度和日志
- 📊 **数据可视化** - 赔率变化趋势图、命中率统计图表
- 👥 **多用户支持** - 独立的用户认证、数据隔离和工作空间管理

### 数据管理
- 📦 **批量操作** - 支持批量抓取、批量分析、批量删除
- 🔍 **详细数据** - 历史交锋、近期战绩、阵容情报、联赛积分
- 💾 **数据导出** - 支持 PDF 和 Excel 报告导出
- 🗑️ **数据清理** - 支持单个和批量删除赛事及分析记录

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Node.js 18+ (用于前端开发)
- npm 或 yarn

### 安装步骤

#### 1. 克隆项目

```bash
git clone https://github.com/Mason369ms/football-analyzer.git
cd football-analyzer
```

#### 2. 后端设置

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# Linux/macOS
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

#### 3. 前端设置

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 开发模式（热重载）
npm run dev

# 生产构建
npm run build
```

#### 4. 配置 LLM API（必须）

在使用 LLM 分析功能前，需要配置 API Key：

**方式 1：命令行快速设置（推荐）**

```bash
# 设置 PYTHONPATH
$env:PYTHONPATH='src'  # Windows PowerShell
export PYTHONPATH=src   # Linux/macOS

# 快速设置 API Key
python scripts/quick_setup.py YOUR_API_KEY

# 或指定自定义配置
python scripts/quick_setup.py --key YOUR_API_KEY --url https://api.deepseek.com/v1 --model deepseek-chat
```

**方式 2：通过仪表盘设置**

启动仪表盘后，在"设置"页面配置 API 信息。

**方式 3：交互式设置**

```bash
python scripts/set_api_key.py
```

### 启动服务

#### 开发模式

```bash
# 终端 1：启动后端
$env:PYTHONPATH='src'
python -m football_sim.cli dashboard --server fastapi --host 127.0.0.1 --port 8766

# 终端 2：启动前端（可选，用于前端开发）
cd frontend
npm run dev
```

访问 http://localhost:3001（前端开发服务器）或 http://localhost:8766（后端服务）

#### 生产模式

```bash
# 构建前端
cd frontend
npm run build
cd ..

# 启动服务
$env:PYTHONPATH='src'
python -m football_sim.cli dashboard --server fastapi --host 0.0.0.0 --port 8766
```

访问 http://localhost:8766

### Docker 部署

```bash
# 设置管理员账号（可选）
$env:FOOTBALL_ADMIN_USER='admin'
$env:FOOTBALL_ADMIN_PASSWORD='your-secure-password'

# 启动服务
docker compose up -d --build

# 查看日志
docker compose logs -f

# 停止服务
docker compose down
```

访问 http://localhost:8766

## 📖 使用指南

### CLI 命令

所有 CLI 命令通过 `python -m football_sim.cli` 调用：

```bash
# 设置 PYTHONPATH（必须）
$env:PYTHONPATH='src'

# 抓取今日赛事
python -m football_sim.cli fetch-matches --date today

# 获取赛事详情和赔率
python -m football_sim.cli fetch-details --date 2026-06-06

# LLM 智能分析赛事
python -m football_sim.cli analyze --date 2026-06-06

# 生成赔率分析报告
python -m football_sim.cli odds-report --date today

# 获取历史比赛结果
python -m football_sim.cli fetch-results --date 2026-06-06

# 启动 Web 仪表盘
python -m football_sim.cli dashboard --port 8766
```

### Web 仪表盘功能

#### 1. 赛事列表
- 查看当日所有赛事
- 抓取赛事和赔率数据
- 单个/批量删除赛事
- 单个/批量分析赛事

#### 2. 赛事详情
- 查看完整的赛事信息
- 赔率摘要（欧赔隐含概率、亚盘方向、大小球方向）
- 赔率变化趋势图
- 执行 LLM 分析

#### 3. 分析详情
- 查看预测结果（胜平负、比分、进球数）
- 完整的分析文本
- 导出 PDF 报告

#### 4. 近期分析
- 查看所有分析记录
- 按序号排序
- 查看命中率统计
- 获取比赛结果

## 🏗️ 架构说明

### 源码结构

```
src/football_sim/
├── __init__.py              # 模块声明
├── auth.py                  # 用户认证系统（PBKDF2-SHA256）
├── cli.py                   # CLI 命令行入口
├── dashboard.py             # stdlib HTTP 仪表盘
├── fastapi_app.py           # FastAPI 多用户仪表盘
├── history_db.py            # SQLite 数据库管理
├── launcher.py              # 启动入口
├── models.py                # 数据模型定义
├── user_workspace.py        # 用户工作空间管理
├── config.py                # 配置管理
├── cache.py                 # 缓存层
├── monitoring.py            # 监控和日志
├── export.py                # 数据导出（PDF/Excel）
├── backup.py                # 数据备份
├── scheduler.py             # 定时任务
├── retry.py                 # 重试机制
├── logger.py                # 结构化日志
├── analysis/
│   ├── odds_analyzer.py     # 赔率分析引擎
│   ├── llm_analyzer.py      # LLM 分析核心
│   └── skill_predictor.py   # 技能预测器
├── data_sources/
│   ├── http_client.py       # HTTP 客户端工具
│   ├── match_fetcher.py     # 赛事数据抓取
│   ├── match_store.py       # 赛事数据存储
│   └── odds_fetcher.py      # 赔率数据抓取
├── prompts/
│   └── match_analysis.py    # LLM 提示词模板
└── reports/
    └── text_report.py       # 文本报告生成
```

### 前端结构

```
frontend/
├── src/
│   ├── main.ts              # 入口文件
│   ├── App.vue              # 根组件
│   ├── router/index.ts      # 路由配置
│   ├── layouts/
│   │   └── MainLayout.vue   # 主布局
│   ├── views/
│   │   ├── Dashboard.vue    # 仪表盘
│   │   ├── MatchDetail.vue  # 比赛详情
│   │   └── AnalysisDetail.vue # 分析详情
│   ├── utils/
│   │   └── api.ts           # API 封装
│   └── assets/
│       └── main.scss        # 全局样式
├── package.json
├── vite.config.ts
└── tsconfig.json
```

### 数据流

```
赛事数据抓取 (match_fetcher)
       ↓
赛事数据存储 (match_store)
       ↓
赔率数据抓取 (odds_fetcher)
       ↓
赔率分析 (odds_analyzer)
       ↓
LLM 分析 (llm_analyzer)
       ↓
技能预测 (skill_predictor)
       ↓
报告生成 (text_report)
       ↓
Web 仪表盘展示 (fastapi_app)
```

### 数据目录

```
data/
├── app_football.sqlite3     # 认证数据库
├── matches/                 # 赛事数据（按日期存储）
│   └── 2026-06-06/
│       └── 周六217_国际友谊_阿根廷_vs_洪都拉斯/
│           ├── 赛事信息.json
│           ├── 赔率变化数据.json
│           ├── 两队比赛历史交锋数据.json
│           └── ...
└── users/
    └── <username>/
        └── history.sqlite3  # 用户历史数据库
```

## ⚙️ 配置说明

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `PYTHONPATH` | `src` | 必须设置，指向源码目录 |
| `FOOTBALL_HOST` | `127.0.0.1` | 仪表盘监听地址 |
| `FOOTBALL_PORT` | `8766` | 仪表盘监听端口 |
| `FOOTBALL_OPEN_BROWSER` | `1` | 启动时自动打开浏览器 |
| `FOOTBALL_ADMIN_USER` | `admin` | 初始管理员用户名 |
| `FOOTBALL_ADMIN_PASSWORD` | `admin` | 初始管理员密码 |
| `FOOTBALL_SSL_VERIFY` | `true` | 是否验证 SSL 证书 |
| `FOOTBALL_RETRY_COUNT` | `3` | HTTP 请求重试次数 |
| `FOOTBALL_USE_PROXY` | `false` | 是否使用代理 |

### LLM 配置

通过 Web 仪表盘的 "设置" 页面设置：

- **LLM 提供商**：`openai`、`deepseek` 或其他 OpenAI 兼容 API
- **API 地址**：如 `https://api.openai.com/v1` 或 `https://api.deepseek.com/v1`
- **模型名称**：如 `gpt-4`、`deepseek-chat`
- **API 密钥**：你的 API 密钥

## 🧪 测试

```bash
# 设置 PYTHONPATH
$env:PYTHONPATH='src'

# 运行所有测试
python -m pytest tests/ -v

# 运行单个测试
python -m pytest tests/test_auth.py -v

# 生成覆盖率报告
python -m pytest tests/ --cov=football_sim --cov-report=html
```

## 📦 EXE 打包

```powershell
.\scripts\build_exe.ps1
```

产物在 `dist\football-analyzer\`。`launcher.py` 为入口，自动选择 FastAPI 或 stdlib 模式。

## 🔧 开发指南

### 项目约定

- 测试使用 `unittest`（非 pytest fixtures）
- 测试文件位于 `tests/`
- 每个测试类使用 `_temp_dir()` 上下文管理器创建隔离的临时目录
- FastAPI 测试通过 `TestClient` 发起请求
- 数据库操作使用 SQLite，支持多用户隔离
- 前端使用 Vue 3 Composition API + TypeScript

### 关键设计模式

- **数据源模式**：每个数据源（赛事、赔率）独立实现，通过 HTTP 客户端抓取
- **分析器模式**：赔率分析、LLM 分析、技能预测各自独立，可组合使用
- **工作空间模式**：按用户名隔离数据目录、报告目录和数据库
- **认证模式**：PBKDF2-SHA256 密码哈希，Session 管理，多用户支持
- **SSE 推送模式**：FastAPI 仪表盘通过 Server-Sent Events 实时推送任务进度
- **缓存模式**：多级缓存（内存、Redis、文件），自动过期和清理
- **重试模式**：指数退避重试机制，支持配置最大重试次数

### 平台注意事项

项目开发基于 Windows（PowerShell），但支持 Linux/macOS：

- **激活虚拟环境**：Windows `.\.venv\Scripts\Activate.ps1`，Linux/macOS `source .venv/bin/activate`
- **PYTHONPATH**：所有 CLI 命令前需设置（PowerShell: `$env:PYTHONPATH='src'`，Linux: `export PYTHONPATH=src`）
- **路径分隔符**：代码中统一使用 `pathlib.Path` 处理路径

## 📊 性能优化

- **数据库索引**：为常用查询字段添加索引
- **连接池**：SQLite 连接池管理
- **缓存层**：多级缓存减少数据库查询
- **异步处理**：赔率抓取使用 aiohttp，LLM 调用支持流式响应
- **批量操作**：支持批量插入和更新

## 🔒 安全特性

- **密码哈希**：PBKDF2-SHA256，迭代次数 260,000
- **会话管理**：7 天有效期，支持 IP 绑定
- **SQL 注入防护**：参数化查询
- **CSRF 防护**：表单提交验证
- **输入验证**：Pydantic 模型验证

## 📈 监控和日志

- **结构化日志**：JSON 格式，支持日志级别过滤
- **健康检查**：`/health` 和 `/health/detailed` 端点
- **Prometheus 指标**：`/metrics` 端点
- **请求追踪**：自动记录请求耗时和状态码
- **错误追踪**：集成 Sentry（可选）

## 🤝 贡献指南

欢迎贡献代码！请遵循以下步骤：

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

### 代码规范

- Python: 遵循 PEP 8
- TypeScript: 使用 ESLint + Prettier
- 提交信息: 使用中文，格式为 `[类型] 描述`

## 📝 更新日志

### v1.0.0 (2026-06-06)
- ✨ 初始发布
- 🏟️ 赛事数据抓取功能
- 📊 赔率深度分析
- 🤖 LLM 智能分析
- 🌐 Vue 3 现代化前端
- 📱 响应式设计
- 🔄 实时进度显示
- 👥 多用户支持
- 🐳 Docker 部署支持

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

- [FastAPI](https://fastapi.tiangolo.com/) - 现代、快速的 Python Web 框架
- [Vue.js](https://vuejs.org/) - 渐进式 JavaScript 框架
- [Element Plus](https://element-plus.org/) - Vue 3 UI 组件库
- [ECharts](https://echarts.apache.org/) - 数据可视化图表库
- [Pydantic](https://docs.pydantic.dev/) - 数据验证和设置管理

## 📞 联系方式

- 项目地址: https://github.com/Mason369ms/football-analyzer
- 问题反馈: [Issues](https://github.com/Mason369ms/football-analyzer/issues)

---

⭐ 如果这个项目对你有帮助，请给个 Star 支持一下！
