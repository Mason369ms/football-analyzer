import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from queue import Queue
from typing import Any, Dict, List, Optional, Tuple

from football_sim.logger import get_logger

logger = get_logger(__name__)

SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS matches (
        match_id TEXT PRIMARY KEY,
        date TEXT NOT NULL,
        league TEXT,
        home_team TEXT,
        away_team TEXT,
        match_time TEXT,
        round_info TEXT,
        data_dir TEXT,
        fetched_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id TEXT NOT NULL,
        analysis_type TEXT NOT NULL,
        home_team TEXT,
        away_team TEXT,
        league TEXT,
        confidence INTEGER DEFAULT 0,
        prediction_json TEXT,
        analysis_text TEXT,
        brief_text TEXT,
        created_at TEXT,
        user_key TEXT,
        prediction_outcome TEXT,
        prediction_score TEXT,
        prediction_goals TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS match_results (
        match_id TEXT PRIMARY KEY,
        home_score INTEGER,
        away_score INTEGER,
        result TEXT,
        half_home_score INTEGER,
        half_away_score INTEGER,
        fetched_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS llm_calls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id TEXT,
        model TEXT,
        prompt_tokens INTEGER DEFAULT 0,
        completion_tokens INTEGER DEFAULT 0,
        created_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dashboard_config (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dashboard_actions (
        job_id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        action TEXT NOT NULL,
        match_id TEXT,
        status TEXT NOT NULL,
        exit_code INTEGER NOT NULL,
        summary TEXT NOT NULL,
        data_dir TEXT NOT NULL
    )
    """,
)

# 数据库索引定义
INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_analyses_match_id ON analyses(match_id)",
    "CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_analyses_user_key ON analyses(user_key)",
    "CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(date)",
    "CREATE INDEX IF NOT EXISTS idx_matches_match_id ON matches(match_id)",
    "CREATE INDEX IF NOT EXISTS idx_match_results_match_id ON match_results(match_id)",
    "CREATE INDEX IF NOT EXISTS idx_dashboard_actions_created_at ON dashboard_actions(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_dashboard_actions_action ON dashboard_actions(action)",
]


class SQLitePool:
    """SQLite 连接池，支持多线程并发访问"""

    def __init__(self, db_path: Path, max_connections: int = 5):
        self.db_path = Path(db_path)
        self.max_connections = max_connections
        self._pool: Queue = Queue(maxsize=max_connections)
        self._lock = threading.Lock()
        self._created_connections = 0
        self._initialize_pool()

    def _initialize_pool(self):
        """初始化连接池"""
        for _ in range(min(2, self.max_connections)):  # 预创建 2 个连接
            conn = self._create_connection()
            self._pool.put(conn)

    def _create_connection(self) -> sqlite3.Connection:
        """创建新的数据库连接并配置优化参数"""
        conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=30
        )
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-4000")  # 4MB 缓存
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA mmap_size=268435456")  # 256MB mmap
        conn.execute("PRAGMA busy_timeout=5000")  # 5 秒忙等待
        self._created_connections += 1
        logger.debug(f"创建数据库连接 {self._created_connections}/{self.max_connections}")
        return conn

    @contextmanager
    def get_connection(self):
        """从连接池获取连接"""
        conn = None
        try:
            # 尝试从池中获取连接
            try:
                conn = self._pool.get_nowait()
            except Exception:
                # 池为空，创建新连接（如果未达上限）
                with self._lock:
                    if self._created_connections < self.max_connections:
                        conn = self._create_connection()
                    else:
                        # 等待可用连接
                        conn = self._pool.get(timeout=30)

            yield conn

        except Exception as e:
            logger.error(f"数据库连接错误: {e}")
            if conn:
                try:
                    conn.close()
                except:
                    pass
                conn = None
            raise
        finally:
            # 归还连接到池
            if conn:
                try:
                    self._pool.put_nowait(conn)
                except Exception:
                    # 池已满，关闭连接
                    try:
                        conn.close()
                    except:
                        pass

    def close_all(self):
        """关闭所有连接"""
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except:
                pass
        logger.info("所有数据库连接已关闭")


# 全局连接池管理
_connection_pools: Dict[str, SQLitePool] = {}
_pool_lock = threading.Lock()


def get_connection_pool(db_path: Path) -> SQLitePool:
    """获取或创建数据库连接池"""
    db_str = str(db_path)
    with _pool_lock:
        if db_str not in _connection_pools:
            _connection_pools[db_str] = SQLitePool(db_path)
        return _connection_pools[db_str]


def init_history_db(db_path: Path) -> None:
    """初始化历史数据库，创建表结构和索引"""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    pool = get_connection_pool(db_path)
    with pool.get_connection() as conn:
        # 创建表结构
        for statement in SCHEMA:
            conn.execute(statement)

        # 创建索引
        for index_sql in INDEXES:
            conn.execute(index_sql)

        # 迁移：为旧版 analyses 表补充缺失的列
        _migrate_analyses_table(conn)
        conn.commit()

    logger.debug(f"数据库初始化完成: {db_path}")


def _migrate_analyses_table(conn: sqlite3.Connection) -> None:
    """为旧版 analyses 表添加 prediction_outcome / prediction_score / prediction_goals 列"""
    try:
        cols = [row[1] for row in conn.execute("PRAGMA table_info(analyses)").fetchall()]
    except sqlite3.OperationalError:
        return  # 表不存在，CREATE TABLE IF NOT EXISTS 会处理
    migrations = [
        ("prediction_outcome", "TEXT"),
        ("prediction_score", "TEXT"),
        ("prediction_goals", "TEXT"),
    ]
    for col_name, col_type in migrations:
        if col_name not in cols:
            conn.execute(f"ALTER TABLE analyses ADD COLUMN {col_name} {col_type}")


def record_match(db_path: Path, record: Dict[str, Any]) -> None:
    """记录比赛信息到数据库"""
    init_history_db(db_path)
    pool = get_connection_pool(db_path)

    with pool.get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO matches (
                match_id, date, league, home_team, away_team,
                match_time, round_info, data_dir, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(record.get("match_id", "")),
                str(record.get("date", "")),
                str(record.get("league", "")),
                str(record.get("home_team", "")),
                str(record.get("away_team", "")),
                str(record.get("match_time", "")),
                str(record.get("round_info", "")),
                str(record.get("data_dir", "")),
                str(record.get("fetched_at", "")),
            ),
        )
        conn.commit()

    logger.debug(f"记录比赛: {record.get('home_team', '')} vs {record.get('away_team', '')}")


def load_matches(db_path: Path, date: str = "", limit: int = 100) -> List[Dict[str, Any]]:
    """加载比赛列表"""
    init_history_db(db_path)
    pool = get_connection_pool(db_path)

    with pool.get_connection() as conn:
        conn.row_factory = sqlite3.Row
        if date:
            rows = conn.execute(
                "SELECT * FROM matches WHERE date = ? ORDER BY match_time LIMIT ?",
                (date, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM matches ORDER BY date DESC, match_time DESC LIMIT ?",
                (limit,),
            ).fetchall()

    result = []
    for row in rows:
        item = dict(row)

        # 提取序号（从 round_info 中，如 "周六217" -> "217"）
        round_info = item.get("round_info", "")
        if round_info:
            import re
            num_match = re.search(r'(\d+)', round_info)
            item["match_number"] = int(num_match.group(1)) if num_match else 0
        else:
            item["match_number"] = 0

        # 检查是否有数据文件
        data_dir = item.get("data_dir", "")
        item["has_data"] = bool(data_dir and Path(data_dir).exists())

        # 检查是否有分析记录
        try:
            analysis_count = conn.execute(
                "SELECT COUNT(*) FROM analyses WHERE match_id = ?",
                (item["match_id"],)
            ).fetchone()[0]
            item["has_analysis"] = analysis_count > 0
        except:
            item["has_analysis"] = False

        result.append(item)

    logger.debug(f"加载比赛列表: {len(result)} 条记录")
    return result


def delete_match(db_path: Path, match_id: str) -> bool:
    """删除单个比赛记录"""
    init_history_db(db_path)
    pool = get_connection_pool(db_path)

    with pool.get_connection() as conn:
        cursor = conn.execute("DELETE FROM matches WHERE match_id = ?", (match_id,))
        conn.commit()
        deleted = cursor.rowcount > 0

    if deleted:
        logger.info(f"删除比赛记录: {match_id}")
    return deleted


def delete_matches(db_path: Path, match_ids: List[str]) -> int:
    """批量删除比赛记录"""
    init_history_db(db_path)
    pool = get_connection_pool(db_path)

    with pool.get_connection() as conn:
        placeholders = ','.join(['?'] * len(match_ids))
        cursor = conn.execute(f"DELETE FROM matches WHERE match_id IN ({placeholders})", match_ids)
        conn.commit()
        deleted_count = cursor.rowcount

    logger.info(f"批量删除比赛记录: {deleted_count} 条")
    return deleted_count


def record_analysis(db_path: Path, record: Dict[str, Any]) -> None:
    """记录分析结果 - 如果同一比赛已有分析记录则更新，否则插入新记录"""
    init_history_db(db_path)
    pool = get_connection_pool(db_path)

    match_id = str(record.get("match_id", ""))
    analysis_type = str(record.get("analysis_type", "full"))
    home_team = str(record.get("home_team", ""))
    away_team = str(record.get("away_team", ""))
    league = str(record.get("league", ""))
    confidence = int(record.get("confidence", 0))
    prediction_json = str(record.get("prediction_json", ""))
    analysis_text = str(record.get("analysis_text", ""))
    brief_text = str(record.get("brief_text", ""))
    created_at = str(record.get("created_at", ""))
    user_key = str(record.get("user_key", ""))
    prediction_outcome = str(record.get("prediction_outcome", ""))
    prediction_score = str(record.get("prediction_score", ""))
    prediction_goals = str(record.get("prediction_goals", ""))

    with pool.get_connection() as conn:
        # 检查是否已有该比赛的分析记录
        existing = conn.execute(
            "SELECT id FROM analyses WHERE match_id = ? ORDER BY id DESC LIMIT 1",
            (match_id,)
        ).fetchone()

        if existing:
            # 更新现有记录
            conn.execute(
                """
                UPDATE analyses SET
                    analysis_type = ?,
                    home_team = ?,
                    away_team = ?,
                    league = ?,
                    confidence = ?,
                    prediction_json = ?,
                    analysis_text = ?,
                    brief_text = ?,
                    created_at = ?,
                    user_key = ?,
                    prediction_outcome = ?,
                    prediction_score = ?,
                    prediction_goals = ?
                WHERE match_id = ?
                """,
                (
                    analysis_type, home_team, away_team, league,
                    confidence, prediction_json, analysis_text, brief_text,
                    created_at, user_key, prediction_outcome, prediction_score,
                    prediction_goals, match_id,
                ),
            )
            logger.debug(f"更新分析记录: {match_id}")
        else:
            # 插入新记录
            conn.execute(
                """
                INSERT INTO analyses (
                    match_id, analysis_type, home_team, away_team, league,
                    confidence, prediction_json, analysis_text, brief_text,
                    created_at, user_key, prediction_outcome, prediction_score,
                    prediction_goals
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    match_id, analysis_type, home_team, away_team, league,
                    confidence, prediction_json, analysis_text, brief_text,
                    created_at, user_key, prediction_outcome, prediction_score,
                    prediction_goals,
                ),
            )
            logger.debug(f"插入新分析记录: {match_id}")

        conn.commit()

    logger.info(f"记录分析结果: {home_team} vs {away_team}, 置信度: {confidence}")


def load_analyses(db_path: Path, match_id: str = "", limit: int = 50) -> List[Dict[str, Any]]:
    """加载分析记录，包含序号信息"""
    init_history_db(db_path)
    pool = get_connection_pool(db_path)

    with pool.get_connection() as conn:
        conn.row_factory = sqlite3.Row
        if match_id:
            rows = conn.execute(
                """
                SELECT a.*, m.round_info
                FROM analyses a
                LEFT JOIN matches m ON a.match_id = m.match_id
                WHERE a.match_id = ?
                ORDER BY a.id DESC
                LIMIT ?
                """,
                (match_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT a.*, m.round_info
                FROM analyses a
                LEFT JOIN matches m ON a.match_id = m.match_id
                ORDER BY a.id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    result = []
    for row in rows:
        item = dict(row)

        # 提取序号（从 round_info 中，如 "周六217" -> 217）
        round_info = item.get("round_info", "")
        if round_info:
            import re
            num_match = re.search(r'(\d+)', round_info)
            item["match_number"] = int(num_match.group(1)) if num_match else 0
        else:
            item["match_number"] = 0

        result.append(item)

    logger.debug(f"加载分析记录: {len(result)} 条")
    return result


def load_analysis_by_id(db_path: Path, analysis_id: int) -> Optional[Dict[str, Any]]:
    """根据 ID 加载单个分析记录"""
    init_history_db(db_path)
    pool = get_connection_pool(db_path)

    with pool.get_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM analyses WHERE id = ?",
            (analysis_id,),
        ).fetchall()

    if rows:
        logger.debug(f"加载分析记录 ID: {analysis_id}")
        return dict(rows[0])
    return None


def record_dashboard_action(db_path: Path, record: Dict[str, Any]) -> None:
    """记录仪表盘操作"""
    init_history_db(db_path)
    pool = get_connection_pool(db_path)

    with pool.get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO dashboard_actions (
                job_id, created_at, action, match_id, status,
                exit_code, summary, data_dir
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(record.get("job_id", "")),
                str(record.get("created_at", "")),
                str(record.get("action", "")),
                str(record.get("match_id", "")),
                str(record.get("status", "")),
                int(record.get("exit_code", 0)),
                str(record.get("summary", "")),
                str(record.get("data_dir", "")),
            ),
        )
        conn.commit()

    logger.debug(f"记录仪表盘操作: {record.get('action', '')}")


def load_dashboard_actions(db_path: Path, limit: int = 100) -> List[Dict[str, Any]]:
    """加载仪表盘操作记录"""
    init_history_db(db_path)
    pool = get_connection_pool(db_path)

    with pool.get_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM dashboard_actions ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()

    result = [dict(row) for row in rows]
    logger.debug(f"加载仪表盘操作: {len(result)} 条")
    return result


def save_dashboard_config(db_path: Path, config: Dict[str, str]) -> None:
    """保存仪表盘配置"""
    init_history_db(db_path)
    pool = get_connection_pool(db_path)
    allowed = {"llm_provider", "llm_base_url", "llm_model", "llm_api_key"}

    with pool.get_connection() as conn:
        for key, value in config.items():
            if key not in allowed:
                continue
            conn.execute(
                "INSERT OR REPLACE INTO dashboard_config (key, value) VALUES (?, ?)",
                (key, str(value or "")),
            )
        conn.commit()

    logger.info(f"保存仪表盘配置: {list(config.keys())}")


def load_dashboard_config(db_path: Path) -> Dict[str, str]:
    """加载仪表盘配置"""
    init_history_db(db_path)
    pool = get_connection_pool(db_path)

    with pool.get_connection() as conn:
        rows = conn.execute("SELECT key, value FROM dashboard_config").fetchall()

    config = {str(key): str(value) for key, value in rows}
    logger.debug(f"加载仪表盘配置: {list(config.keys())}")
    return config


def record_match_result(db_path: Path, result: Dict[str, Any]) -> None:
    """记录比赛结果"""
    init_history_db(db_path)
    pool = get_connection_pool(db_path)

    with pool.get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO match_results (
                match_id, home_score, away_score, result,
                half_home_score, half_away_score, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(result.get("match_id", "")),
                int(result.get("home_score", 0)),
                int(result.get("away_score", 0)),
                str(result.get("result", "")),
                int(result.get("half_home_score", 0) or 0),
                int(result.get("half_away_score", 0) or 0),
                str(result.get("fetched_at", "")),
            ),
        )
        conn.commit()

    logger.info(f"记录比赛结果: {result.get('match_id', '')}")


def load_match_result(db_path: Path, match_id: str) -> Optional[Dict[str, Any]]:
    """加载单场比赛结果"""
    init_history_db(db_path)
    pool = get_connection_pool(db_path)

    with pool.get_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM match_results WHERE match_id = ?",
            (match_id,),
        ).fetchall()

    if rows:
        logger.debug(f"加载比赛结果: {match_id}")
        return dict(rows[0])
    return None


def load_all_match_results(db_path: Path, limit: int = 100) -> List[Dict[str, Any]]:
    """加载所有比赛结果"""
    init_history_db(db_path)
    pool = get_connection_pool(db_path)

    with pool.get_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM match_results ORDER BY fetched_at DESC LIMIT ?",
            (limit,),
        ).fetchall()

    result = [dict(row) for row in rows]
    logger.debug(f"加载所有比赛结果: {len(result)} 条")
    return result


def update_analysis_prediction(db_path: Path, analysis_id: int, prediction: Dict[str, Any]) -> None:
    """更新分析记录的预测结果"""
    init_history_db(db_path)
    pool = get_connection_pool(db_path)

    with pool.get_connection() as conn:
        conn.execute(
            """
            UPDATE analyses SET
                prediction_outcome = ?,
                prediction_score = ?
            WHERE id = ?
            """,
            (
                str(prediction.get("outcome", "")),
                str(prediction.get("score", "")),
                analysis_id,
            ),
        )
        conn.commit()

    logger.debug(f"更新分析预测: ID={analysis_id}")


def get_analysis_with_results(db_path: Path, limit: int = 50) -> List[Dict[str, Any]]:
    """获取分析记录及对应的比赛结果，计算命中状态，并关联赛事序号"""
    init_history_db(db_path)
    pool = get_connection_pool(db_path)

    with pool.get_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT
                a.id, a.match_id, a.home_team, a.away_team, a.league,
                a.confidence, a.prediction_outcome, a.prediction_score,
                a.prediction_goals, a.brief_text, a.created_at,
                m.round_info,
                r.home_score, r.away_score, r.result
            FROM analyses a
            INNER JOIN matches m ON a.match_id = m.match_id
            LEFT JOIN match_results r ON a.match_id = r.match_id
            ORDER BY a.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    results = []
    for row in rows:
        item = dict(row)
        # 提取序号（从 round_info 中，如 "周四201" -> "201"）
        round_info = item.get("round_info", "")
        if round_info:
            # 提取数字部分作为序号
            import re
            match = re.search(r'(\d+)', round_info)
            item["match_number"] = match.group(1) if match else ""
        else:
            item["match_number"] = ""

        # 计算三项命中状态
        item["hit_status"], item["hit_count"] = _calculate_hit_status(item)
        results.append(item)

    logger.debug(f"获取分析结果: {len(results)} 条")
    return results


def clear_analyses(db_path: Path) -> int:
    """清除所有分析记录，返回删除的记录数"""
    init_history_db(db_path)
    pool = get_connection_pool(db_path)

    with pool.get_connection() as conn:
        cursor = conn.execute("DELETE FROM analyses")
        conn.commit()
        deleted_count = cursor.rowcount

    logger.info(f"清除分析记录: {deleted_count} 条")
    return deleted_count


def _calculate_hit_status(analysis: Dict[str, Any]) -> Tuple[str, int]:
    """计算预测命中状态（胜平负、比分、进球数三项），返回 (状态文字, 命中数)"""
    prediction_outcome = analysis.get("prediction_outcome", "")
    actual_result = analysis.get("result", "")
    prediction_score = analysis.get("prediction_score", "")
    prediction_goals = analysis.get("prediction_goals", "")
    home_score = analysis.get("home_score")
    away_score = analysis.get("away_score")

    if not actual_result:
        return "待开奖", 0

    if not prediction_outcome:
        return "无预测", 0

    hits = 0
    total = 3  # 胜平负 + 比分 + 进球数

    # 1) 胜平负命中
    outcome_hit = prediction_outcome == actual_result
    if outcome_hit:
        hits += 1

    # 2) 比分命中
    score_hit = False
    if prediction_score and home_score is not None and away_score is not None:
        actual_score = f"{home_score}-{away_score}"
        if prediction_score == actual_score:
            score_hit = True
            hits += 1

    # 3) 进球数命中
    goals_hit = False
    if prediction_goals and home_score is not None and away_score is not None:
        actual_total = int(home_score) + int(away_score)
        # 解析预测进球数：支持 "3球"/"3"/"2-3球"/"3球以上" 等格式
        import re
        # 纯数字
        m = re.match(r'^(\d+)$', prediction_goals.strip())
        if m:
            pred_total = int(m.group(1))
            if pred_total == actual_total:
                goals_hit = True
                hits += 1
        else:
            # 范围格式 "2-3球" / "2~3球"
            m = re.match(r'^(\d+)\s*[-~到]\s*(\d+)', prediction_goals)
            if m:
                low, high = int(m.group(1)), int(m.group(2))
                if low <= actual_total <= high:
                    goals_hit = True
                    hits += 1
            else:
                # "X球以上" / "X球以下"
                m = re.match(r'^(\d+)\s*球?\s*(以上|以下|≥|≤|>=|<=)', prediction_goals)
                if m:
                    threshold = int(m.group(1))
                    direction = m.group(2)
                    if direction in ("以上", "≥", ">=") and actual_total >= threshold:
                        goals_hit = True
                        hits += 1
                    elif direction in ("以下", "≤", "<=") and actual_total <= threshold:
                        goals_hit = True
                        hits += 1

    # 组装状态文字
    if hits == total:
        status = "✅ 3/3全中"
    elif hits == 2:
        detail = []
        if outcome_hit: detail.append("方向")
        if score_hit: detail.append("比分")
        if goals_hit: detail.append("进球")
        status = f"✅ 2/3中({'+'.join(detail)})"
    elif hits == 1:
        detail = []
        if outcome_hit: detail.append("方向")
        if score_hit: detail.append("比分")
        if goals_hit: detail.append("进球")
        status = f"🔶 1/3中({'+'.join(detail)})"
    else:
        status = "❌ 0/3未中"

    return status, hits


def get_hit_statistics(db_path: Path) -> Dict[str, Any]:
    """获取命中率统计"""
    analyses = get_analysis_with_results(db_path, limit=1000)

    total = len(analyses)
    pending = sum(1 for a in analyses if "待开奖" in a["hit_status"])
    no_pred = sum(1 for a in analyses if "无预测" in a["hit_status"])
    # 至少命中1项的都算"方向中"
    hit = sum(1 for a in analyses if a.get("hit_count", 0) >= 1)
    miss = sum(1 for a in analyses if "未中" in a["hit_status"])

    judged = hit + miss
    hit_rate = round(hit / judged * 100, 1) if judged > 0 else 0

    # 三项分别统计
    outcome_hits = sum(1 for a in analyses if a.get("hit_count", 0) >= 1 and "方向" not in a.get("hit_status","未中"))
    score_hits = sum(1 for a in analyses if a.get("hit_count", 0) >= 1 and "比分" in a.get("hit_status",""))
    goals_hits = sum(1 for a in analyses if a.get("hit_count", 0) >= 1 and "进球" in a.get("hit_status",""))

    return {
        "total": total,
        "pending": pending,
        "no_prediction": no_pred,
        "hit": hit,
        "miss": miss,
        "hit_rate": hit_rate,
        "outcome_hits": outcome_hits,
        "score_hits": score_hits,
        "goals_hits": goals_hits,
    }
