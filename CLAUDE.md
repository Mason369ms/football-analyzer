# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

独立的足球赛事数据分析与 LLM 智能预测系统。从竞彩 API 抓取实时赛事数据，通过赔率分析和机器学习模型生成赛事预测，支持 Web 仪表盘可视化展示。

## 常用命令

### 环境搭建
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 启动仪表盘（FastAPI）
```powershell
$env:PYTHONPATH='src'
python -m football_sim.cli dashboard --server fastapi --host 127.0.0.1 --port 8766
```

### 运行测试
```powershell
$env:PYTHONPATH='src'
python -m pytest tests/
```

### 运行单个测试
```powershell
$env:PYTHONPATH='src'
python -m pytest tests/test_auth.py -v
```

### CLI 子命令（均通过 `python -m football_sim.cli` 调用）
- `fetch-matches --date today` — 抓取当日赛事列表
- `fetch-details --date 2026-06-01` — 抓取赛事详情和赔率
- `analyze --date 2026-06-01` — LLM 分析赛事
- `odds-report --date today` — 生成赔率分析报告
- `fetch-results --date 2026-06-01` — 获取历史比赛结果
- `dashboard` — 启动足球数据 Web 仪表盘

### 自动化脚本
- `scripts/build_exe.ps1` — PyInstaller EXE 打包

### EXE 打包
```powershell
.\scripts\build_exe.ps1
```
产物在 `dist\football-analyzer\`。`launcher.py` 为入口，自动选择 FastAPI 或 stdlib 模式，EXE 内通过 `--cli` 参数调用 CLI 子命令。

### Docker 部署
```powershell
$env:FOOTBALL_ADMIN_USER='admin'
$env:FOOTBALL_ADMIN_PASSWORD='change-this-password'
docker compose up -d --build
```

## 架构

### 源码结构（`src/football_sim/`）

**核心数据流：** data_sources → analysis → reports → dashboard

| 模块 | 职责 |
|---|---|
| `models.py` | 所有足球数据类型的冻结数据类（`FootballMatch`、`OddsSnapshot`、`MatchAnalysis` 等） |
| `data_sources/match_fetcher.py` | 从竞彩 API 抓取赛事列表，解析比赛结果 |
| `data_sources/odds_fetcher.py` | 异步抓取欧赔/亚盘/大小球赔率变化、历史交锋、近期战绩等 |
| `data_sources/match_store.py` | 赛事数据本地存储（JSON 文件），目录管理，zip 打包 |
| `data_sources/http_client.py` | HTTP 客户端工具：自定义 SSL 适配器（TLS 1.2/1.3）、带重试的 Session、随机 User-Agent |
| `analysis/odds_analyzer.py` | 赔率分析引擎：欧赔隐含概率计算、亚盘/大小球方向判定、多公司对比、异常波动检测 |
| `analysis/llm_analyzer.py` | LLM 调用核心：OpenAI 兼容 API 调用（同步/流式）、赛事分析、赔率意图分析、JSON 提取 |
| `analysis/skill_predictor.py` | 基于本地赔率数据的简化预测器：生成胜平负/比分/进球预测 |
| `prompts/match_analysis.py` | LLM Prompt 模板：系统提示词、用户提示构建（含赔率摘要、skill 预测参考） |
| `reports/text_report.py` | 文本报告生成：分析报告、比赛数据摘要、每日汇总报告、JSON 导出 |
| `history_db.py` | SQLite 表结构：matches、analyses、match_results、llm_calls、dashboard_config、dashboard_actions |
| `auth.py` | PBKDF2-SHA256 密码哈希、会话管理（7 天有效期） |
| `user_workspace.py` | 按用户隔离的目录：报告、模型、导出文件 |
| `dashboard.py` | stdlib HTTP 服务（单用户备用模式） |
| `fastapi_app.py` | FastAPI 应用：认证、SSE 任务流、多用户支持 |
| `cli.py` | argparse CLI — 全部 fetch-matches/fetch-details/analyze/odds-report/fetch-results/dashboard 子命令 |
| `launcher.py` | EXE 入口 — 自动选择 FastAPI 或 stdlib，配置 PYTHONPATH |

### 关键设计模式

- **数据源模式**：每个数据源（赛事、赔率）独立实现，通过 HTTP 客户端抓取
- **分析器模式**：赔率分析、LLM 分析、技能预测各自独立，可组合使用
- **工作空间模式**：按用户名隔离数据目录、报告目录和数据库
- **认证模式**：PBKDF2-SHA256 密码哈希，Session 管理，多用户支持
- **SSE 推送模式**：FastAPI 仪表盘通过 Server-Sent Events 实时推送任务进度

### 数据目录

- `data/matches/` — 赛事数据（按日期存储的 JSON 文件）
- `data/users/<username>/` — 按用户隔离的数据库和配置
- `data/app_football.sqlite3` — 认证与仪表盘状态数据库
- `reports/latest/` — 当前报告
- `reports/users/<username>/` — 按用户隔离的报告

### 环境变量

- `PYTHONPATH=src` — 所有 CLI/仪表盘调用必须设置
- `FOOTBALL_ADMIN_USER` / `FOOTBALL_ADMIN_PASSWORD` — 初始化管理员账号（默认 admin/admin）
- `FOOTBALL_HOST`、`FOOTBALL_PORT`、`FOOTBALL_OPEN_BROWSER` — launcher.py 默认值
- `FOOTBALL_CLI_EXE` — 打包为 EXE 时自动设置
- `FOOTBALL_SSL_VERIFY` — 是否验证 SSL 证书（默认 true）
- `FOOTBALL_RETRY_COUNT` — HTTP 请求重试次数（默认 3）
- `FOOTBALL_USE_PROXY` — 是否使用代理（默认 false）

### LLM 配置

通过 Web 仪表盘的 "AI 配置" 页面设置：

- **LLM 提供商**：`openai`、`deepseek` 或其他 OpenAI 兼容 API
- **API 地址**：如 `https://api.openai.com/v1` 或 `https://api.deepseek.com/v1`
- **模型名称**：如 `gpt-4`、`deepseek-chat`
- **API 密钥**：你的 API 密钥

配置存储在 `data/users/<username>/history.sqlite3` 的 `dashboard_config` 表中。LLM 调用实现在 `analysis/llm_analyzer.py`，通过 OpenAI 兼容 API（同步/流式）实现。

### 核心依赖

- `fastapi` + `uvicorn` — Web 仪表盘框架
- `httpx` + `aiohttp` — 异步 HTTP 客户端（赔率抓取）
- `requests` — 同步 HTTP 请求（赛事数据抓取）

完整依赖见 `requirements.txt`。

### 平台注意事项

项目开发基于 Windows（PowerShell），但支持 Linux/macOS：
- **激活虚拟环境**：Windows `.\.venv\Scripts\Activate.ps1`，Linux/macOS `source .venv/bin/activate`
- **PYTHONPATH**：所有 CLI 命令前需设置（PowerShell: `$env:PYTHONPATH='src'`，Linux: `export PYTHONPATH=src`）
- **路径分隔符**：代码中统一使用 `pathlib.Path` 处理路径

### 测试

测试使用 `unittest`（非 pytest fixtures）。测试文件位于 `tests/`。FastAPI 测试通过 `fastapi.testclient.TestClient` 发起请求。临时目录使用 `.test-tmp/`（已 gitignore）。

测试约定：
- 每个测试类用 `_temp_dir()` 上下文管理器创建隔离的临时目录，测试结束自动清理
- FastAPI 测试通过 `patch.dict(os.environ, ...)` 注入环境变量（如 `FOOTBALL_ADMIN_USER`）
- 测试命名：`test_<module>.py`，类名 `<Feature>Tests(unittest.TestCase)`
- 测试覆盖：认证（`test_auth.py`）、多用户功能（`test_fastapi_multi_user.py`）、工作空间（`test_user_workspace.py`）

### 数据格式

赛事数据存储为 JSON 文件（`data/matches/YYYY-MM-DD/<match_id>/`），包含：
- 赛事基本信息：`match_id`、联赛、主客场、比赛时间、轮次等
- 赔率快照：欧赔（1/X/2）、亚盘（让球数+水位）、大小球（盘口+水位）
- 赔率变化历史：各公司赔率变化时间序列
- 历史交锋和近期战绩：对阵记录、近期 5-10 场战绩

SQLite 数据库结构详见 `history_db.py`：
- `matches`：赛事基础信息
- `analyses`：LLM 分析结果
- `match_results`：比赛最终结果
- `dashboard_config`：LLM API 配置
- `dashboard_actions`：仪表盘操作记录

### 开发调试

- **测试隔离**：每个测试类使用 `_temp_dir()` 创建临时目录，测试后自动清理
- **FastAPI 测试**：通过 `TestClient` 发起请求，使用 `patch.dict(os.environ, ...)` 注入配置
- **LLM 配置**：在仪表盘中配置后会存储到 `data/users/<username>/history.sqlite3`
- **赔率抓取**：使用自定义 SSL 适配器（支持 TLS 1.2/1.3），随机 User-Agent 避免封禁
- **异步处理**：赔率抓取使用 `aiohttp`，LLM 调用支持流式响应
