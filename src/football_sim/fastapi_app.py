import json
import os
import sqlite3
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs

from football_sim.auth import AuthStore, SESSION_COOKIE_NAME, SESSION_TTL_DAYS
from football_sim.dashboard import (
    DashboardJob,
    load_dashboard_model,
    render_dashboard_html,
)
from football_sim.history_db import init_history_db, load_dashboard_config, save_dashboard_config
from football_sim.user_workspace import workspace_for_user
from football_sim.logger import get_logger, setup_logging
from football_sim.config import get_settings, init_config
from football_sim.cache import start_cache_cleanup, get_all_cache_stats, invalidate_match_caches
from football_sim.monitoring import (
    get_metrics_collector,
    get_health_checker,
    init_monitoring,
    get_prometheus_metrics,
    get_health_status,
    track_request,
)
from football_sim.export import get_exporter

# 初始化日志
logger = get_logger(__name__)

# 初始化配置
settings = init_config()
setup_logging(level=settings.logging.level, json_format=settings.logging.json_format)

# 初始化监控
init_monitoring(version="1.0.0")

# 启动缓存清理
start_cache_cleanup()

_DASHBOARD_JOBS: Dict[str, DashboardJob] = {}
_DASHBOARD_JOBS_LOCK = None


def _get_jobs_lock():
    import threading
    global _DASHBOARD_JOBS_LOCK
    if _DASHBOARD_JOBS_LOCK is None:
        _DASHBOARD_JOBS_LOCK = threading.Lock()
    return _DASHBOARD_JOBS_LOCK


def _get_dashboard_job(job_id: str) -> Optional[DashboardJob]:
    with _get_jobs_lock():
        return _DASHBOARD_JOBS.get(job_id)


def _job_snapshot(job: DashboardJob) -> Dict[str, Any]:
    with job.lock:
        return {
            "job_id": job.job_id,
            "action": job.action,
            "match_id": job.match_id,
            "status": job.status,
            "stage_label": job.stage_label,
            "stage_index": job.stage_index,
            "exit_code": job.exit_code,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
            "output_lines": list(job.output_lines),
        }


def _job_sse_events(job: DashboardJob):
    import time
    last_index = 0
    while True:
        with job.lock:
            if job.status == "finished":
                lines = job.output_lines[last_index:]
                for line in lines:
                    yield f"data: {json.dumps({'line': line}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'done': True, 'exit_code': job.exit_code}, ensure_ascii=False)}\n\n"
                return
            lines = job.output_lines[last_index:]
            for line in lines:
                yield f"data: {json.dumps({'line': line}, ensure_ascii=False)}\n\n"
            last_index = len(job.output_lines)
        time.sleep(0.2)


def start_batch_analyze_job(
    match_ids: list,
    root_path: Path,
    data_dir: Optional[Path] = None,
    user_key: str = "",
) -> DashboardJob:
    """启动批量分析任务"""
    import subprocess
    import sys
    import threading
    import time
    import uuid

    job_id = uuid.uuid4().hex[:8]
    date_str = datetime.now().strftime("%Y-%m-%d")
    data_dir = data_dir or root_path / "data" / "users" / "default"
    matches_dir = data_dir.parent.parent / "matches"
    db_path = data_dir / "history.sqlite3"

    # 构建批量分析命令
    cmd = [sys.executable, "-m", "football_sim.cli", "analyze", "--match-ids", ",".join(match_ids), "--db-path", str(db_path)]
    stage_labels = (f"批量分析 {len(match_ids)} 场比赛",)

    job = DashboardJob(
        job_id=job_id,
        action="batch-analyze",
        match_id=",".join(match_ids[:3]) + ("..." if len(match_ids) > 3 else ""),
        command=tuple(cmd),
        stage_labels=stage_labels,
        user_key=user_key,
    )

    def run_job():
        env = {**os.environ, "PYTHONPATH": str(root_path / "src")}
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
            job.started_at = time.time()
            for line in proc.stdout or []:
                with job.lock:
                    job.output_lines.append(line.rstrip())
            proc.wait()
            job.exit_code = proc.returncode
            job.status = "finished"
        except Exception as e:
            with job.lock:
                job.output_lines.append(f"Error: {e}")
            job.exit_code = 1
            job.status = "finished"
        finally:
            job.finished_at = time.time()

    with _get_jobs_lock():
        _DASHBOARD_JOBS[job_id] = job

    thread = threading.Thread(target=run_job, daemon=True)
    thread.start()
    return job


def start_dashboard_job(
    action: str,
    root_path: Path,
    match_id: str = "",
    data_dir: Optional[Path] = None,
    user_key: str = "",
) -> DashboardJob:
    import subprocess
    import sys
    import threading
    import time
    import uuid

    job_id = uuid.uuid4().hex[:8]
    date_str = datetime.now().strftime("%Y-%m-%d")
    data_dir = data_dir or root_path / "data" / "users" / "default"
    matches_dir = data_dir.parent.parent / "matches"
    db_path = data_dir / "history.sqlite3"

    if action == "fetch-list":
        cmd = [sys.executable, "-m", "football_sim.cli", "fetch-matches", "--date", "today", "--output", str(matches_dir), "--db-path", str(db_path)]
        stage_labels = ("抓取赛事列表",)
    elif action == "fetch-all":
        # fetch-all = 抓取赛事列表 + 赔率详情
        cmd = [sys.executable, "-m", "football_sim.cli", "fetch-matches", "--date", "today", "--with-odds", "--output", str(matches_dir), "--db-path", str(db_path)]
        stage_labels = ("抓取赛事列表和赔率",)
    elif action == "fetch-details":
        cmd = [sys.executable, "-m", "football_sim.cli", "fetch-details", "--date", date_str, "--output", str(matches_dir), "--db-path", str(db_path)]
        stage_labels = ("抓取赛事详情和赔率",)
    elif action == "analyze":
        if match_id:
            # 从数据库查找 match_id 对应的 data_dir
            from football_sim.history_db import load_matches as _load_matches
            _matches = _load_matches(db_path, limit=2000)
            _match = next((m for m in _matches if m.get("match_id") == match_id), None)
            if _match and _match.get("data_dir"):
                match_dir_path = _match["data_dir"]
                if not Path(match_dir_path).is_absolute():
                    match_dir_path = str(root_path / match_dir_path)
            else:
                # 兜底：尝试用 match_id 作目录名
                match_dir_path = str(matches_dir / date_str / match_id)
            cmd = [sys.executable, "-m", "football_sim.cli", "analyze", "--match-dir", match_dir_path, "--db-path", str(db_path)]
        else:
            cmd = [sys.executable, "-m", "football_sim.cli", "analyze", "--date", date_str, "--db-path", str(db_path)]
        stage_labels = ("LLM 分析赛事",)
    elif action == "odds-report":
        cmd = [sys.executable, "-m", "football_sim.cli", "odds-report", "--date", date_str]
        stage_labels = ("生成赔率报告",)
    elif action == "fetch-results":
        cmd = [sys.executable, "-m", "football_sim.cli", "fetch-results", "--date", date_str, "--db-path", str(db_path)]
        stage_labels = ("获取比赛结果",)
    else:
        raise ValueError(f"Unknown action: {action}")

    job = DashboardJob(
        job_id=job_id,
        action=action,
        match_id=match_id,
        command=tuple(cmd),
        stage_labels=stage_labels,
        user_key=user_key,
    )

    def run_job():
        env = {**os.environ, "PYTHONPATH": str(root_path / "src")}
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
            job.started_at = time.time()
            for line in proc.stdout or []:
                with job.lock:
                    job.output_lines.append(line.rstrip())
            proc.wait()
            job.exit_code = proc.returncode
            job.status = "finished"
        except Exception as e:
            with job.lock:
                job.output_lines.append(f"Error: {e}")
            job.exit_code = 1
            job.status = "finished"
        finally:
            job.finished_at = time.time()

    with _get_jobs_lock():
        _DASHBOARD_JOBS[job_id] = job

    thread = threading.Thread(target=run_job, daemon=True)
    thread.start()
    return job


def create_fastapi_app(reports_dir: Path, repo_root: Path):
    try:
        from fastapi import FastAPI, Request
        from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
    except ModuleNotFoundError as exc:
        raise RuntimeError(f"FastAPI 服务需要先安装依赖：{FASTAPI_INSTALL_HINT}") from exc

    root_path = Path(repo_root)
    auth_store = AuthStore(root_path / "data" / "app_football.sqlite3")
    _bootstrap_admin_user(auth_store)
    app = FastAPI(title="足球赛事分析系统")

    # 静态文件服务
    static_dir = root_path / "src" / "football_sim" / "static"
    if static_dir.exists():
        from fastapi.staticfiles import StaticFiles
        app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

    # 添加请求跟踪中间件
    @app.middleware("http")
    async def track_requests_middleware(request, call_next):
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time

        # 记录请求指标
        get_metrics_collector().record_http_request(
            method=request.method,
            endpoint=request.url.path,
            status_code=response.status_code,
            duration=duration
        )

        # 添加响应头
        response.headers["X-Process-Time"] = str(round(duration, 4))

        return response

    def current_user(request: Request):
        token = request.cookies.get(SESSION_COOKIE_NAME, "")
        if not token:
            return None
        return auth_store.get_session_user(token)

    def unauthorized_api_response():
        return JSONResponse({"ok": False, "error": "authentication required"}, status_code=401)

    @app.get("/", response_class=HTMLResponse)
    @app.get("/index.html", response_class=HTMLResponse)
    async def index(request: Request):
        # 检查是否有 Vue 前端构建文件
        static_dir = root_path / "src" / "football_sim" / "static"
        index_file = static_dir / "index.html"

        if index_file.exists():
            # 服务 Vue 前端
            return HTMLResponse(index_file.read_text(encoding="utf-8"))

        # 回退到旧版 HTML 模板
        workspace = workspace_for_user(root_path, "default")
        init_history_db(workspace.history_db)
        page = render_dashboard_html(load_dashboard_model(data_dir=workspace.data_dir))
        return HTMLResponse(page)

    # API 路由（优先级最高）
    @app.get("/health")
    async def health():
        """健康检查端点"""
        health_status = get_health_status()
        status_code = 200 if health_status["status"] == "healthy" else 503
        return JSONResponse(health_status, status_code=status_code)

    @app.get("/health/detailed")
    async def health_detailed():
        """详细健康检查"""
        return get_health_status()

    @app.get("/metrics")
    async def metrics():
        """Prometheus metrics 端点"""
        from fastapi.responses import Response
        metrics_data = get_prometheus_metrics()
        content_type = get_metrics_collector().get_metrics_content_type()
        return Response(content=metrics_data, media_type=content_type)

    @app.get("/api/stats")
    async def stats():
        """系统统计信息"""
        return {
            "metrics": get_metrics_collector().get_stats(),
            "cache": get_all_cache_stats(),
            "timestamp": datetime.now().isoformat()
        }

    @app.get("/api/config")
    async def get_config(request: Request):
        """获取配置"""
        return settings.to_dict()

    @app.post("/api/config")
    async def save_config(request: Request):
        """保存配置"""
        workspace = workspace_for_user(root_path, "default")
        body = await request.body()
        form = {}
        if body:
            try:
                form = json.loads(body.decode("utf-8"))
            except:
                form = _parse_form_body(body)
        save_dashboard_config(workspace.history_db, form)
        return {"ok": True}

    @app.get("/api/matches")
    async def list_matches(request: Request, date: str = "", limit: int = 100):
        """获取比赛列表"""
        workspace = workspace_for_user(root_path, "default")
        from football_sim.history_db import load_matches
        matches = load_matches(workspace.history_db, date=date or "", limit=limit)
        return {"matches": matches, "count": len(matches)}

    @app.delete("/api/matches/{match_id}")
    async def delete_match(match_id: str, request: Request):
        """删除单个比赛"""
        workspace = workspace_for_user(root_path, "default")
        from football_sim.history_db import delete_match
        deleted = delete_match(workspace.history_db, match_id)
        if deleted:
            # 同时清除相关缓存
            invalidate_match_caches(match_id)
            return {"ok": True, "message": "删除成功"}
        return JSONResponse({"ok": False, "error": "比赛不存在"}, status_code=404)

    @app.post("/api/matches/delete")
    async def delete_matches_batch(request: Request):
        """批量删除比赛"""
        workspace = workspace_for_user(root_path, "default")
        body = await request.json()
        match_ids = body.get("match_ids", [])

        if not match_ids:
            return JSONResponse({"ok": False, "error": "未选择比赛"}, status_code=400)

        from football_sim.history_db import delete_matches
        deleted_count = delete_matches(workspace.history_db, match_ids)

        # 清除相关缓存
        for match_id in match_ids:
            invalidate_match_caches(match_id)

        return {"ok": True, "deleted_count": deleted_count}

    @app.get("/api/match/{match_id}")
    async def get_match_detail(match_id: str, request: Request):
        """获取赛事详情（JSON 格式）"""
        workspace = workspace_for_user(root_path, "default")
        from football_sim.history_db import load_matches, load_analyses

        # 查找赛事
        matches = load_matches(workspace.history_db, limit=1000)
        match = next((m for m in matches if m.get("match_id") == match_id), None)

        if not match:
            return JSONResponse({"ok": False, "error": "比赛不存在"}, status_code=404)

        # 加载赛事数据文件
        match_data = {}
        odds_summary = {}
        data_dir_path = match.get("data_dir", "")

        if data_dir_path:
            match_dir = Path(data_dir_path)
            if not match_dir.is_absolute():
                match_dir = root_path / match_dir

            if match_dir.exists():
                from football_sim.data_sources.match_store import load_match_data
                try:
                    match_data = load_match_data(match_dir)
                except Exception as e:
                    logger.warning(f"加载赛事数据失败: {e}")

                # 加载赔率摘要
                try:
                    from football_sim.analysis.odds_analyzer import generate_odds_summary
                    odds_summary = generate_odds_summary(match_dir)
                except Exception as e:
                    logger.warning(f"生成赔率摘要失败: {e}")

        # 查找分析记录
        analyses = load_analyses(workspace.history_db, match_id=match_id, limit=1)
        analysis = analyses[0] if analyses else None

        return {
            "ok": True,
            "match": match,
            "match_data": match_data,
            "odds_summary": odds_summary,
            "analysis": analysis
        }

    @app.get("/api/analyses")
    async def list_analyses(request: Request, match_id: str = "", limit: int = 50):
        """获取分析列表"""
        workspace = workspace_for_user(root_path, "default")
        from football_sim.history_db import load_analyses
        analyses = load_analyses(workspace.history_db, match_id=match_id or "", limit=limit)
        return {"analyses": analyses, "count": len(analyses)}

    @app.get("/api/analysis/{analysis_id}")
    async def get_analysis_detail(analysis_id: int, request: Request):
        """获取分析详情（JSON 格式）"""
        workspace = workspace_for_user(root_path, "default")
        from football_sim.history_db import load_analysis_by_id

        analysis = load_analysis_by_id(workspace.history_db, analysis_id)

        if not analysis:
            return JSONResponse({"ok": False, "error": "分析记录不存在"}, status_code=404)

        return {"ok": True, "analysis": analysis}

    @app.post("/api/analyses/clear")
    async def clear_analyses(request: Request):
        """清除分析记录"""
        workspace = workspace_for_user(root_path, "default")
        from football_sim.history_db import clear_analyses
        deleted_count = clear_analyses(workspace.history_db)
        return {"ok": True, "deleted_count": deleted_count}

    @app.get("/api/cache/stats")
    async def cache_stats():
        """缓存统计"""
        return get_all_cache_stats()

    @app.post("/api/cache/clear")
    async def clear_cache():
        """清空缓存"""
        from football_sim.cache import invalidate_all_caches
        result = invalidate_all_caches()
        return {"ok": True, "cleared": result}

    @app.post("/api/export/pdf/{analysis_id}")
    async def export_pdf(analysis_id: int, request: Request):
        """导出 PDF 报告"""
        try:
            workspace = workspace_for_user(root_path, "default")
            from football_sim.history_db import load_analysis_by_id
            analysis = load_analysis_by_id(workspace.history_db, analysis_id)

            if not analysis:
                return JSONResponse(
                    {"ok": False, "error": "分析记录不存在"},
                    status_code=404
                )

            exporter = get_exporter()
            pdf_path = exporter.export_pdf(analysis)

            from fastapi.responses import FileResponse
            return FileResponse(
                str(pdf_path),
                media_type="application/pdf",
                filename=pdf_path.name
            )
        except Exception as e:
            logger.error(f"PDF 导出失败: {e}")
            return JSONResponse(
                {"ok": False, "error": str(e)},
                status_code=500
            )

    @app.get("/api/export/excel")
    async def export_excel(request: Request, limit: int = 100):
        """导出 Excel 报告"""
        try:
            workspace = workspace_for_user(root_path, "default")
            from football_sim.history_db import get_analysis_with_results
            analyses = get_analysis_with_results(workspace.history_db, limit=limit)

            exporter = get_exporter()
            excel_path = exporter.export_excel(analyses)

            from fastapi.responses import FileResponse
            return FileResponse(
                str(excel_path),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                filename=excel_path.name
            )
        except Exception as e:
            logger.error(f"Excel 导出失败: {e}")
            return JSONResponse(
                {"ok": False, "error": str(e)},
                status_code=500
            )

    @app.get("/api/run")
    async def api_run(request: Request):
        """SSE endpoint for frontend EventSource compatibility"""
        workspace = workspace_for_user(root_path, "default")
        params = request.query_params
        action = params.get("action", "")
        match_id = params.get("match_id", "")
        match_ids = params.get("match_ids", "")  # 支持批量 match_id，用逗号分隔

        try:
            # 如果有多个 match_id，批量分析
            if match_ids and action == "analyze":
                match_id_list = [mid.strip() for mid in match_ids.split(",") if mid.strip()]
                if match_id_list:
                    job = start_batch_analyze_job(
                        match_id_list,
                        root_path,
                        data_dir=workspace.data_dir,
                        user_key="default",
                    )
                else:
                    return JSONResponse({"ok": False, "error": "未指定比赛ID"}, status_code=400)
            else:
                job = start_dashboard_job(
                    action,
                    root_path,
                    match_id=match_id,
                    data_dir=workspace.data_dir,
                    user_key="default",
                )
        except ValueError as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
        return StreamingResponse(
            _job_sse_events(job),
            media_type="text/event-stream; charset=utf-8",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )

    @app.post("/api/jobs/{action}")
    async def start_job(action: str, request: Request):
        """启动任务"""
        workspace = workspace_for_user(root_path, "default")
        params = request.query_params
        match_id = params.get("match_id", "")
        try:
            job = start_dashboard_job(
                action,
                root_path,
                match_id=match_id,
                data_dir=workspace.data_dir,
                user_key="default",
            )
        except ValueError as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
        status_code = 202 if job.status == "running" else 400
        return JSONResponse(_job_snapshot(job), status_code=status_code)

    @app.get("/api/jobs/{job_id}")
    async def get_job(job_id: str, request: Request):
        """获取任务状态"""
        job = _get_dashboard_job(job_id)
        if job is None:
            return JSONResponse({"ok": False, "error": "job not found"}, status_code=404)
        return _job_snapshot(job)

    @app.get("/api/jobs/{job_id}/events")
    async def job_events(job_id: str, request: Request):
        """任务事件流"""
        job = _get_dashboard_job(job_id)
        if job is None:
            return JSONResponse({"ok": False, "error": "job not found"}, status_code=404)
        return StreamingResponse(_job_sse_events(job), media_type="text/event-stream")

    # HTML 页面路由
    @app.get("/", response_class=HTMLResponse)
    @app.get("/index.html", response_class=HTMLResponse)
    async def index(request: Request):
        """主页"""
        # 检查是否有 Vue 前端构建文件
        static_dir = root_path / "src" / "football_sim" / "static"
        index_file = static_dir / "index.html"

        if index_file.exists():
            # 服务 Vue 前端
            return HTMLResponse(index_file.read_text(encoding="utf-8"))

        # 回退到旧版 HTML 模板
        workspace = workspace_for_user(root_path, "default")
        init_history_db(workspace.history_db)
        page = render_dashboard_html(load_dashboard_model(data_dir=workspace.data_dir))
        return HTMLResponse(page)

    @app.get("/match/{match_id}", response_class=HTMLResponse)
    async def match_detail(match_id: str, request: Request):
        """比赛详情页"""
        workspace = workspace_for_user(root_path, "default")
        from football_sim.history_db import load_matches, load_analyses
        from football_sim.data_sources.match_store import load_match_data
        from football_sim.analysis.odds_analyzer import generate_odds_summary
        from football_sim.dashboard import render_match_detail_html

        # 查找赛事
        matches = load_matches(workspace.history_db, limit=1000)
        match = next((m for m in matches if m.get("match_id") == match_id), None)
        if not match:
            return HTMLResponse("<h1>未找到赛事</h1>", status_code=404)

        # 加载赛事数据
        match_data: Dict[str, Any] = {}
        odds_summary: Dict[str, Any] = {}
        data_dir_path = match.get("data_dir", "")
        if data_dir_path:
            match_dir = Path(data_dir_path)
            if not match_dir.is_absolute():
                match_dir = root_path / match_dir
            if match_dir.exists():
                match_data = load_match_data(match_dir)
                try:
                    odds_summary = generate_odds_summary(match_dir)
                except Exception:
                    odds_summary = {}

        # 查找已有分析
        analyses = load_analyses(workspace.history_db, match_id=match_id, limit=1)

        page = render_match_detail_html(match, match_data, odds_summary, analyses)
        return HTMLResponse(page)

    @app.get("/analysis/{analysis_id}", response_class=HTMLResponse)
    async def analysis_detail(analysis_id: str, request: Request):
        """分析详情页"""
        workspace = workspace_for_user(root_path, "default")
        from football_sim.history_db import load_analyses
        analyses = load_analyses(workspace.history_db, limit=100)
        for a in analyses:
            if str(a.get("id")) == analysis_id:
                return HTMLResponse(f"""
                <h1>{a.get('home_team', '')} vs {a.get('away_team', '')}</h1>
                <p>联赛: {a.get('league', '')}</p>
                <p>置信度: {a.get('confidence', 0)}</p>
                <pre>{a.get('analysis_text', '')}</pre>
                """)
        return HTMLResponse("<h1>未找到分析记录</h1>", status_code=404)

    # Vue Router catch-all（最后定义）
    @app.get("/{path:path}", response_class=HTMLResponse)
    async def catch_all(path: str, request: Request):
        """Vue 路由支持"""
        # 检查是否有 Vue 前端构建文件
        static_dir = root_path / "src" / "football_sim" / "static"
        index_file = static_dir / "index.html"

        if index_file.exists():
            # 尝试提供静态文件
            file_path = static_dir / path
            if file_path.exists() and file_path.is_file():
                from fastapi.responses import FileResponse
                return FileResponse(str(file_path))

            # Vue 路由 - 返回 index.html
            return HTMLResponse(index_file.read_text(encoding="utf-8"))

        return HTMLResponse("<h1>404 Not Found</h1>", status_code=404)
    async def login_form(request: Request):
        if current_user(request) is not None:
            return RedirectResponse("/", status_code=303)
        return HTMLResponse(_render_login_page())

    @app.get("/register", response_class=HTMLResponse)
    async def register_form(request: Request):
        if current_user(request) is not None:
            return RedirectResponse("/", status_code=303)
        return HTMLResponse(_render_register_page())

    @app.post("/login")
    async def login(request: Request):
        form = _parse_form_body(await request.body())
        user = auth_store.authenticate(form.get("username", ""), form.get("password", ""))
        if user is None:
            return HTMLResponse(_render_login_page("用户名或密码错误"), status_code=401)
        token = auth_store.create_session(user.username)
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(
            SESSION_COOKIE_NAME,
            token,
            max_age=SESSION_TTL_DAYS * 24 * 60 * 60,
            httponly=True,
            samesite="lax",
        )
        return response

    @app.post("/register")
    async def register(request: Request):
        form = _parse_form_body(await request.body())
        username = form.get("username", "")
        password = form.get("password", "")
        if not str(username).strip() or not str(password):
            return HTMLResponse(_render_register_page("请输入账号和密码"), status_code=400)
        try:
            user = auth_store.create_user(username, password)
        except ValueError:
            return HTMLResponse(_render_register_page("账号只能包含字母、数字、下划线或短横线"), status_code=400)
        except sqlite3.IntegrityError:
            return HTMLResponse(_render_register_page("账号已存在，请直接登录"), status_code=409)
        token = auth_store.create_session(user.username)
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(
            SESSION_COOKIE_NAME,
            token,
            max_age=SESSION_TTL_DAYS * 24 * 60 * 60,
            httponly=True,
            samesite="lax",
        )
        return response

    @app.post("/logout")
    async def logout(request: Request):
        token = request.cookies.get(SESSION_COOKIE_NAME, "")
        if token:
            auth_store.delete_session(token)
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie(SESSION_COOKIE_NAME)
        return response

    return app


def _bootstrap_admin_user(auth_store: AuthStore) -> None:
    username = os.environ.get("FOOTBALL_ADMIN_USER", "admin")
    password = os.environ.get("FOOTBALL_ADMIN_PASSWORD", "admin")
    auth_store.bootstrap_admin(username, password)


def _parse_form_body(body: bytes) -> dict:
    if not body:
        return {}
    return {
        key: values[0]
        for key, values in parse_qs(body.decode("utf-8")).items()
        if values
    }


def _render_login_page(error: str = "") -> str:
    error_html = f'<p class="login-error">{_html_escape(error)}</p>' if error else ""
    return f"""
<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>足球赛事分析系统 - 登录</title>
<style>
:root {{
  color-scheme: light;
  --bg: #f4f6f8;
  --panel: #ffffff;
  --text: #172033;
  --muted: #667085;
  --line: #d7dde5;
  --blue: #1d4ed8;
  --blue-hover: #1e40af;
  --green: #16835f;
  --red: #b42318;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  font-family: Arial, "Microsoft YaHei", "PingFang SC", sans-serif;
  background: var(--bg);
  color: var(--text);
}}
.login-shell {{
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(280px, 0.88fr) minmax(340px, 1fr);
  align-items: stretch;
}}
.login-aside {{
  display: grid;
  align-content: center;
  gap: 22px;
  padding: 54px;
  background: #172033;
  color: #f8fafc;
}}
.brand-lockup {{ display: grid; gap: 12px; }}
.brand-mark {{
  width: 46px;
  height: 46px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(255,255,255,.28);
  border-radius: 8px;
  background: rgba(255,255,255,.08);
  font-size: 22px;
  font-weight: 700;
}}
.brand-lockup h1 {{
  margin: 0;
  font-size: 30px;
  line-height: 1.18;
  letter-spacing: 0;
}}
.brand-lockup p {{
  margin: 0;
  max-width: 440px;
  color: #cbd5e1;
  line-height: 1.7;
  font-size: 15px;
}}
.login-points {{
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
  color: #e2e8f0;
  font-size: 14px;
}}
.login-points li {{
  display: flex;
  gap: 8px;
  align-items: center;
}}
.login-points li::before {{
  content: "";
  width: 7px;
  height: 7px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: #34d399;
}}
.login-main {{
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 36px 22px;
}}
.login-card {{
  width: min(420px, 100%);
  display: grid;
  gap: 18px;
  padding: 30px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: 0 18px 45px rgba(16, 24, 40, .10);
}}
.login-card header {{ display: grid; gap: 6px; }}
.login-card h2 {{
  margin: 0;
  font-size: 24px;
  line-height: 1.25;
  letter-spacing: 0;
}}
.login-card p {{
  margin: 0;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.6;
}}
.field {{
  display: grid;
  gap: 7px;
  color: #344054;
  font-size: 14px;
}}
.field input {{
  width: 100%;
  height: 42px;
  border: 1px solid #c8ced8;
  border-radius: 6px;
  padding: 0 12px;
  color: var(--text);
  background: #fff;
  font-size: 15px;
}}
.field input:focus {{
  border-color: var(--blue);
  outline: 3px solid rgba(29, 78, 216, .14);
}}
.login-actions {{
  display: grid;
  gap: 12px;
  margin-top: 2px;
}}
.login-button {{
  height: 42px;
  border: 0;
  border-radius: 6px;
  background: var(--blue);
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
}}
.login-button:hover {{ background: var(--blue-hover); }}
.auth-switch {{
  margin: 0;
  color: var(--muted);
  text-align: center;
  font-size: 14px;
}}
.register-link {{
  color: var(--blue);
  font-weight: 700;
  text-decoration: none;
}}
.register-link:hover {{
  color: var(--blue-hover);
  text-decoration: underline;
}}
.login-error {{
  margin: 0;
  padding: 10px 12px;
  border: 1px solid #f3b8ae;
  border-radius: 6px;
  background: #fff4f2;
  color: var(--red);
  font-size: 14px;
}}
@media (max-width: 820px) {{
  .login-shell {{ grid-template-columns: 1fr; }}
  .login-aside {{
    min-height: auto;
    padding: 30px 22px;
  }}
  .brand-lockup h1 {{ font-size: 24px; }}
  .login-points {{ display: none; }}
  .login-main {{
    min-height: auto;
    place-items: start center;
  }}
  .login-card {{ padding: 22px; }}
}}
</style>
</head>
<body>
<main class="login-shell">
<section class="login-aside" aria-label="系统信息">
  <div class="brand-lockup">
    <div class="brand-mark">球</div>
    <h1>足球赛事分析系统</h1>
    <p>多用户服务模式已启用。赛事数据共享，分析记录和配置按账号隔离。</p>
  </div>
  <ul class="login-points">
    <li>赛事数据实时抓取</li>
    <li>LLM 智能分析</li>
    <li>赔率波动追踪</li>
    <li>适合 Docker 或局域网部署</li>
  </ul>
</section>
<section class="login-main" aria-label="登录表单">
<form class="login-card" method="post" action="/login">
<header>
<h2>账号登录</h2>
<p>请输入管理员或已创建用户的账号密码。</p>
</header>
{error_html}
<label class="field">账号<input name="username" autocomplete="username" required></label>
<label class="field">密码<input name="password" type="password" autocomplete="current-password" required></label>
<div class="login-actions">
<button class="login-button" type="submit">登录</button>
<p class="auth-switch">还没有账号？<a class="register-link" href="/register">注册新账号</a></p>
</div>
</form>
</section>
</main>
</body>
</html>
""".strip()


def _render_register_page(error: str = "") -> str:
    page = _render_login_page(error)
    replacements = (
        ("<title>足球赛事分析系统 - 登录</title>", "<title>足球赛事分析系统 - 注册</title>"),
        ('aria-label="登录表单"', 'aria-label="注册表单"'),
        ('method="post" action="/login"', 'method="post" action="/register"'),
        ("<h2>账号登录</h2>", "<h2>注册账号</h2>"),
        ("<p>请输入管理员或已创建用户的账号密码。</p>", "<p>创建后会自动进入个人工作区。</p>"),
        ('autocomplete="current-password"', 'autocomplete="new-password"'),
        ('<button class="login-button" type="submit">登录</button>', '<button class="login-button" type="submit">注册</button>'),
        ('还没有账号？<a class="register-link" href="/register">注册新账号</a>', '已有账号？<a class="register-link" href="/login">返回登录</a>'),
    )
    for old, new in replacements:
        page = page.replace(old, new, 1)
    return page


def _inject_user_bar(page: str, username: str) -> str:
    bar = f"""
<div style="position:sticky;top:0;z-index:20;display:flex;justify-content:flex-end;gap:10px;align-items:center;padding:8px 18px;background:#ffffff;border-bottom:1px solid #d6dae1;font-family:Arial,Microsoft YaHei,sans-serif;">
<span>{_html_escape(username)}</span>
<form method="post" action="/logout" style="margin:0;">
<button type="submit" style="height:30px;border:1px solid #c8ced8;border-radius:6px;background:#fff;color:#111827;cursor:pointer;">退出登录</button>
</form>
</div>
""".strip()
    if "<body>" in page:
        return page.replace("<body>", f"<body>\n{bar}", 1)
    return f"{bar}\n{page}"


def _html_escape(value: str) -> str:
    import html
    return html.escape(str(value or ""))


def serve_fastapi_dashboard(
    reports_dir: Path,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = False,
    repo_root: Optional[Path] = None,
) -> None:
    try:
        import uvicorn
    except ModuleNotFoundError as exc:
        raise RuntimeError(f"FastAPI 服务需要先安装依赖：{FASTAPI_INSTALL_HINT}") from exc

    app = create_fastapi_app(Path(reports_dir), Path(repo_root or Path.cwd()))
    url = f"http://{host}:{port}"
    print(f"FastAPI 足球仪表盘地址：{url}")
    if open_browser:
        webbrowser.open(url)
    uvicorn.run(app, host=host, port=port, log_level="info")
