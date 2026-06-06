import asyncio
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from football_sim.history_db import (
    get_analysis_with_results,
    get_hit_statistics,
    init_history_db,
    load_analyses,
    load_dashboard_actions,
    load_dashboard_config,
    load_matches,
    record_dashboard_action,
    save_dashboard_config,
)


@dataclass(frozen=True)
class DashboardMatch:
    match_id: str
    league: str
    home_team: str
    away_team: str
    match_time: str
    round_info: str = ""
    has_data: bool = False
    has_analysis: bool = False
    confidence: int = 0


@dataclass(frozen=True)
class DashboardConfig:
    llm_provider: str = ""
    llm_base_url: str = ""
    llm_model: str = ""
    llm_api_key_masked: str = ""


@dataclass(frozen=True)
class DashboardModel:
    date: str
    matches: Tuple[DashboardMatch, ...]
    recent_analyses: Tuple[Dict[str, Any], ...]
    config: DashboardConfig
    ai_summary: str = ""


@dataclass
class DashboardJob:
    job_id: str
    action: str
    match_id: str
    command: Tuple[str, ...]
    stage_labels: Tuple[str, ...]
    created_at: float = field(default_factory=time.time)
    started_at: float = field(default_factory=time.time)
    finished_at: float = 0.0
    status: str = "running"
    exit_code: Optional[int] = None
    stage_label: str = "准备执行"
    stage_index: int = 0
    output_lines: List[str] = field(default_factory=list)
    user_key: str = ""
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


_DASHBOARD_JOBS: Dict[str, DashboardJob] = {}
_DASHBOARD_JOBS_LOCK = threading.Lock()


def _mask_api_key(value: str) -> str:
    value = str(value or "")
    if not value:
        return ""
    if len(value) <= 3:
        return "***"
    prefix = value[:3] if value.startswith("sk-") else value[:4]
    return f"{prefix}***"


def load_dashboard_model(date: str = "", data_dir: Path = None) -> DashboardModel:
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    db_path = (data_dir or Path("data/users/default")) / "history.sqlite3"
    init_history_db(db_path)

    matches_db = load_matches(db_path, date=date)
    # 使用带命中状态的分析记录
    analyses_db = get_analysis_with_results(db_path, limit=20)
    config_dict = load_dashboard_config(db_path)

    # 获取命中率统计
    hit_stats = get_hit_statistics(db_path)

    matches = tuple(
        DashboardMatch(
            match_id=m.get("match_id", ""),
            league=m.get("league", ""),
            home_team=m.get("home_team", ""),
            away_team=m.get("away_team", ""),
            match_time=m.get("match_time", ""),
            round_info=m.get("round_info", ""),
            has_data=bool(m.get("data_dir")),
        )
        for m in matches_db
    )

    config = DashboardConfig(
        llm_provider=config_dict.get("llm_provider", ""),
        llm_base_url=config_dict.get("llm_base_url", ""),
        llm_model=config_dict.get("llm_model", ""),
        llm_api_key_masked=_mask_api_key(config_dict.get("llm_api_key", "")),
    )

    configured = "已配置" if config.llm_base_url and config.llm_model else "未配置"
    ai_summary = f"大模型接口{configured}；共 {len(matches)} 场赛事，{len(analyses_db)} 条分析记录。"
    if hit_stats["hit"] + hit_stats["miss"] > 0:
        ai_summary += f" 命中率 {hit_stats['hit_rate']}%"

    return DashboardModel(
        date=date,
        matches=matches,
        recent_analyses=tuple(analyses_db),
        config=config,
        ai_summary=ai_summary,
    )


def _render_match_detail_html(match: Dict[str, Any], match_data: Dict[str, Any]) -> str:
    """渲染赛事详情页面"""
    match_id = match.get("match_id", "")
    league = match.get("league", "")
    home_team = match.get("home_team", "")
    away_team = match.get("away_team", "")
    match_time = match.get("match_time", "")

    # 赔率信息
    odds_html = ""
    odds = match_data.get("odds", {})
    if odds:
        odds_html = "<h3>赔率数据</h3><table><tr><th>类型</th><th>主</th><th>平</th><th>客</th></tr>"
        # 欧赔
        euro = odds.get("european", {})
        if euro:
            odds_html += f"<tr><td>欧赔</td><td>{euro.get('home', '-')}</td><td>{euro.get('draw', '-')}</td><td>{euro.get('away', '-')}</td></tr>"
        # 亚盘
        asian = odds.get("asian", {})
        if asian:
            odds_html += f"<tr><td>亚盘</td><td>{asian.get('home', '-')}/{asian.get('home_odds', '-')}</td><td>-</td><td>{asian.get('away', '-')}/{asian.get('away_odds', '-')}</td></tr>"
        # 大小球
        totals = odds.get("totals", {})
        if totals:
            odds_html += f"<tr><td>大小球</td><td>大 {totals.get('line', '-')} @ {totals.get('over_odds', '-')}</td><td>-</td><td>小 @ {totals.get('under_odds', '-')}</td></tr>"
        odds_html += "</table>"

    # 其他信息
    info_html = ""
    info = match_data.get("info", {})
    if info:
        info_html = f"<h3>赛事信息</h3><pre>{_html_escape(json.dumps(info, indent=2, ensure_ascii=False))}</pre>"

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_html_escape(home_team)} vs {_html_escape(away_team)} - 赛事详情</title>
<style>
:root {{ --bg:#f4f6f8; --panel:#fff; --text:#172033; --muted:#667085; --line:#d7dde5; --blue:#1d4ed8; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:Arial,"Microsoft YaHei",sans-serif; background:var(--bg); color:var(--text); }}
.nav {{ display:flex; gap:18px; align-items:center; padding:12px 24px; background:#172033; color:#fff; }}
.nav a {{ color:#cbd5e1; text-decoration:none; }} .nav a:hover {{ color:#fff; }}
.container {{ max-width:900px; margin:0 auto; padding:24px; }}
.card {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:20px; margin-bottom:16px; }}
.card h3 {{ margin:0 0 12px; }}
table {{ width:100%; border-collapse:collapse; }}
th, td {{ padding:8px 12px; text-align:left; border-bottom:1px solid var(--line); }}
th {{ background:#f8f9fb; font-weight:600; }}
button {{ padding:6px 14px; border:1px solid var(--line); border-radius:6px; background:#fff; cursor:pointer; }}
.btn-primary {{ background:var(--blue); color:#fff; border-color:var(--blue); }}
pre {{ background:#f8f9fb; padding:12px; border-radius:6px; overflow-x:auto; font-size:13px; }}
</style>
</head>
<body>
<nav class="nav">
  <strong>足球赛事分析系统</strong>
  <a href="/">赛事列表</a>
  <a href="/analysis">分析报告</a>
  <span style="flex:1"></span>
</nav>
<div class="container">
  <div class="card">
    <h3>{_html_escape(league)}: {_html_escape(home_team)} vs {_html_escape(away_team)}</h3>
    <p>比赛时间: {_html_escape(match_time)}</p>
    <p>赛事ID: {_html_escape(match_id)}</p>
    <button class="btn-primary" onclick="analyzeMatch()">分析此赛事</button>
    <span id="status"></span>
  </div>
  {odds_html}
  {info_html}
  <div class="card">
    <h3>分析日志</h3>
    <div id="log" style="background:#1e293b;color:#e2e8f0;padding:12px;border-radius:6px;font-family:monospace;font-size:13px;max-height:300px;overflow-y:auto;white-space:pre-wrap;">等待分析...</div>
  </div>
</div>
<script>
function analyzeMatch() {{
  document.getElementById('status').textContent = '分析中...';
  const evt = new EventSource('/api/run?action=analyze&match_id={match_id}');
  const logEl = document.getElementById('log');
  logEl.textContent = '';
  evt.onmessage = function(e) {{
    const data = JSON.parse(e.data);
    if (data.line) logEl.textContent += data.line + '\\n';
    if (data.done) {{
      evt.close();
      document.getElementById('status').textContent = '分析完成';
    }}
    if (data.error) {{
      evt.close();
      document.getElementById('status').textContent = '错误: ' + data.error;
    }}
  }};
  evt.onerror = function() {{
    evt.close();
    document.getElementById('status').textContent = '连接断开';
  }};
}}
</script>
</body>
</html>"""


def _render_analysis_detail_html(analysis: Dict[str, Any]) -> str:
    """渲染分析详情页面"""
    analysis_id = analysis.get("id", "")
    match_id = analysis.get("match_id", "")
    home_team = analysis.get("home_team", "")
    away_team = analysis.get("away_team", "")
    league = analysis.get("league", "")
    confidence = analysis.get("confidence", 0)
    analysis_text = analysis.get("analysis_text", "")
    brief_text = analysis.get("brief_text", "")
    created_at = analysis.get("created_at", "")

    # 将换行符转为 <br> 显示
    analysis_html = _html_escape(analysis_text).replace("\n", "<br>")
    brief_html = _html_escape(brief_text).replace("\n", "<br>")

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_html_escape(home_team)} vs {_html_escape(away_team)} - 分析报告</title>
<style>
:root {{ --bg:#f4f6f8; --panel:#fff; --text:#172033; --muted:#667085; --line:#d7dde5; --blue:#1d4ed8; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:Arial,"Microsoft YaHei",sans-serif; background:var(--bg); color:var(--text); }}
.nav {{ display:flex; gap:18px; align-items:center; padding:12px 24px; background:#172033; color:#fff; }}
.nav a {{ color:#cbd5e1; text-decoration:none; }} .nav a:hover {{ color:#fff; }}
.container {{ max-width:900px; margin:0 auto; padding:24px; }}
.card {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:20px; margin-bottom:16px; }}
.card h3 {{ margin:0 0 12px; }}
.meta {{ color:var(--muted); font-size:14px; margin-bottom:12px; }}
.confidence {{ display:inline-block; padding:4px 12px; border-radius:12px; font-size:14px; background:#ecfdf5; color:#065f46; }}
.analysis-content {{ white-space:pre-wrap; line-height:1.6; }}
</style>
</head>
<body>
<nav class="nav">
  <strong>足球赛事分析系统</strong>
  <a href="/">赛事列表</a>
  <a href="/match/{match_id}">赛事详情</a>
  <span style="flex:1"></span>
</nav>
<div class="container">
  <div class="card">
    <h3>{_html_escape(league)}: {_html_escape(home_team)} vs {_html_escape(away_team)}</h3>
    <p class="meta">
      分析时间: {_html_escape(created_at)} |
      <span class="confidence">置信度: {confidence}</span>
    </p>
  </div>
  <div class="card">
    <h3>精简摘要</h3>
    <div class="analysis-content">{brief_html}</div>
  </div>
  <div class="card">
    <h3>完整分析</h3>
    <div class="analysis-content">{analysis_html}</div>
  </div>
</div>
</body>
</html>"""


def render_dashboard_html(model: DashboardModel) -> str:
    match_rows = ""
    for idx, m in enumerate(model.matches, 1):
        status = "已分析" if m.has_analysis else ("有数据" if m.has_data else "待抓取")
        # 提取序号（从 round_info 中）
        match_number = ""
        if hasattr(m, 'round_info') and m.round_info:
            import re
            num_match = re.search(r'(\d+)', m.round_info)
            match_number = num_match.group(1) if num_match else str(idx).zfill(3)
        else:
            match_number = str(idx).zfill(3)

        match_rows += f"""
        <tr>
          <td><input type="checkbox" class="match-check" value="{_html_escape(m.match_id)}"></td>
          <td>{_html_escape(match_number)}</td>
          <td>{_html_escape(m.league)}</td>
          <td>{_html_escape(m.home_team)}</td>
          <td>{_html_escape(m.away_team)}</td>
          <td>{_html_escape(m.match_time)}</td>
          <td>{status}</td>
          <td>
            <a href="/match/{m.match_id}">详情</a>
            <button onclick="analyzeMatch('{m.match_id}')">分析</button>
          </td>
        </tr>"""

    analysis_rows = ""
    for a in model.recent_analyses[:10]:
        # 获取命中状态
        hit_status = a.get("hit_status", "待开奖")
        hit_class = ""
        if "3/3" in hit_status or "2/3" in hit_status:
            hit_class = "status-ok"
        elif "1/3" in hit_status:
            hit_class = "status-partial"
        elif "未中" in hit_status:
            hit_class = "status-warn"

        prediction = a.get("prediction_outcome", "")
        score = a.get("prediction_score", "")
        goals = a.get("prediction_goals", "")
        actual_score = ""
        if a.get("home_score") is not None and a.get("away_score") is not None:
            actual_score = f"{a.get('home_score')}-{a.get('away_score')}"

        # 获取比赛序号
        match_number = a.get("match_number", "")

        analysis_rows += f"""
        <tr>
          <td>{_html_escape(match_number)}</td>
          <td>{_html_escape(a.get('created_at', '')[:10] if a.get('created_at') else '')}</td>
          <td>{_html_escape(a.get('league', ''))}</td>
          <td>{_html_escape(a.get('home_team', ''))} vs {_html_escape(a.get('away_team', ''))}</td>
          <td>{_html_escape(prediction)}</td>
          <td>{_html_escape(score)}</td>
          <td>{_html_escape(goals)}</td>
          <td>{_html_escape(actual_score)}</td>
          <td><span class="status {hit_class}">{hit_status}</span></td>
          <td><a href="/analysis/{a.get('id', '')}">查看</a></td>
        </tr>"""

    config = model.config
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>足球赛事分析系统</title>
<style>
:root {{ --bg:#f4f6f8; --panel:#fff; --text:#172033; --muted:#667085; --line:#d7dde5; --blue:#1d4ed8; --green:#16835f; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:Arial,"Microsoft YaHei",sans-serif; background:var(--bg); color:var(--text); }}
.nav {{ display:flex; gap:18px; align-items:center; padding:12px 24px; background:#172033; color:#fff; }}
.nav a {{ color:#cbd5e1; text-decoration:none; }} .nav a:hover {{ color:#fff; }}
.container {{ max-width:1200px; margin:0 auto; padding:24px; }}
.card {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:20px; margin-bottom:16px; }}
.card h3 {{ margin:0 0 12px; }}
table {{ width:100%; border-collapse:collapse; }}
th, td {{ padding:8px 12px; text-align:left; border-bottom:1px solid var(--line); }}
th {{ background:#f8f9fb; font-weight:600; }}
button {{ padding:6px 14px; border:1px solid var(--line); border-radius:6px; background:#fff; cursor:pointer; }}
button:hover {{ background:#f0f4ff; }}
.btn-primary {{ background:var(--blue); color:#fff; border-color:var(--blue); }}
.btn-primary:hover {{ background:#1e40af; }}
.btn-green {{ background:var(--green); color:#fff; border-color:var(--green); }}
.btn-green:hover {{ background:#10664d; }}
.config-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
.config-grid label {{ display:grid; gap:4px; font-size:14px; color:var(--muted); }}
.config-grid input {{ height:36px; padding:0 10px; border:1px solid var(--line); border-radius:6px; }}
.status {{ padding:4px 10px; border-radius:12px; font-size:13px; }}
.status-ok {{ background:#ecfdf5; color:#065f46; }}
.status-partial {{ background:#fffbeb; color:#92400e; }}
.status-warn {{ background:#fffbeb; color:#92400e; }}
#sse-log {{ background:#1e293b; color:#e2e8f0; padding:12px; border-radius:6px; font-family:monospace; font-size:13px; max-height:300px; overflow-y:auto; white-space:pre-wrap; }}
.progress-bar {{ width:100%; height:24px; background:#e5e7eb; border-radius:12px; overflow:hidden; margin:8px 0; }}
.progress-fill {{ height:100%; background:linear-gradient(90deg,#1d4ed8,#3b82f6); border-radius:12px; transition:width 0.3s; display:flex; align-items:center; justify-content:center; color:#fff; font-size:12px; font-weight:600; min-width:40px; }}
.progress-fill.done {{ background:linear-gradient(90deg,#16835f,#34d399); }}
.toolbar {{ display:flex; gap:8px; flex-wrap:wrap; align-items:center; }}
.toolbar .sep {{ color:var(--muted); }}
</style>
</head>
<body>
<nav class="nav">
  <strong>足球赛事分析系统</strong>
  <a href="/">赛事列表</a>
  <a href="/analysis">分析报告</a>
  <a href="/config">配置</a>
  <span style="flex:1"></span>
  <a href="/logout">退出</a>
</nav>
<div class="container">
  <div class="card">
    <h3>{_html_escape(model.date)} 赛事列表 ({len(model.matches)} 场)</h3>
    <div class="toolbar" style="margin-bottom:12px;">
      <button class="btn-primary" onclick="fetchAll()">抓取今日赛事+赔率</button>
      <button onclick="fetchList()">仅抓取赛事列表</button>
      <span id="fetch-status"></span>
      <span class="sep">|</span>
      <button class="btn-green" onclick="analyzeSelected()">批量分析选中</button>
      <span id="batch-status"></span>
    </div>
    <div id="batch-progress-wrap" style="display:none;">
      <div class="progress-bar"><div id="batch-progress-fill" class="progress-fill" style="width:0%">0%</div></div>
    </div>
    <table>
      <thead><tr><th><input type="checkbox" id="select-all" onchange="toggleAll(this)"></th><th>序号</th><th>联赛</th><th>主队</th><th>客队</th><th>时间</th><th>状态</th><th>操作</th></tr></thead>
      <tbody>{match_rows}</tbody>
    </table>
  </div>
  <div class="card">
    <h3>近期分析</h3>
    <div style="margin-bottom:12px; display:flex; gap:10px; align-items:center;">
      <button class="btn-primary" onclick="fetchResults()">获取比赛结果</button>
      <button style="background:#dc3545; color:#fff; border-color:#dc3545;" onclick="clearAnalyses()">清除分析记录</button>
      <span id="results-status"></span>
    </div>
    <table>
      <thead><tr><th>序号</th><th>日期</th><th>联赛</th><th>对阵</th><th>预测</th><th>比分</th><th>进球</th><th>结果</th><th>状态</th><th>详情</th></tr></thead>
      <tbody>{analysis_rows}</tbody>
    </table>
  </div>
  <div class="card">
    <h3>AI 配置</h3>
    <p>{_html_escape(model.ai_summary)}</p>
    <div class="config-grid">
      <label>Provider
        <input id="llm-provider" value="{_html_escape(config.llm_provider)}" placeholder="openai / anthropic">
      </label>
      <label>Base URL
        <input id="llm-base-url" value="{_html_escape(config.llm_base_url)}" placeholder="https://api.openai.com/v1">
      </label>
      <label>Model
        <input id="llm-model" value="{_html_escape(config.llm_model)}" placeholder="gpt-4o">
      </label>
      <label>API Key
        <input id="llm-api-key" type="password" placeholder="已配置则显示掩码" value="">
      </label>
    </div>
    <div style="margin-top:12px;">
      <button class="btn-primary" onclick="saveConfig()">保存配置</button>
      <span id="config-status"></span>
    </div>
  </div>
  <div class="card">
    <h3>执行日志</h3>
    <div id="sse-log">等待任务...</div>
  </div>
</div>
<script>
/* ── 全选/取消全选 ── */
function toggleAll(el) {{
  document.querySelectorAll('.match-check').forEach(cb => cb.checked = el.checked);
}}

/* ── SSE 任务 Promise 封装 ── */
function runSSE(action, matchId) {{
  return new Promise((resolve, reject) => {{
    const url = '/api/run?action=' + action + (matchId ? '&match_id=' + matchId : '');
    const evt = new EventSource(url);
    const logEl = document.getElementById('sse-log');
    evt.onmessage = function(e) {{
      const data = JSON.parse(e.data);
      if (data.line) logEl.textContent += data.line + '\\n';
      if (data.done) {{
        evt.close();
        resolve(data.exit_code);
      }}
    }};
    evt.onerror = function() {{
      evt.close();
      reject(new Error('SSE connection lost'));
    }};
  }});
}}

/* ── 单任务 + 进度条（抓取/单个分析） ── */
function runTask(action, matchId) {{
  const statusEl = document.getElementById('fetch-status');
  const progressWrap = document.getElementById('batch-progress-wrap');
  const progressFill = document.getElementById('batch-progress-fill');
  statusEl.textContent = '执行中...';
  progressWrap.style.display = 'block';
  progressFill.style.width = '100%';
  progressFill.textContent = '处理中...';
  progressFill.classList.remove('done');
  const logEl = document.getElementById('sse-log');
  logEl.textContent = '';
  const url = '/api/run?action=' + action + (matchId ? '&match_id=' + matchId : '');
  const evt = new EventSource(url);
  evt.onmessage = function(e) {{
    const data = JSON.parse(e.data);
    if (data.line) logEl.textContent += data.line + '\\n';
    if (data.done) {{
      evt.close();
      statusEl.textContent = '完成';
      progressFill.textContent = '100%';
      progressFill.classList.add('done');
      setTimeout(function() {{ location.reload(); }}, 1500);
    }}
  }};
  evt.onerror = function() {{
    evt.close();
    statusEl.textContent = '连接断开';
    progressFill.textContent = '出错';
  }};
}}

/* ── 批量分析选中 ── */
async function analyzeSelected() {{
  const checks = document.querySelectorAll('.match-check:checked');
  const ids = Array.from(checks).map(cb => cb.value);
  if (ids.length === 0) {{
    document.getElementById('batch-status').textContent = '请先勾选要分析的比赛';
    return;
  }}
  const batchStatus = document.getElementById('batch-status');
  const progressWrap = document.getElementById('batch-progress-wrap');
  const progressFill = document.getElementById('batch-progress-fill');
  const logEl = document.getElementById('sse-log');
  logEl.textContent = '';
  progressWrap.style.display = 'block';
  progressFill.classList.remove('done');
  const total = ids.length;
  let done = 0;
  for (const mid of ids) {{
    batchStatus.textContent = '分析中 ' + (done + 1) + '/' + total;
    const pct = Math.round(done / total * 100);
    progressFill.style.width = pct + '%';
    progressFill.textContent = pct + '%';
    try {{
      await runSSE('analyze', mid);
    }} catch(err) {{
      logEl.textContent += '⚠ ' + mid + ' 分析失败: ' + err.message + '\\n';
    }}
    done++;
  }}
  const finalPct = 100;
  progressFill.style.width = finalPct + '%';
  progressFill.textContent = finalPct + '%';
  progressFill.classList.add('done');
  batchStatus.textContent = '完成 ' + done + '/' + total;
  setTimeout(function() {{ location.reload(); }}, 1500);
}}

/* ── 快捷函数 ── */
function fetchAll() {{ runTask('fetch-all'); }}
function fetchList() {{ runTask('fetch-list'); }}
function analyzeMatch(matchId) {{ runTask('analyze', matchId); }}
function fetchResults() {{
  const statusEl = document.getElementById('results-status');
  statusEl.textContent = '获取中...';
  const evt = new EventSource('/api/run?action=fetch-results');
  const logEl = document.getElementById('sse-log');
  evt.onmessage = function(e) {{
    const data = JSON.parse(e.data);
    if (data.line) logEl.textContent += data.line + '\\n';
    if (data.done) {{
      evt.close();
      statusEl.textContent = '完成';
      setTimeout(function() {{ location.reload(); }}, 1000);
    }}
  }};
  evt.onerror = function() {{
    evt.close();
    statusEl.textContent = '连接断开';
  }};
}}
function clearAnalyses() {{
  if (!confirm('确定要清除所有分析记录吗？此操作不可恢复。')) {{
    return;
  }}
  const statusEl = document.getElementById('results-status');
  statusEl.textContent = '清除中...';
  fetch('/api/analyses/clear', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
  }}).then(r => r.json()).then(resp => {{
    if (resp.ok) {{
      statusEl.textContent = '已清除 ' + resp.deleted_count + ' 条记录';
      setTimeout(function() {{ location.reload(); }}, 1000);
    }} else {{
      statusEl.textContent = '清除失败';
    }}
  }}).catch(err => {{
    statusEl.textContent = '错误: ' + err.message;
  }});
}}
function saveConfig() {{
  const data = {{
    llm_provider: document.getElementById('llm-provider').value,
    llm_base_url: document.getElementById('llm-base-url').value,
    llm_model: document.getElementById('llm-model').value,
    llm_api_key: document.getElementById('llm-api-key').value,
  }};
  fetch('/api/config', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify(data)
  }}).then(r => r.json()).then(resp => {{
    document.getElementById('config-status').textContent = resp.ok ? '已保存' : '保存失败';
  }});
}}
</script>
</body>
</html>"""


def _html_escape(text: str) -> str:
    if text is None:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_match_detail_html(
    match: Dict[str, Any],
    match_data: Dict[str, Any],
    odds_summary: Dict[str, Any],
    analyses: list,
) -> str:
    """渲染赛事详情页面（基于 match_store 多 JSON 数据源）"""
    import json as _json

    match_id = match.get("match_id", "")
    league = match.get("league", "")
    home_team = match.get("home_team", "")
    away_team = match.get("away_team", "")
    match_time = match.get("match_time", "")

    # ── 赔率摘要 ──
    implied = odds_summary.get("euro_implied", {})
    implied_html = ""
    if implied:
        implied_html = f"""
        <div class="card">
          <h3>赔率摘要</h3>
          <table>
            <tr><td>欧赔隐含概率（去水）</td><td>主胜 {implied.get('p_home',0)}%</td><td>平局 {implied.get('p_draw',0)}%</td><td>客胜 {implied.get('p_away',0)}%</td></tr>
            <tr><td>返还率 margin</td><td colspan="3">{implied.get('margin',0)}%</td></tr>
            <tr><td>亚盘方向</td><td colspan="3">{_html_escape(odds_summary.get('asian_direction',''))}</td></tr>
            <tr><td>大小球方向</td><td colspan="3">{_html_escape(odds_summary.get('ou_direction',''))}</td></tr>
            <tr><td>欧亚一致性</td><td colspan="3">{_html_escape(odds_summary.get('euro_asian_consistency',''))}</td></tr>
          </table>
          {_render_movement_alerts(odds_summary.get('movement_alerts', []))}
          {_render_outliers(odds_summary.get('bookmaker_outliers', []))}
        </div>"""

    # ── 各公司赔率变化表 ──
    odds_raw = match_data.get("赔率变化数据", {})
    odds_tables_html = ""
    if odds_raw:
        for odds_type, label in [("欧指", "欧赔"), ("亚盘", "亚盘"), ("大小球", "大小球")]:
            rows_html = ""
            for company_name, types_data in odds_raw.items():
                type_list = types_data.get(odds_type, [])
                if not type_list:
                    continue
                first = type_list[0] if type_list else {}
                last = type_list[-1] if type_list else {}
                if odds_type == "欧指":
                    init_h = first.get("home_win_odds", first.get("current_left", "-"))
                    init_d = first.get("draw_odds", first.get("current_middle", "-"))
                    init_a = first.get("away_win_odds", first.get("current_right", "-"))
                    cur_h = last.get("home_win_odds", last.get("current_left", "-"))
                    cur_d = last.get("draw_odds", last.get("current_middle", "-"))
                    cur_a = last.get("away_win_odds", last.get("current_right", "-"))
                    rows_html += f"<tr><td>{_html_escape(company_name)}</td><td>{init_h}/{init_d}/{init_a}</td><td>{cur_h}/{cur_d}/{cur_a}</td><td>{len(type_list)}</td></tr>"
                elif odds_type == "亚盘":
                    init_h = first.get("home_win_odds", first.get("current_left", "-"))
                    init_a = first.get("away_win_odds", first.get("current_right", "-"))
                    cur_h = last.get("home_win_odds", last.get("current_left", "-"))
                    cur_a = last.get("away_win_odds", last.get("current_right", "-"))
                    hc = last.get("handicap", last.get("ovalue0", "-"))
                    rows_html += f"<tr><td>{_html_escape(company_name)}</td><td>{init_h}/{init_a}</td><td>{cur_h}/{cur_a}</td><td>{_html_escape(str(hc))}</td></tr>"
                else:  # 大小球
                    init_o = first.get("home_win_odds", first.get("current_left", "-"))
                    init_u = first.get("away_win_odds", first.get("current_right", "-"))
                    cur_o = last.get("home_win_odds", last.get("current_left", "-"))
                    cur_u = last.get("away_win_odds", last.get("current_right", "-"))
                    line = last.get("handicap", last.get("ovalue0", "-"))
                    rows_html += f"<tr><td>{_html_escape(company_name)}</td><td>{init_o}/{init_u}</td><td>{cur_o}/{cur_u}</td><td>{_html_escape(str(line))}</td></tr>"
            if rows_html:
                if odds_type == "欧指":
                    header = "<tr><th>公司</th><th>初盘(主/平/客)</th><th>即时(主/平/客)</th><th>变化次数</th></tr>"
                elif odds_type == "亚盘":
                    header = "<tr><th>公司</th><th>初盘(主/客)</th><th>即时(主/客)</th><th>盘口</th></tr>"
                else:
                    header = "<tr><th>公司</th><th>初盘(大/小)</th><th>即时(大/小)</th><th>盘口</th></tr>"
                odds_tables_html += f"""
                <div class="card">
                  <h3>{label}变化</h3>
                  <table><thead>{header}</thead><tbody>{rows_html}</tbody></table>
                </div>"""

    # ── 附加数据区 ──
    extra_sections = ""
    section_config = [
        ("两队比赛历史交锋数据", "历史交锋"),
        ("主客队近期比赛数据", "近期战绩"),
        ("主客队队员、情报信息数据", "阵容情报"),
        ("比赛场地、天气、主客队队员上场信息(身价、位置)数据", "阵容/天气"),
        ("联赛积分排名、近期状态(进球数、失球数)、未来赛事数据", "联赛积分"),
    ]
    for key, label in section_config:
        data = match_data.get(key, {})
        if data and not (isinstance(data, dict) and data.get("error")):
            truncated = _json.dumps(data, ensure_ascii=False, indent=2)
            if len(truncated) > 3000:
                truncated = truncated[:3000] + "\n... (数据过长已截断)"
            extra_sections += f"""
            <details class="card">
              <summary><h3 style="display:inline">{label}</h3></summary>
              <pre>{_html_escape(truncated)}</pre>
            </details>"""

    # ── 已有分析 ──
    analysis_html = ""
    if analyses:
        a = analyses[0]
        pred_outcome = a.get("prediction_outcome", "")
        pred_score = a.get("prediction_score", "")
        confidence = a.get("confidence", 0)
        brief = a.get("brief_text", "")
        analysis_html = f"""
        <div class="card">
          <h3>已有分析</h3>
          <p>预测方向: <strong>{_html_escape(pred_outcome)}</strong> | 比分: <strong>{_html_escape(pred_score)}</strong> | 置信度: {confidence}</p>
          <div class="analysis-content">{_html_escape(brief).replace(chr(10), '<br>')}</div>
          <p style="margin-top:8px"><a href="/analysis/{a.get('id','')}">查看完整分析 →</a></p>
        </div>"""

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_html_escape(home_team)} vs {_html_escape(away_team)} - 赛事详情</title>
<style>
:root {{ --bg:#f4f6f8; --panel:#fff; --text:#172033; --muted:#667085; --line:#d7dde5; --blue:#1d4ed8; --green:#16835f; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:Arial,"Microsoft YaHei",sans-serif; background:var(--bg); color:var(--text); }}
.nav {{ display:flex; gap:18px; align-items:center; padding:12px 24px; background:#172033; color:#fff; }}
.nav a {{ color:#cbd5e1; text-decoration:none; }} .nav a:hover {{ color:#fff; }}
.container {{ max-width:900px; margin:0 auto; padding:24px; }}
.card {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:20px; margin-bottom:16px; }}
.card h3 {{ margin:0 0 12px; }}
table {{ width:100%; border-collapse:collapse; }}
th, td {{ padding:8px 12px; text-align:left; border-bottom:1px solid var(--line); }}
th {{ background:#f8f9fb; font-weight:600; }}
button {{ padding:6px 14px; border:1px solid var(--line); border-radius:6px; background:#fff; cursor:pointer; }}
.btn-primary {{ background:var(--blue); color:#fff; border-color:var(--blue); }}
.btn-primary:hover {{ background:#1e40af; }}
.btn-green {{ background:var(--green); color:#fff; border-color:var(--green); }}
pre {{ background:#f8f9fb; padding:12px; border-radius:6px; overflow-x:auto; font-size:13px; max-height:400px; overflow-y:auto; }}
.analysis-content {{ white-space:pre-wrap; line-height:1.6; }}
.alert {{ color:#92400e; background:#fffbeb; padding:4px 10px; border-radius:6px; font-size:13px; margin:2px 0; }}
.outlier {{ color:#065f46; background:#ecfdf5; padding:4px 10px; border-radius:6px; font-size:13px; margin:2px 0; }}
details summary {{ cursor:pointer; list-style:none; }}
details summary::-webkit-details-marker {{ display:none; }}
details summary::before {{ content:"▶ "; color:var(--muted); }}
details[open] summary::before {{ content:"▼ "; }}
#sse-log {{ background:#1e293b; color:#e2e8f0; padding:12px; border-radius:6px; font-family:monospace; font-size:13px; max-height:300px; overflow-y:auto; white-space:pre-wrap; }}
</style>
</head>
<body>
<nav class="nav">
  <strong>足球赛事分析系统</strong>
  <a href="/">赛事列表</a>
  <a href="/analysis">分析报告</a>
  <span style="flex:1"></span>
  <a href="/logout">退出</a>
</nav>
<div class="container">
  <div class="card">
    <h3>{_html_escape(league)}: {_html_escape(home_team)} vs {_html_escape(away_team)}</h3>
    <p>比赛时间: {_html_escape(match_time)} | 赛事ID: {_html_escape(match_id)}</p>
    <button class="btn-green" onclick="doAnalyze()">分析此赛事</button>
    <span id="status"></span>
  </div>
  {implied_html}
  {odds_tables_html}
  {extra_sections}
  {analysis_html}
  <div class="card">
    <h3>执行日志</h3>
    <div id="sse-log">等待分析...</div>
  </div>
</div>
<script>
function doAnalyze() {{
  document.getElementById('status').textContent = '分析中...';
  const logEl = document.getElementById('sse-log');
  logEl.textContent = '';
  const evt = new EventSource('/api/run?action=analyze&match_id={match_id}');
  evt.onmessage = function(e) {{
    const data = JSON.parse(e.data);
    if (data.line) logEl.textContent += data.line + '\\n';
    if (data.done) {{
      evt.close();
      document.getElementById('status').textContent = '分析完成';
      setTimeout(function() {{ location.reload(); }}, 1500);
    }}
  }};
  evt.onerror = function() {{
    evt.close();
    document.getElementById('status').textContent = '连接断开';
  }};
}}
</script>
</body>
</html>"""


def _render_movement_alerts(alerts: list) -> str:
    if not alerts:
        return ""
    items = "".join(f'<div class="alert">{_html_escape(a)}</div>' for a in alerts)
    return f'<div style="margin-top:8px"><strong>赔率波动警告</strong>{items}</div>'


def _render_outliers(outliers: list) -> str:
    if not outliers:
        return ""
    items = "".join(f'<div class="outlier">{_html_escape(o)}</div>' for o in outliers)
    return f'<div style="margin-top:8px"><strong>离群公司</strong>{items}</div>'


def _make_dashboard_handler(data_dir: Path) -> type:
    class DashboardHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def _send(self, code: int, content_type: str, body: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path in {"", "/index.html", "/"}:
                model = load_dashboard_model(data_dir=data_dir)
                self._send(200, "text/html; charset=utf-8", render_dashboard_html(model).encode("utf-8"))
                return
            if path == "/health":
                body = json.dumps({"ok": True}, ensure_ascii=False).encode("utf-8")
                self._send(200, "application/json; charset=utf-8", body)
                return
            if path == "/api/config":
                db_path = data_dir / "history.sqlite3"
                config = load_dashboard_config(db_path)
                body = json.dumps(config, ensure_ascii=False).encode("utf-8")
                self._send(200, "application/json; charset=utf-8", body)
                return
            if path.startswith("/api/run"):
                self._handle_run()
                return
            if path == "/api/hit-stats":
                # 命中率统计 API
                self._send_hit_stats()
                return
            if path == "/api/analyses-with-results":
                # 分析记录与结果 API
                self._send_analyses_with_results()
                return
            if path.startswith("/match/"):
                # 赛事详情页
                match_id = path[7:]  # 去掉 "/match/"
                self._send_match_detail(match_id)
                return
            if path.startswith("/analysis/"):
                # 分析详情页
                try:
                    analysis_id = int(path[10:])  # 去掉 "/analysis/"
                except ValueError:
                    self._send(400, "text/plain", b"Invalid analysis ID")
                    return
                self._send_analysis_detail(analysis_id)
                return
            self._send(404, "text/plain", b"Not Found")

        def _send_match_detail(self, match_id: str) -> None:
            """渲染赛事详情页面"""
            from football_sim.history_db import load_matches
            db_path = data_dir / "history.sqlite3"
            matches = load_matches(db_path, limit=1000)
            match = next((m for m in matches if m.get("match_id") == match_id), None)
            if not match:
                self._send(404, "text/plain", b"Match not found")
                return

            data_dir_path = match.get("data_dir", "")
            match_data = {}
            if data_dir_path and Path(data_dir_path).exists():
                import json
                info_file = Path(data_dir_path) / "info.json"
                odds_file = Path(data_dir_path) / "odds.json"
                if info_file.exists():
                    match_data["info"] = json.loads(info_file.read_text(encoding="utf-8"))
                if odds_file.exists():
                    match_data["odds"] = json.loads(odds_file.read_text(encoding="utf-8"))

            html = _render_match_detail_html(match, match_data)
            self._send(200, "text/html; charset=utf-8", html.encode("utf-8"))

        def _send_analysis_detail(self, analysis_id: int) -> None:
            """渲染分析详情页面"""
            from football_sim.history_db import load_analysis_by_id
            db_path = data_dir / "history.sqlite3"
            analysis = load_analysis_by_id(db_path, analysis_id)
            if not analysis:
                self._send(404, "text/plain", b"Analysis not found")
                return

            html = _render_analysis_detail_html(analysis)
            self._send(200, "text/html; charset=utf-8", html.encode("utf-8"))

        def _send_hit_stats(self) -> None:
            """发送命中率统计"""
            from football_sim.history_db import get_hit_statistics
            db_path = data_dir / "history.sqlite3"
            stats = get_hit_statistics(db_path)
            body = json.dumps(stats, ensure_ascii=False).encode("utf-8")
            self._send(200, "application/json; charset=utf-8", body)

        def _send_analyses_with_results(self) -> None:
            """发送分析记录及比赛结果"""
            from football_sim.history_db import get_analysis_with_results
            db_path = data_dir / "history.sqlite3"
            analyses = get_analysis_with_results(db_path, limit=50)
            body = json.dumps(analyses, ensure_ascii=False).encode("utf-8")
            self._send(200, "application/json; charset=utf-8", body)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path == "/api/config":
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                data = json.loads(body.decode("utf-8"))
                db_path = data_dir / "history.sqlite3"
                init_history_db(db_path)
                save_dashboard_config(db_path, data)
                self._send(200, "application/json; charset=utf-8", json.dumps({"ok": True}).encode("utf-8"))
                return
            self._send(404, "text/plain", b"Not Found")

        def _handle_run(self) -> None:
            params = parse_qs(urlparse(self.path).query)
            action = (params.get("action") or [""])[0]
            match_id = (params.get("match_id") or [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            def send_event(data: dict) -> None:
                self.wfile.write(f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8"))
                self.wfile.flush()

            job_id = uuid.uuid4().hex[:8]
            db_path = data_dir / "history.sqlite3"
            matches_dir = data_dir.parent.parent / "matches"
            cmd = []
            if action == "fetch-list":
                cmd = [sys.executable, "-m", "football_sim.cli", "fetch-matches", "--date", "today", "--output", str(matches_dir), "--db-path", str(db_path)]
            elif action == "fetch-all":
                cmd = [sys.executable, "-m", "football_sim.cli", "fetch-matches", "--date", "today", "--with-odds", "--output", str(matches_dir), "--db-path", str(db_path)]
            elif action == "analyze" and match_id:
                cmd = [sys.executable, "-m", "football_sim.cli", "analyze", "--match-id", match_id]
            elif action == "fetch-results":
                # 获取所有已分析赛事的结果
                cmd = [sys.executable, "-m", "football_sim.cli", "fetch-results"]

            if not cmd:
                send_event({"error": "unknown action"})
                return

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env={**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent)},
                )
                for line in proc.stdout or []:
                    send_event({"line": line.rstrip()})
                proc.wait()
                send_event({"done": True, "exit_code": proc.returncode})
            except Exception as e:
                send_event({"error": str(e)})

    return DashboardHandler


def serve_dashboard(
    reports_dir: Path,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = False,
) -> None:
    # 使用固定的数据目录，与 CLI 保持一致
    data_dir = Path("data/users/default")
    data_dir.mkdir(parents=True, exist_ok=True)
    handler = _make_dashboard_handler(data_dir)
    server = ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{server.server_port}"
    print(f"足球仪表盘地址：{url}")
    print("按 Ctrl+C 停止服务")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("仪表盘服务已停止")
    finally:
        server.server_close()