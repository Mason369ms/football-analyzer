"""定时任务调度模块 - 提供自动化数据抓取和分析"""

import asyncio
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from football_sim.logger import get_logger

logger = get_logger(__name__)

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    logger.warning("APScheduler 未安装，定时任务功能将不可用")


class TaskScheduler:
    """任务调度器"""

    def __init__(self, use_async: bool = False):
        """
        初始化调度器

        Args:
            use_async: 是否使用异步调度器
        """
        self._scheduler = None
        self._running = False
        self._tasks: Dict[str, Dict[str, Any]] = {}

        if APSCHEDULER_AVAILABLE:
            if use_async:
                self._scheduler = AsyncIOScheduler()
            else:
                self._scheduler = BackgroundScheduler()
        else:
            logger.warning("APScheduler 不可用，使用简化模式")

    def add_cron_task(
        self,
        task_id: str,
        func: Callable,
        hour: int = 0,
        minute: int = 0,
        second: int = 0,
        args: tuple = (),
        kwargs: dict = None,
        description: str = ""
    ):
        """
        添加定时任务

        Args:
            task_id: 任务 ID
            func: 任务函数
            hour: 小时
            minute: 分钟
            second: 秒
            args: 位置参数
            kwargs: 关键字参数
            description: 任务描述
        """
        if not APSCHEDULER_AVAILABLE or not self._scheduler:
            logger.warning(f"无法添加定时任务: {task_id} (APScheduler 不可用)")
            return

        trigger = CronTrigger(hour=hour, minute=minute, second=second)

        job = self._scheduler.add_job(
            func,
            trigger=trigger,
            args=args or (),
            kwargs=kwargs or {},
            id=task_id,
            name=description or task_id,
            replace_existing=True
        )

        self._tasks[task_id] = {
            "id": task_id,
            "func": func.__name__,
            "trigger": f"{hour:02d}:{minute:02d}:{second:02d}",
            "description": description,
            "next_run": job.next_run_time
        }

        logger.info(f"添加定时任务: {task_id} ({hour:02d}:{minute:02d}:{second:02d})")

    def add_interval_task(
        self,
        task_id: str,
        func: Callable,
        hours: int = 0,
        minutes: int = 0,
        seconds: int = 0,
        args: tuple = (),
        kwargs: dict = None,
        description: str = ""
    ):
        """
        添加间隔任务

        Args:
            task_id: 任务 ID
            func: 任务函数
            hours: 小时间隔
            minutes: 分钟间隔
            seconds: 秒间隔
            args: 位置参数
            kwargs: 关键字参数
            description: 任务描述
        """
        if not APSCHEDULER_AVAILABLE or not self._scheduler:
            logger.warning(f"无法添加间隔任务: {task_id} (APScheduler 不可用)")
            return

        trigger = IntervalTrigger(
            hours=hours,
            minutes=minutes,
            seconds=seconds
        )

        job = self._scheduler.add_job(
            func,
            trigger=trigger,
            args=args or (),
            kwargs=kwargs or {},
            id=task_id,
            name=description or task_id,
            replace_existing=True
        )

        interval_str = f"{hours}h {minutes}m {seconds}s"
        self._tasks[task_id] = {
            "id": task_id,
            "func": func.__name__,
            "trigger": f"every {interval_str}",
            "description": description,
            "next_run": job.next_run_time
        }

        logger.info(f"添加间隔任务: {task_id} (every {interval_str})")

    def remove_task(self, task_id: str) -> bool:
        """移除任务"""
        if not APSCHEDULER_AVAILABLE or not self._scheduler:
            return False

        try:
            self._scheduler.remove_job(task_id)
            if task_id in self._tasks:
                del self._tasks[task_id]
            logger.info(f"移除任务: {task_id}")
            return True
        except Exception as e:
            logger.error(f"移除任务失败 {task_id}: {e}")
            return False

    def start(self):
        """启动调度器"""
        if not APSCHEDULER_AVAILABLE or not self._scheduler:
            logger.warning("调度器无法启动 (APScheduler 不可用)")
            return

        if not self._running:
            self._scheduler.start()
            self._running = True
            logger.info("任务调度器已启动")

    def stop(self):
        """停止调度器"""
        if self._scheduler and self._running:
            self._scheduler.shutdown()
            self._running = False
            logger.info("任务调度器已停止")

    def get_tasks(self) -> List[Dict[str, Any]]:
        """获取所有任务"""
        tasks = list(self._tasks.values())

        # 更新下次运行时间
        if APSCHEDULER_AVAILABLE and self._scheduler:
            for task in tasks:
                job = self._scheduler.get_job(task["id"])
                if job:
                    task["next_run"] = str(job.next_run_time) if job.next_run_time else None

        return tasks

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        return self._tasks.get(task_id)

    @property
    def is_running(self) -> bool:
        """调度器是否运行中"""
        return self._running


# ============================================================
# 预定义任务
# ============================================================

class FootballTasks:
    """足球分析系统预定义任务"""

    def __init__(self, scheduler: TaskScheduler):
        self.scheduler = scheduler

    def register_default_tasks(self):
        """注册默认任务"""
        # 每日 8 点抓取今日赛事
        self.scheduler.add_cron_task(
            task_id="daily_fetch_matches",
            func=self.fetch_daily_matches,
            hour=8,
            minute=0,
            description="每日赛事抓取"
        )

        # 每日 9 点自动分析
        self.scheduler.add_cron_task(
            task_id="daily_analyze",
            func=self.analyze_daily_matches,
            hour=9,
            minute=0,
            description="每日赛事分析"
        )

        # 每日 22 点获取比赛结果
        self.scheduler.add_cron_task(
            task_id="daily_fetch_results",
            func=self.fetch_daily_results,
            hour=22,
            minute=0,
            description="每日结果获取"
        )

        # 每小时清理过期缓存
        self.scheduler.add_interval_task(
            task_id="cache_cleanup",
            func=self.cleanup_cache,
            hours=1,
            description="缓存清理"
        )

        # 每日 3 点自动备份
        self.scheduler.add_cron_task(
            task_id="daily_backup",
            func=self.create_daily_backup,
            hour=3,
            minute=0,
            description="每日自动备份"
        )

        logger.info("默认任务已注册")

    def fetch_daily_matches(self):
        """抓取每日赛事"""
        try:
            from football_sim.cli import fetch_matches
            logger.info("开始抓取今日赛事...")
            fetch_matches(date="today")
            logger.info("今日赛事抓取完成")
        except Exception as e:
            logger.error(f"抓取今日赛事失败: {e}")

    def analyze_daily_matches(self):
        """分析每日赛事"""
        try:
            from football_sim.cli import analyze_matches
            logger.info("开始分析今日赛事...")
            analyze_matches(date="today")
            logger.info("今日赛事分析完成")
        except Exception as e:
            logger.error(f"分析今日赛事失败: {e}")

    def fetch_daily_results(self):
        """获取每日结果"""
        try:
            from football_sim.cli import fetch_results
            logger.info("开始获取今日比赛结果...")
            fetch_results(date="today")
            logger.info("今日比赛结果获取完成")
        except Exception as e:
            logger.error(f"获取今日比赛结果失败: {e}")

    def cleanup_cache(self):
        """清理缓存"""
        try:
            from football_sim.cache import get_all_cache_stats, _analysis_cache, _match_cache, _odds_cache
            _analysis_cache.cleanup_expired()
            _match_cache.cleanup_expired()
            _odds_cache.cleanup_expired()
            logger.debug("缓存清理完成")
        except Exception as e:
            logger.error(f"缓存清理失败: {e}")

    def create_daily_backup(self):
        """创建每日备份"""
        try:
            from football_sim.backup import get_backup_manager
            backup_manager = get_backup_manager()
            backup_manager.create_backup(
                name=f"daily_backup_{datetime.now().strftime('%Y%m%d')}"
            )
            logger.info("每日备份创建完成")
        except Exception as e:
            logger.error(f"每日备份创建失败: {e}")


# 全局调度器实例
_scheduler: Optional[TaskScheduler] = None
_football_tasks: Optional[FootballTasks] = None


def get_scheduler() -> TaskScheduler:
    """获取全局调度器"""
    global _scheduler
    if _scheduler is None:
        _scheduler = TaskScheduler(use_async=False)
    return _scheduler


def get_football_tasks() -> FootballTasks:
    """获取足球任务管理器"""
    global _football_tasks
    if _football_tasks is None:
        _football_tasks = FootballTasks(get_scheduler())
    return _football_tasks


def start_scheduler():
    """启动调度器"""
    scheduler = get_scheduler()

    # 注册默认任务
    tasks = get_football_tasks()
    tasks.register_default_tasks()

    scheduler.start()
    logger.info("任务调度系统已启动")


def stop_scheduler():
    """停止调度器"""
    global _scheduler
    if _scheduler:
        _scheduler.stop()


def get_scheduled_tasks() -> List[Dict[str, Any]]:
    """获取所有已调度的任务"""
    return get_scheduler().get_tasks()


# ============================================================
# 简化的调度器（APScheduler 不可用时）
# ============================================================

class SimpleScheduler:
    """简化的调度器 - 当 APScheduler 不可用时使用"""

    def __init__(self):
        self._tasks: List[Dict[str, Any]] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def add_task(
        self,
        task_id: str,
        func: Callable,
        interval_seconds: int,
        args: tuple = (),
        kwargs: dict = None
    ):
        """添加任务"""
        self._tasks.append({
            "id": task_id,
            "func": func,
            "interval": interval_seconds,
            "args": args or (),
            "kwargs": kwargs or {},
            "last_run": None
        })

    def start(self):
        """启动调度器"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("简化调度器已启动")

    def stop(self):
        """停止调度器"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self):
        """运行调度器"""
        while self._running:
            now = time.time()
            for task in self._tasks:
                if task["last_run"] is None or (now - task["last_run"]) >= task["interval"]:
                    try:
                        task["func"](*task["args"], **task["kwargs"])
                        task["last_run"] = now
                    except Exception as e:
                        logger.error(f"任务执行失败 {task['id']}: {e}")

            time.sleep(1)


# 导出
__all__ = [
    'TaskScheduler',
    'FootballTasks',
    'get_scheduler',
    'get_football_tasks',
    'start_scheduler',
    'stop_scheduler',
    'get_scheduled_tasks',
    'SimpleScheduler',
]
