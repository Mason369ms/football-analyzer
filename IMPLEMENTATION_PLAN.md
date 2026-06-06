# Football Analyzer - 全面改进实施计划

## 📋 实施概览

本计划涵盖除安全性外的所有改进项，按优先级和依赖关系分阶段实施。

---

## 🎯 实施阶段

### 阶段 1：基础设施优化（第 1-2 周）
**目标**：提升系统可靠性和性能基础

#### 1.1 数据库优化 [Task #2]
- [x] 添加数据库索引
- [ ] 实现 WAL 模式
- [ ] 添加连接池管理
- [ ] 优化慢查询

#### 1.2 缓存层实现 [Task #3]
- [ ] 实现内存缓存（TTLCache）
- [ ] 为频繁查询添加缓存
- [ ] 实现缓存失效策略

#### 1.3 结构化日志 [Task #5]
- [ ] 实现 JSON 格式日志
- [ ] 添加日志级别配置
- [ ] 集成日志轮转

---

### 阶段 2：代码质量提升（第 2-3 周）
**目标**：提高代码可维护性和可测试性

#### 2.1 类型注解完善 [Task #4]
- [ ] 为所有函数添加类型注解
- [ ] 引入 Pydantic 模型
- [ ] 配置 mypy 类型检查

#### 2.2 配置管理改进 [Task #4]
- [ ] 实现 Pydantic Settings
- [ ] 创建 .env.example
- [ ] 配置分环境管理

#### 2.3 错误处理改进 [Task #3]
- [ ] 实现重试队列
- [ ] LLM 降级策略
- [ ] 用户友好的错误提示

---

### 阶段 3：监控与运维（第 3-4 周）
**目标**：建立完整的可观测性体系

#### 3.1 监控指标 [Task #5]
- [ ] 集成 Prometheus metrics
- [ ] 添加请求延迟指标
- [ ] 业务指标收集

#### 3.2 健康检查增强 [Task #6]
- [ ] 详细健康检查端点
- [ ] 依赖服务检查
- [ ] 资源使用监控

#### 3.3 Docker 生产配置 [Task #6]
- [ ] 创建生产级 Dockerfile
- [ ] 资源限制配置
- [ ] 日志轮转配置
- [ ] 健康检查优化

---

### 阶段 4：功能增强（第 4-5 周）
**目标**：提升产品功能完整性

#### 4.1 数据导出 [Task #7]
- [ ] PDF 报告生成
- [ ] Excel 数据导出
- [ ] 批量导出支持

#### 4.2 批量分析优化 [Task #7]
- [ ] 并行分析实现
- [ ] 进度实时反馈
- [ ] 失败重试机制

#### 4.3 自动化调度 [Task #7]
- [ ] 集成 APScheduler
- [ ] 定时数据抓取
- [ ] 定时报告生成

---

### 阶段 5：用户体验提升（第 5-7 周）
**目标**：改善前端交互和可视化

#### 5.1 前端框架升级 [Task #8]
- [ ] 引入 Vue 3
- [ ] 集成 Element Plus
- [ ] 组件化重构

#### 5.2 数据可视化 [Task #8]
- [ ] 集成 ECharts
- [ ] 赔率趋势图
- [ ] 命中率统计图

#### 5.3 移动端适配 [Task #8]
- [ ] 响应式布局
- [ ] PWA 支持
- [ ] 手势操作

---

### 阶段 6：测试完善（第 5-7 周，与阶段 5 并行）
**目标**：提升代码质量和可靠性

#### 6.1 单元测试 [Task #9]
- [ ] analysis 模块测试
- [ ] data_sources 模块测试
- [ ] 覆盖率达到 70%

#### 6.2 集成测试 [Task #9]
- [ ] API 端点测试
- [ ] 数据库集成测试
- [ ] LLM 调用模拟测试

---

## 📊 详细实施方案

### 1. 数据库优化实施方案

#### 1.1 添加索引
```sql
-- analyses 表索引
CREATE INDEX IF NOT EXISTS idx_analyses_match_id ON analyses(match_id);
CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses(created_at);
CREATE INDEX IF NOT EXISTS idx_analyses_user_key ON analyses(user_key);

-- matches 表索引
CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(date);
CREATE INDEX IF NOT EXISTS idx_matches_match_id ON matches(match_id);

-- match_results 表索引
CREATE INDEX IF NOT EXISTS idx_match_results_match_id ON match_results(match_id);

-- dashboard_actions 表索引
CREATE INDEX IF NOT EXISTS idx_dashboard_actions_created_at ON dashboard_actions(created_at);
```

#### 1.2 WAL 模式
```python
def init_history_db(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-2000")  # 2MB 缓存
        conn.execute("PRAGMA temp_store=MEMORY")
```

#### 1.3 连接池
```python
from contextlib import contextmanager
import sqlite3
from queue import Queue

class SQLitePool:
    def __init__(self, db_path, max_connections=5):
        self.db_path = db_path
        self.pool = Queue(max_connections)
        for _ in range(max_connections):
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            self.pool.put(conn)

    @contextmanager
    def get_connection(self):
        conn = self.pool.get()
        try:
            yield conn
        finally:
            self.pool.put(conn)
```

---

### 2. 缓存层实施方案

#### 2.1 内存缓存
```python
from cachetools import TTLCache
from functools import wraps
import hashlib
import json

# 全局缓存实例
analysis_cache = TTLCache(maxsize=1000, ttl=300)  # 5 分钟
match_cache = TTLCache(maxsize=500, ttl=600)  # 10 分钟

def cached(cache, key_func=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = hashlib.md5(
                    json.dumps([str(args), str(kwargs)]).encode()
                ).hexdigest()

            # 尝试从缓存获取
            if cache_key in cache:
                return cache[cache_key]

            # 执行函数并缓存结果
            result = func(*args, **kwargs)
            cache[cache_key] = result
            return result
        return wrapper
    return decorator

# 使用示例
@cached(analysis_cache)
def get_analysis_with_results(db_path, limit=50):
    # 实际查询逻辑
    ...
```

#### 2.2 缓存失效策略
```python
def invalidate_match_cache(match_id):
    """使指定比赛的所有缓存失效"""
    keys_to_remove = [k for k in match_cache.keys() if match_id in str(k)]
    for key in keys_to_remove:
        del match_cache[key]

def invalidate_analysis_cache(match_id=None):
    """使分析缓存失效"""
    if match_id:
        keys_to_remove = [k for k in analysis_cache.keys() if match_id in str(k)]
    else:
        keys_to_remove = list(analysis_cache.keys())
    for key in keys_to_remove:
        del analysis_cache[key]
```

---

### 3. 结构化日志实施方案

#### 3.1 JSON 日志格式
```python
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)

        return json.dumps(log_data, ensure_ascii=False)

def setup_logging(level=logging.INFO):
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

    logger = logging.getLogger("football_sim")
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger

logger = setup_logging()

# 使用示例
logger.info("比赛分析完成", extra={
    "extra_data": {
        "match_id": "12345",
        "home_team": "主队",
        "away_team": "客队",
        "confidence": 85
    }
})
```

---

### 4. 监控指标实施方案

#### 4.1 Prometheus Metrics
```python
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi import Request
import time

# 定义指标
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

ACTIVE_CONNECTIONS = Gauge(
    'active_connections',
    'Number of active connections'
)

LLM_CALLS = Counter(
    'llm_calls_total',
    'Total LLM API calls',
    ['status']  # success, error, timeout
)

ANALYSIS_COUNT = Counter(
    'analyses_total',
    'Total analyses performed',
    ['result']  # success, failed
)

# FastAPI 中间件
@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    start_time = time.time()

    response = await call_next(request)

    duration = time.time() - start_time
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()

    REQUEST_DURATION.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)

    return response

# Metrics 端点
@app.get("/metrics")
async def metrics():
    return Response(
        content=generate_latest(),
        media_type="text/plain"
    )
```

---

### 5. Docker 生产配置

#### 5.1 生产级 Dockerfile
```dockerfile
FROM python:3.12-slim as builder

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim

WORKDIR /app

# 复制依赖
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制应用代码
COPY src ./src
COPY README.md LICENSE ./

# 创建必要目录
RUN mkdir -p data/matches data/users reports/latest reports/users /app/logs

# 环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PYTHONPATH=/app/src \
    FOOTBALL_HOST=0.0.0.0 \
    FOOTBALL_PORT=8766 \
    TZ=Asia/Shanghai

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8766/health', timeout=3).read()" || exit 1

# 暴露端口
EXPOSE 8766

# 启动命令
CMD ["python", "-m", "football_sim.cli", "dashboard", "--server", "fastapi", "--host", "0.0.0.0", "--port", "8766"]
```

#### 5.2 生产 docker-compose
```yaml
# docker-compose.prod.yml
services:
  football-analyzer:
    build:
      context: .
      dockerfile: Dockerfile.prod
    image: football-analyzer:latest
    container_name: football-analyzer
    ports:
      - "8766:8766"
    environment:
      FOOTBALL_ADMIN_USER: ${FOOTBALL_ADMIN_USER}
      FOOTBALL_ADMIN_PASSWORD: ${FOOTBALL_ADMIN_PASSWORD}
      FOOTBALL_LLM_API_KEY: ${FOOTBALL_LLM_API_KEY}
      PYTHONPATH: /app/src
      PYTHONUTF8: "1"
      TZ: Asia/Shanghai
    volumes:
      - ./data:/app/data
      - ./reports:/app/reports
      - ./logs:/app/logs
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"
    restart: unless-stopped
    networks:
      - football-network

  # 可选：Redis 缓存
  redis:
    image: redis:7-alpine
    container_name: football-redis
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes
    restart: unless-stopped
    networks:
      - football-network

networks:
  football-network:
    driver: bridge

volumes:
  redis-data:
```

---

### 6. 数据导出实施方案

#### 6.1 PDF 生成
```python
from weasyprint import HTML
from jinja2 import Template

PDF_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #172033; border-bottom: 2px solid #1d4ed8; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { border: 1px solid #d7dde5; padding: 8px; text-align: left; }
        th { background: #f8f9fb; }
        .prediction { background: #ecfdf5; padding: 10px; border-radius: 4px; }
    </style>
</head>
<body>
    <h1>{{ league }}: {{ home_team }} vs {{ away_team }}</h1>
    <p><strong>比赛时间:</strong> {{ match_time }}</p>
    <p><strong>分析时间:</strong> {{ created_at }}</p>

    <h2>预测结果</h2>
    <div class="prediction">
        <p><strong>胜平负:</strong> {{ prediction_outcome }}</p>
        <p><strong>比分:</strong> {{ prediction_score }}</p>
        <p><strong>进球数:</strong> {{ prediction_goals }}</p>
        <p><strong>置信度:</strong> {{ confidence }}%</p>
    </div>

    <h2>详细分析</h2>
    <div>{{ analysis_text }}</div>
</body>
</html>
"""

def generate_pdf(analysis_data, output_path):
    template = Template(PDF_TEMPLATE)
    html_content = template.render(**analysis_data)

    HTML(string=html_content).write_pdf(output_path)
    return output_path

@app.get("/api/export/pdf/{analysis_id}")
async def export_pdf(analysis_id: int):
    workspace = workspace_for_user(root_path, "default")
    analysis = load_analysis_by_id(workspace.history_db, analysis_id)

    if not analysis:
        raise HTTPException(status_code=404, detail="分析记录不存在")

    output_path = f"/tmp/analysis_{analysis_id}.pdf"
    generate_pdf(analysis, output_path)

    return FileResponse(
        output_path,
        media_type="application/pdf",
        filename=f"分析报告_{analysis_id}.pdf"
    )
```

#### 6.2 Excel 导出
```python
import pandas as pd
from io import BytesIO

@app.get("/api/export/excel")
async def export_excel(date: str = "", limit: int = 100):
    workspace = workspace_for_user(root_path, "default")
    analyses = get_analysis_with_results(workspace.history_db, limit=limit)

    df = pd.DataFrame(analyses)
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='分析记录', index=False)

    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=analyses_{date}.xlsx"}
    )
```

---

### 7. 批量并行分析

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

class BatchAnalyzer:
    def __init__(self, max_workers=3):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.results = {}
        self.progress = {}

    async def analyze_batch(self, match_ids, llm_config):
        """并行分析多个比赛"""
        loop = asyncio.get_event_loop()
        tasks = []

        for match_id in match_ids:
            self.progress[match_id] = {"status": "pending", "progress": 0}
            task = loop.run_in_executor(
                self.executor,
                self._analyze_single,
                match_id,
                llm_config
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for match_id, result in zip(match_ids, results):
            if isinstance(result, Exception):
                self.progress[match_id] = {"status": "failed", "error": str(result)}
            else:
                self.progress[match_id] = {"status": "completed", "result": result}

        return self.progress

    def _analyze_single(self, match_id, llm_config):
        """单个比赛分析（在线程池中执行）"""
        # 实际分析逻辑
        ...
```

---

### 8. 自动化调度

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job(CronTrigger(hour=8, minute=0))
async def daily_fetch_matches():
    """每天 8 点抓取今日赛事"""
    logger.info("开始每日赛事抓取")
    try:
        # 调用抓取逻辑
        ...
        logger.info("每日赛事抓取完成")
    except Exception as e:
        logger.error(f"每日赛事抓取失败: {e}")

@scheduler.scheduled_job(CronTrigger(hour=9, minute=0))
async def daily_analyze():
    """每天 9 点自动分析今日赛事"""
    logger.info("开始每日赛事分析")
    try:
        # 调用分析逻辑
        ...
        logger.info("每日赛事分析完成")
    except Exception as e:
        logger.error(f"每日赛事分析失败: {e}")

def start_scheduler():
    scheduler.start()
    logger.info("定时任务调度器已启动")
```

---

## 📅 时间线

| 周次 | 阶段 | 主要任务 | 产出 |
|------|------|---------|------|
| 1-2 | 基础设施 | 数据库优化、缓存层、日志 | 性能提升 50%+ |
| 2-3 | 代码质量 | 类型注解、配置管理、错误处理 | 可维护性提升 |
| 3-4 | 监控运维 | Prometheus、健康检查、Docker | 可观测性完善 |
| 4-5 | 功能增强 | 导出、批量分析、调度 | 功能完整性 |
| 5-7 | 用户体验 | 前端升级、可视化、移动端 | 用户满意度提升 |
| 5-7 | 测试完善 | 单元测试、集成测试 | 覆盖率 70%+ |

---

## ✅ 验收标准

1. **性能指标**
   - API 响应时间 < 200ms (95th percentile)
   - 数据库查询 < 50ms
   - 缓存命中率 > 80%

2. **可靠性指标**
   - 系统可用性 > 99.5%
   - 错误率 < 1%
   - 数据备份成功率 100%

3. **代码质量**
   - 测试覆盖率 > 70%
   - 类型检查通过率 100%
   - 日志结构化率 100%

4. **用户体验**
   - 页面加载时间 < 2s
   - 移动端适配完成
   - 导出功能可用

---

## 🚀 立即开始

从阶段 1 开始实施，首先进行数据库优化...
