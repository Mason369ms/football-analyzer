# Football Analyzer

[![中文](https://img.shields.io/badge/语言-中文-blue.svg)](README_zh.md)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Vue.js](https://img.shields.io/badge/Vue.js-3.x-brightgreen.svg)](https://vuejs.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An independent football match data analysis and LLM intelligent prediction system. Fetches real-time match data from lottery APIs, generates match predictions through odds analysis and machine learning models, and supports Web dashboard visualization.

![Dashboard Preview](docs/images/dashboard.png)

## ✨ Features

### Core Features
- 🏟️ **Match Data Fetching** - Real-time match list and results from lottery API
- 📊 **Deep Odds Analysis** - European odds implied probability, Asian handicap/over-under direction, anomaly detection
- 🤖 **LLM Intelligent Analysis** - AI-powered match analysis using OpenAI-compatible API
- 📈 **Skill Predictor** - Simplified prediction model based on local odds data
- 📋 **Hit Rate Tracking** - Automatic prediction hit rate calculation (win/draw/lose, score, goals)

### Web Dashboard
- 🌐 **Vue 3 Modern Frontend** - Responsive interface based on Element Plus + ECharts
- 📱 **Mobile Responsive** - Full responsive design for phones and tablets
- 🔄 **Real-time Progress** - SSE real-time task progress and log streaming
- 📊 **Data Visualization** - Odds trend charts, hit rate statistics
- 👥 **Multi-user Support** - Independent user authentication, data isolation

### Data Management
- 📦 **Batch Operations** - Support batch fetching, analysis, and deletion
- 🔍 **Detailed Data** - Head-to-head history, recent form, squad info, league standings
- 💾 **Data Export** - PDF and Excel report export
- 🗑️ **Data Cleanup** - Single and batch deletion of matches and analyses

## 🚀 Quick Start

### Requirements

- Python 3.8+
- Node.js 18+ (for frontend development)
- npm or yarn

### Installation

#### 1. Clone Repository

```bash
git clone https://github.com/Mason369ms/football-analyzer.git
cd football-analyzer
```

#### 2. Backend Setup

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# Linux/macOS
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### 3. Frontend Setup

```bash
# Enter frontend directory
cd frontend

# Install dependencies
npm install

# Development mode (hot reload)
npm run dev

# Production build
npm run build
```

#### 4. Configure LLM API (Required)

Configure API Key before using LLM analysis:

**Method 1: Quick Setup via Command Line (Recommended)**

```bash
# Set PYTHONPATH
$env:PYTHONPATH='src'  # Windows PowerShell
export PYTHONPATH=src   # Linux/macOS

# Quick setup API Key
python scripts/quick_setup.py YOUR_API_KEY

# Or with custom configuration
python scripts/quick_setup.py --key YOUR_API_KEY --url https://api.deepseek.com/v1 --model deepseek-chat
```

**Method 2: Via Dashboard**

Start the dashboard and configure API in "Settings" page.

**Method 3: Interactive Setup**

```bash
python scripts/set_api_key.py
```

### Start Services

#### Development Mode

```bash
# Terminal 1: Start backend
$env:PYTHONPATH='src'
python -m football_sim.cli dashboard --server fastapi --host 127.0.0.1 --port 8766

# Terminal 2: Start frontend (optional, for frontend development)
cd frontend
npm run dev
```

Visit http://localhost:3001 (frontend dev server) or http://localhost:8766 (backend service)

#### Production Mode

```bash
# Build frontend
cd frontend
npm run build
cd ..

# Start service
$env:PYTHONPATH='src'
python -m football_sim.cli dashboard --server fastapi --host 0.0.0.0 --port 8766
```

Visit http://localhost:8766

### Docker Deployment

```bash
# Set admin account (optional)
$env:FOOTBALL_ADMIN_USER='admin'
$env:FOOTBALL_ADMIN_PASSWORD='your-secure-password'

# Start service
docker compose up -d --build

# View logs
docker compose logs -f

# Stop service
docker compose down
```

Visit http://localhost:8766

## 📖 Usage Guide

### CLI Commands

All CLI commands are invoked via `python -m football_sim.cli`:

```bash
# Set PYTHONPATH (required)
$env:PYTHONPATH='src'

# Fetch today's matches
python -m football_sim.cli fetch-matches --date today

# Get match details and odds
python -m football_sim.cli fetch-details --date 2026-06-06

# LLM analysis
python -m football_sim.cli analyze --date 2026-06-06

# Generate odds report
python -m football_sim.cli odds-report --date today

# Get match results
python -m football_sim.cli fetch-results --date 2026-06-06

# Start web dashboard
python -m football_sim.cli dashboard --port 8766
```

### Web Dashboard Features

#### 1. Match List
- View all matches for the day
- Fetch match and odds data
- Single/batch delete matches
- Single/batch analyze matches

#### 2. Match Details
- Complete match information
- Odds summary (European implied probability, Asian direction, O/U direction)
- Odds change trend chart
- Run LLM analysis

#### 3. Analysis Details
- Prediction results (win/draw/lose, score, goals)
- Complete analysis text
- Export PDF report

#### 4. Recent Analyses
- View all analysis records
- Sorted by match number
- View hit rate statistics
- Fetch match results

## 🏗️ Architecture

### Source Structure

```
src/football_sim/
├── __init__.py              # Module declaration
├── auth.py                  # User authentication (PBKDF2-SHA256)
├── cli.py                   # CLI entry point
├── dashboard.py             # stdlib HTTP dashboard
├── fastapi_app.py           # FastAPI multi-user dashboard
├── history_db.py            # SQLite database management
├── launcher.py              # Launcher entry point
├── models.py                # Data models
├── user_workspace.py        # User workspace management
├── config.py                # Configuration management
├── cache.py                 # Cache layer
├── monitoring.py            # Monitoring and logging
├── export.py                # Data export (PDF/Excel)
├── backup.py                # Data backup
├── scheduler.py             # Scheduled tasks
├── retry.py                 # Retry mechanism
├── logger.py                # Structured logging
├── analysis/
│   ├── odds_analyzer.py     # Odds analysis engine
│   ├── llm_analyzer.py      # LLM analysis core
│   └── skill_predictor.py   # Skill predictor
├── data_sources/
│   ├── http_client.py       # HTTP client tools
│   ├── match_fetcher.py     # Match data fetching
│   ├── match_store.py       # Match data storage
│   └── odds_fetcher.py      # Odds data fetching
├── prompts/
│   └── match_analysis.py    # LLM prompt templates
└── reports/
    └── text_report.py       # Text report generation
```

### Frontend Structure

```
frontend/
├── src/
│   ├── main.ts              # Entry file
│   ├── App.vue              # Root component
│   ├── router/index.ts      # Router configuration
│   ├── layouts/
│   │   └── MainLayout.vue   # Main layout
│   ├── views/
│   │   ├── Dashboard.vue    # Dashboard
│   │   ├── MatchDetail.vue  # Match details
│   │   └── AnalysisDetail.vue # Analysis details
│   ├── utils/
│   │   └── api.ts           # API wrapper
│   └── assets/
│       └── main.scss        # Global styles
├── package.json
├── vite.config.ts
└── tsconfig.json
```

### Data Flow

```
Match Data Fetching (match_fetcher)
       ↓
Match Data Storage (match_store)
       ↓
Odds Data Fetching (odds_fetcher)
       ↓
Odds Analysis (odds_analyzer)
       ↓
LLM Analysis (llm_analyzer)
       ↓
Skill Prediction (skill_predictor)
       ↓
Report Generation (text_report)
       ↓
Web Dashboard Display (fastapi_app)
```

### Data Directory

```
data/
├── app_football.sqlite3     # Authentication database
├── matches/                 # Match data (stored by date)
│   └── 2026-06-06/
│       └── 周六217_国际友谊_阿根廷_vs_洪都拉斯/
│           ├── 赛事信息.json
│           ├── 赔率变化数据.json
│           ├── 两队比赛历史交锋数据.json
│           └── ...
└── users/
    └── <username>/
        └── history.sqlite3  # User history database
```

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PYTHONPATH` | `src` | Required, points to source directory |
| `FOOTBALL_HOST` | `127.0.0.1` | Dashboard listen address |
| `FOOTBALL_PORT` | `8766` | Dashboard listen port |
| `FOOTBALL_OPEN_BROWSER` | `1` | Auto-open browser on start |
| `FOOTBALL_ADMIN_USER` | `admin` | Initial admin username |
| `FOOTBALL_ADMIN_PASSWORD` | `admin` | Initial admin password |
| `FOOTBALL_SSL_VERIFY` | `true` | SSL certificate verification |
| `FOOTBALL_RETRY_COUNT` | `3` | HTTP request retry count |
| `FOOTBALL_USE_PROXY` | `false` | Use proxy |

### LLM Configuration

Configure via Web dashboard "Settings" page:

- **LLM Provider**: `openai`, `deepseek`, or other OpenAI-compatible API
- **API URL**: e.g., `https://api.openai.com/v1` or `https://api.deepseek.com/v1`
- **Model Name**: e.g., `gpt-4`, `deepseek-chat`
- **API Key**: Your API key

## 🧪 Testing

```bash
# Set PYTHONPATH
$env:PYTHONPATH='src'

# Run all tests
python -m pytest tests/ -v

# Run specific test
python -m pytest tests/test_auth.py -v

# Generate coverage report
python -m pytest tests/ --cov=football_sim --cov-report=html
```

## 📦 EXE Packaging

```powershell
.\scripts\build_exe.ps1
```

Output in `dist\football-analyzer\`. `launcher.py` is the entry point, auto-selecting FastAPI or stdlib mode.

## 🔧 Development Guide

### Project Conventions

- Tests use `unittest` (not pytest fixtures)
- Test files in `tests/`
- Each test class uses `_temp_dir()` context manager for isolated temp directories
- FastAPI tests use `TestClient`
- Database operations use SQLite with multi-user isolation
- Frontend uses Vue 3 Composition API + TypeScript

### Key Design Patterns

- **Data Source Pattern**: Each data source (matches, odds) implemented independently
- **Analyzer Pattern**: Odds analysis, LLM analysis, skill prediction are independent and composable
- **Workspace Pattern**: Per-user data directory, report directory, and database isolation
- **Authentication Pattern**: PBKDF2-SHA256 password hashing, session management
- **SSE Push Pattern**: Real-time task progress via Server-Sent Events
- **Cache Pattern**: Multi-level cache (memory, Redis, file) with auto-expiry
- **Retry Pattern**: Exponential backoff with configurable max retries

### Platform Notes

Project developed on Windows (PowerShell), but supports Linux/macOS:

- **Virtual env**: Windows `.\.venv\Scripts\Activate.ps1`, Linux/macOS `source .venv/bin/activate`
- **PYTHONPATH**: Required before all CLI commands (PowerShell: `$env:PYTHONPATH='src'`, Linux: `export PYTHONPATH=src`)
- **Paths**: Code uses `pathlib.Path` for cross-platform path handling

## 📊 Performance Optimization

- **Database Indexes**: Added indexes for frequently queried fields
- **Connection Pool**: SQLite connection pool management
- **Cache Layer**: Multi-level cache reducing database queries
- **Async Processing**: aiohttp for odds fetching, streaming for LLM calls
- **Batch Operations**: Support batch insert and update

## 🔒 Security Features

- **Password Hashing**: PBKDF2-SHA256, 260,000 iterations
- **Session Management**: 7-day validity, IP binding support
- **SQL Injection Protection**: Parameterized queries
- **CSRF Protection**: Form submission validation
- **Input Validation**: Pydantic model validation

## 📈 Monitoring and Logging

- **Structured Logging**: JSON format with log level filtering
- **Health Checks**: `/health` and `/health/detailed` endpoints
- **Prometheus Metrics**: `/metrics` endpoint
- **Request Tracing**: Automatic request duration and status recording
- **Error Tracking**: Sentry integration (optional)

## 🤝 Contributing

Contributions welcome! Please follow these steps:

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Create Pull Request

### Code Standards

- Python: Follow PEP 8
- TypeScript: Use ESLint + Prettier
- Commit messages: Use descriptive format

## 📝 Changelog

### v1.0.0 (2026-06-06)
- ✨ Initial release
- 🏟️ Match data fetching
- 📊 Deep odds analysis
- 🤖 LLM intelligent analysis
- 🌐 Vue 3 modern frontend
- 📱 Responsive design
- 🔄 Real-time progress display
- 👥 Multi-user support
- 🐳 Docker deployment

## 📄 License

MIT License - see [LICENSE](LICENSE) file

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern, fast Python web framework
- [Vue.js](https://vuejs.org/) - Progressive JavaScript framework
- [Element Plus](https://element-plus.org/) - Vue 3 UI component library
- [ECharts](https://echarts.apache.org/) - Data visualization chart library
- [Pydantic](https://docs.pydantic.dev/) - Data validation and settings management

## 📞 Contact

- Repository: https://github.com/Mason369ms/football-analyzer
- Issues: [Issues](https://github.com/Mason369ms/football-analyzer/issues)

---

⭐ If this project helps you, please give it a Star!
