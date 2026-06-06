"""监控模块 - 提供 Prometheus metrics 和健康检查"""

import sys
import time
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

from football_sim.logger import get_logger

logger = get_logger(__name__)

try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        Info,
        generate_latest,
        CONTENT_TYPE_LATEST,
        REGISTRY,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus-client 未安装，监控功能将使用简化模式")


# ============================================================
# Prometheus Metrics 定义
# ============================================================

if PROMETHEUS_AVAILABLE:
    # HTTP 请求指标
    HTTP_REQUESTS = Counter(
        'football_http_requests_total',
        'Total HTTP requests',
        ['method', 'endpoint', 'status']
    )

    HTTP_REQUEST_DURATION = Histogram(
        'football_http_request_duration_seconds',
        'HTTP request duration in seconds',
        ['method', 'endpoint'],
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
    )

    HTTP_REQUESTS_IN_PROGRESS = Gauge(
        'football_http_requests_in_progress',
        'Number of HTTP requests in progress',
        ['method', 'endpoint']
    )

    # 数据库指标
    DB_QUERY_DURATION = Histogram(
        'football_db_query_duration_seconds',
        'Database query duration in seconds',
        ['operation'],
        buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
    )

    DB_CONNECTIONS = Gauge(
        'football_db_connections',
        'Number of database connections',
        ['pool']
    )

    # 缓存指标
    CACHE_HITS = Counter(
        'football_cache_hits_total',
        'Total cache hits',
        ['cache_name']
    )

    CACHE_MISSES = Counter(
        'football_cache_misses_total',
        'Total cache misses',
        ['cache_name']
    )

    CACHE_SIZE = Gauge(
        'football_cache_size',
        'Current cache size',
        ['cache_name']
    )

    # 业务指标
    MATCHES_FETCHED = Counter(
        'football_matches_fetched_total',
        'Total matches fetched'
    )

    ANALYSES_PERFORMED = Counter(
        'football_analyses_performed_total',
        'Total analyses performed',
        ['result']  # success, failed
    )

    LLM_CALLS = Counter(
        'football_llm_calls_total',
        'Total LLM API calls',
        ['status']  # success, error, timeout
    )

    LLM_CALL_DURATION = Histogram(
        'football_llm_call_duration_seconds',
        'LLM API call duration in seconds',
        buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0]
    )

    ODDS_FETCH_DURATION = Histogram(
        'football_odds_fetch_duration_seconds',
        'Odds fetch duration in seconds',
        ['match_count']
    )

    # 系统指标
    SYSTEM_INFO = Info(
        'football_system',
        'System information'
    )

    ACTIVE_USERS = Gauge(
        'football_active_users',
        'Number of active users'
    )

    BACKUP_STATUS = Gauge(
        'football_backup_status',
        'Backup status (1=success, 0=failure)'
    )

    BACKUP_DURATION = Histogram(
        'football_backup_duration_seconds',
        'Backup duration in seconds',
        buckets=[10.0, 30.0, 60.0, 300.0, 600.0]
    )


class MetricsCollector:
    """指标收集器"""

    def __init__(self):
        self._start_time = time.time()
        self._request_count = 0
        self._error_count = 0

    def record_http_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration: float
    ):
        """记录 HTTP 请求"""
        if PROMETHEUS_AVAILABLE:
            HTTP_REQUESTS.labels(
                method=method,
                endpoint=endpoint,
                status=str(status_code)
            ).inc()

            HTTP_REQUEST_DURATION.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)

        self._request_count += 1
        if status_code >= 400:
            self._error_count += 1

    def record_db_query(self, operation: str, duration: float):
        """记录数据库查询"""
        if PROMETHEUS_AVAILABLE:
            DB_QUERY_DURATION.labels(operation=operation).observe(duration)

    def record_cache_hit(self, cache_name: str):
        """记录缓存命中"""
        if PROMETHEUS_AVAILABLE:
            CACHE_HITS.labels(cache_name=cache_name).inc()

    def record_cache_miss(self, cache_name: str):
        """记录缓存未命中"""
        if PROMETHEUS_AVAILABLE:
            CACHE_MISSES.labels(cache_name=cache_name).inc()

    def update_cache_size(self, cache_name: str, size: int):
        """更新缓存大小"""
        if PROMETHEUS_AVAILABLE:
            CACHE_SIZE.labels(cache_name=cache_name).set(size)

    def record_match_fetched(self):
        """记录比赛抓取"""
        if PROMETHEUS_AVAILABLE:
            MATCHES_FETCHED.inc()

    def record_analysis(self, success: bool):
        """记录分析操作"""
        if PROMETHEUS_AVAILABLE:
            ANALYSES_PERFORMED.labels(
                result="success" if success else "failed"
            ).inc()

    def record_llm_call(self, status: str, duration: float):
        """记录 LLM 调用"""
        if PROMETHEUS_AVAILABLE:
            LLM_CALLS.labels(status=status).inc()
            LLM_CALL_DURATION.observe(duration)

    def record_odds_fetch(self, match_count: int, duration: float):
        """记录赔率抓取"""
        if PROMETHEUS_AVAILABLE:
            ODDS_FETCH_DURATION.labels(
                match_count=str(match_count)
            ).observe(duration)

    def record_backup(self, success: bool, duration: float):
        """记录备份操作"""
        if PROMETHEUS_AVAILABLE:
            BACKUP_STATUS.set(1 if success else 0)
            BACKUP_DURATION.observe(duration)

    def set_system_info(self, info: Dict[str, str]):
        """设置系统信息"""
        if PROMETHEUS_AVAILABLE:
            SYSTEM_INFO.info(info)

    def set_active_users(self, count: int):
        """设置活跃用户数"""
        if PROMETHEUS_AVAILABLE:
            ACTIVE_USERS.set(count)

    def get_metrics(self) -> str:
        """获取 Prometheus 格式的指标"""
        if PROMETHEUS_AVAILABLE:
            return generate_latest(REGISTRY).decode('utf-8')
        return "# Prometheus client not available\n"

    def get_metrics_content_type(self) -> str:
        """获取指标内容类型"""
        if PROMETHEUS_AVAILABLE:
            return CONTENT_TYPE_LATEST
        return "text/plain"

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        uptime = time.time() - self._start_time
        return {
            "uptime_seconds": round(uptime, 2),
            "uptime_human": self._format_uptime(uptime),
            "total_requests": self._request_count,
            "total_errors": self._error_count,
            "error_rate": f"{(self._error_count / self._request_count * 100) if self._request_count > 0 else 0:.1f}%"
        }

    def _format_uptime(self, seconds: float) -> str:
        """格式化运行时间"""
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        parts = []
        if days > 0:
            parts.append(f"{days}天")
        if hours > 0:
            parts.append(f"{hours}小时")
        if minutes > 0:
            parts.append(f"{minutes}分钟")
        parts.append(f"{secs}秒")

        return " ".join(parts)


# 全局指标收集器
_metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """获取全局指标收集器"""
    return _metrics_collector


# ============================================================
# 装饰器
# ============================================================

def track_request(method: str, endpoint: str):
    """HTTP 请求跟踪装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status_code = 200

            if PROMETHEUS_AVAILABLE:
                HTTP_REQUESTS_IN_PROGRESS.labels(
                    method=method,
                    endpoint=endpoint
                ).inc()

            try:
                result = await func(*args, **kwargs)
                if hasattr(result, 'status_code'):
                    status_code = result.status_code
                return result
            except Exception as e:
                status_code = 500
                raise
            finally:
                duration = time.time() - start_time
                _metrics_collector.record_http_request(
                    method, endpoint, status_code, duration
                )

                if PROMETHEUS_AVAILABLE:
                    HTTP_REQUESTS_IN_PROGRESS.labels(
                        method=method,
                        endpoint=endpoint
                    ).dec()

        return wrapper
    return decorator


def track_db_query(operation: str):
    """数据库查询跟踪装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                _metrics_collector.record_db_query(operation, duration)

        return wrapper
    return decorator


def track_llm_call(status: str):
    """LLM 调用跟踪装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                _metrics_collector.record_llm_call(status, time.time() - start_time)
                return result
            except Exception as e:
                _metrics_collector.record_llm_call("error", time.time() - start_time)
                raise

        return wrapper
    return decorator


# ============================================================
# 健康检查
# ============================================================

@dataclass
class HealthCheckResult:
    """健康检查结果"""
    status: str  # healthy, degraded, unhealthy
    checks: Dict[str, Any]
    timestamp: str
    uptime: str
    version: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "checks": self.checks,
            "timestamp": self.timestamp,
            "uptime": self.uptime,
            "version": self.version
        }


class HealthChecker:
    """健康检查器"""

    def __init__(self):
        self._checks: Dict[str, Callable] = {}
        self._start_time = time.time()
        self._version = "1.0.0"

    def register_check(self, name: str, check_func: Callable):
        """注册健康检查"""
        self._checks[name] = check_func

    def check_database(self) -> Dict[str, Any]:
        """检查数据库健康状态"""
        try:
            from football_sim.config import get_database_path
            from football_sim.history_db import init_history_db

            db_path = get_database_path()
            if not db_path.exists():
                return {
                    "status": "unhealthy",
                    "message": "数据库文件不存在"
                }

            # 尝试连接
            init_history_db(db_path)

            return {
                "status": "healthy",
                "message": "数据库连接正常",
                "path": str(db_path),
                "size_mb": round(db_path.stat().st_size / (1024 * 1024), 2)
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"数据库错误: {str(e)}"
            }

    def check_llm_config(self) -> Dict[str, Any]:
        """检查 LLM 配置"""
        try:
            from football_sim.config import get_settings
            settings = get_settings()

            if not settings.llm.base_url:
                return {
                    "status": "degraded",
                    "message": "未配置 LLM API"
                }

            if not settings.llm.api_key:
                return {
                    "status": "degraded",
                    "message": "未配置 LLM API Key"
                }

            return {
                "status": "healthy",
                "message": "LLM 配置正常",
                "provider": settings.llm.provider,
                "model": settings.llm.model
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"LLM 配置错误: {str(e)}"
            }

    def check_disk_space(self) -> Dict[str, Any]:
        """检查磁盘空间"""
        try:
            import shutil
            from football_sim.config import get_settings

            settings = get_settings()
            data_dir = settings.data_dir

            total, used, free = shutil.disk_usage(data_dir)
            free_gb = free / (1024 ** 3)
            usage_percent = (used / total) * 100

            status = "healthy"
            if free_gb < 1:
                status = "unhealthy"
            elif free_gb < 5:
                status = "degraded"

            return {
                "status": status,
                "message": f"可用空间: {free_gb:.1f}GB",
                "free_gb": round(free_gb, 2),
                "usage_percent": round(usage_percent, 1)
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"磁盘检查失败: {str(e)}"
            }

    def check_cache(self) -> Dict[str, Any]:
        """检查缓存状态"""
        try:
            from football_sim.cache import get_all_cache_stats
            stats = get_all_cache_stats()

            return {
                "status": "healthy",
                "message": "缓存正常",
                "stats": stats
            }
        except Exception as e:
            return {
                "status": "degraded",
                "message": f"缓存检查失败: {str(e)}"
            }

    def check_memory(self) -> Dict[str, Any]:
        """检查内存使用"""
        try:
            import psutil

            memory = psutil.virtual_memory()
            available_gb = memory.available / (1024 ** 3)
            usage_percent = memory.percent

            status = "healthy"
            if available_gb < 0.5:
                status = "unhealthy"
            elif available_gb < 1:
                status = "degraded"

            return {
                "status": status,
                "message": f"可用内存: {available_gb:.1f}GB",
                "available_gb": round(available_gb, 2),
                "usage_percent": usage_percent
            }
        except ImportError:
            return {
                "status": "healthy",
                "message": "psutil 未安装，跳过内存检查"
            }
        except Exception as e:
            return {
                "status": "degraded",
                "message": f"内存检查失败: {str(e)}"
            }

    def run_all_checks(self) -> HealthCheckResult:
        """运行所有健康检查"""
        checks = {}
        overall_status = "healthy"

        # 注册默认检查
        default_checks = {
            "database": self.check_database,
            "llm_config": self.check_llm_config,
            "disk_space": self.check_disk_space,
            "cache": self.check_cache,
            "memory": self.check_memory,
        }

        all_checks = {**default_checks, **self._checks}

        for name, check_func in all_checks.items():
            try:
                result = check_func()
                checks[name] = result

                # 更新总体状态
                if result.get("status") == "unhealthy":
                    overall_status = "unhealthy"
                elif result.get("status") == "degraded" and overall_status != "unhealthy":
                    overall_status = "degraded"

            except Exception as e:
                checks[name] = {
                    "status": "unhealthy",
                    "message": f"检查失败: {str(e)}"
                }
                overall_status = "unhealthy"

        uptime = time.time() - self._start_time
        uptime_str = _metrics_collector._format_uptime(uptime)

        return HealthCheckResult(
            status=overall_status,
            checks=checks,
            timestamp=datetime.now().isoformat(),
            uptime=uptime_str,
            version=self._version
        )

    def set_version(self, version: str):
        """设置版本号"""
        self._version = version


# 全局健康检查器
_health_checker = HealthChecker()


def get_health_checker() -> HealthChecker:
    """获取全局健康检查器"""
    return _health_checker


# ============================================================
# 初始化函数
# ============================================================

def init_monitoring(version: str = "1.0.0"):
    """初始化监控系统"""
    if PROMETHEUS_AVAILABLE:
        # 设置系统信息
        _metrics_collector.set_system_info({
            "version": version,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "platform": sys.platform,
        })

    _health_checker.set_version(version)
    logger.info(f"监控系统初始化完成 (版本: {version})")


def get_prometheus_metrics() -> str:
    """获取 Prometheus 格式的指标"""
    return _metrics_collector.get_metrics()


def get_health_status() -> Dict[str, Any]:
    """获取健康状态"""
    result = _health_checker.run_all_checks()
    return result.to_dict()


# 导出
__all__ = [
    'MetricsCollector',
    'get_metrics_collector',
    'HealthChecker',
    'get_health_checker',
    'init_monitoring',
    'get_prometheus_metrics',
    'get_health_status',
    'track_request',
    'track_db_query',
    'track_llm_call',
]
