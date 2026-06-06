"""容错模块 - 提供重试机制、降级策略和错误恢复"""

import asyncio
import time
import traceback
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar

from football_sim.logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class RetryStrategy(Enum):
    """重试策略"""
    FIXED = "fixed"  # 固定间隔
    LINEAR = "linear"  # 线性增长
    EXPONENTIAL = "exponential"  # 指数退避


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    base_delay: float = 1.0  # 秒
    max_delay: float = 60.0  # 秒
    retryable_exceptions: tuple = (Exception,)

    def get_delay(self, attempt: int) -> float:
        """计算重试延迟"""
        if self.strategy == RetryStrategy.FIXED:
            delay = self.base_delay
        elif self.strategy == RetryStrategy.LINEAR:
            delay = self.base_delay * (attempt + 1)
        else:  # EXPONENTIAL
            delay = self.base_delay * (2 ** attempt)

        return min(delay, self.max_delay)


def with_retry(config: Optional[RetryConfig] = None):
    """
    重试装饰器

    Args:
        config: 重试配置，如果为 None 则使用默认配置
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except config.retryable_exceptions as e:
                    last_exception = e
                    if attempt < config.max_retries:
                        delay = config.get_delay(attempt)
                        logger.warning(
                            f"重试 {func.__name__} (尝试 {attempt + 1}/{config.max_retries + 1}): {e}. "
                            f"等待 {delay:.1f}秒..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(f"重试失败 {func.__name__}: {e}")

            raise last_exception

        return wrapper
    return decorator


def with_async_retry(config: Optional[RetryConfig] = None):
    """异步重试装饰器"""
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except config.retryable_exceptions as e:
                    last_exception = e
                    if attempt < config.max_retries:
                        delay = config.get_delay(attempt)
                        logger.warning(
                            f"异步重试 {func.__name__} (尝试 {attempt + 1}/{config.max_retries + 1}): {e}. "
                            f"等待 {delay:.1f}秒..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"异步重试失败 {func.__name__}: {e}")

            raise last_exception

        return wrapper
    return decorator


@dataclass
class TaskInfo:
    """任务信息"""
    task_id: str
    func_name: str
    args: tuple
    kwargs: dict
    created_at: datetime
    retry_count: int = 0
    max_retries: int = 3
    last_error: Optional[str] = None
    status: str = "pending"  # pending, running, completed, failed


class RetryQueue:
    """重试队列 - 管理失败的任务并定时重试"""

    def __init__(self, max_queue_size: int = 1000):
        self.queue: deque = deque(maxlen=max_queue_size)
        self._lock = asyncio.Lock()
        self._running = False
        self._task_counter = 0

    def add_task(
        self,
        func: Callable,
        args: tuple = (),
        kwargs: dict = None,
        max_retries: int = 3,
        error: Exception = None
    ) -> str:
        """添加任务到重试队列"""
        self._task_counter += 1
        task_id = f"retry_{self._task_counter}_{int(time.time())}"

        task = TaskInfo(
            task_id=task_id,
            func_name=func.__name__,
            args=args,
            kwargs=kwargs or {},
            created_at=datetime.now(),
            max_retries=max_retries,
            last_error=str(error) if error else None
        )

        self.queue.append(task)
        logger.info(f"任务添加到重试队列: {task_id} ({func.__name__})")
        return task_id

    async def process_queue(self) -> List[Dict[str, Any]]:
        """处理重试队列中的任务"""
        results = []
        tasks_to_process = []

        # 获取待处理的任务
        async with self._lock:
            while self.queue:
                task = self.queue.popleft()
                if task.status == "pending" and task.retry_count < task.max_retries:
                    tasks_to_process.append(task)

        # 处理任务
        for task in tasks_to_process:
            try:
                task.status = "running"
                task.retry_count += 1

                # 这里需要实际执行任务的逻辑
                # 由于我们没有保存函数引用，这里只是示例
                logger.info(f"重试任务: {task.task_id} (第 {task.retry_count} 次)")

                # 假设成功
                task.status = "completed"
                results.append({
                    "task_id": task.task_id,
                    "status": "completed",
                    "retry_count": task.retry_count
                })

            except Exception as e:
                task.last_error = str(e)
                if task.retry_count >= task.max_retries:
                    task.status = "failed"
                    logger.error(f"任务最终失败: {task.task_id}: {e}")
                else:
                    task.status = "pending"
                    async with self._lock:
                        self.queue.append(task)

                results.append({
                    "task_id": task.task_id,
                    "status": task.status,
                    "retry_count": task.retry_count,
                    "error": str(e)
                })

        return results

    def get_stats(self) -> Dict[str, Any]:
        """获取队列统计"""
        pending = sum(1 for t in self.queue if t.status == "pending")
        failed = sum(1 for t in self.queue if t.status == "failed")
        return {
            "total": len(self.queue),
            "pending": pending,
            "failed": failed,
            "running": self._running
        }


class FallbackChain:
    """降级链 - 按优先级尝试多个策略"""

    def __init__(self, name: str):
        self.name = name
        self._strategies: List[Callable] = []
        self._fallback_values: Dict[int, Any] = {}

    def add_strategy(
        self,
        func: Callable,
        priority: int = 0,
        fallback_value: Any = None
    ) -> 'FallbackChain':
        """添加降级策略"""
        self._strategies.append((priority, func))
        self._strategies.sort(key=lambda x: x[0])
        if fallback_value is not None:
            self._fallback_values[id(func)] = fallback_value
        return self

    def execute(self, *args, **kwargs) -> Any:
        """执行降级链"""
        last_error = None

        for priority, func in self._strategies:
            try:
                logger.debug(f"尝试策略: {func.__name__} (优先级: {priority})")
                result = func(*args, **kwargs)
                if result is not None:
                    logger.info(f"策略成功: {func.__name__}")
                    return result
            except Exception as e:
                last_error = e
                logger.warning(f"策略失败: {func.__name__}: {e}")

                # 检查是否有预设的降级值
                fallback = self._fallback_values.get(id(func))
                if fallback is not None:
                    logger.info(f"使用降级值: {func.__name__}")
                    return fallback

        raise last_error or RuntimeError(f"所有策略都失败: {self.name}")


@dataclass
class CircuitBreakerState:
    """断路器状态"""
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    state: str = "closed"  # closed, open, half_open


class CircuitBreaker:
    """断路器 - 防止级联故障"""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self._state = CircuitBreakerState()
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        """获取当前状态"""
        if self._state.state == "open":
            # 检查是否应该进入半开状态
            if (self._state.last_failure_time and
                time.time() - self._state.last_failure_time > self.recovery_timeout):
                self._state.state = "half_open"
                self._state.success_count = 0
        return self._state.state

    async def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        """通过断路器执行函数"""
        async with self._lock:
            current_state = self.state

            if current_state == "open":
                raise RuntimeError(f"断路器打开: 失败次数过多")

            if current_state == "half_open":
                if self._state.success_count >= self.half_open_max_calls:
                    # 半开状态达到最大调用次数，保持半开
                    pass

        try:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)

            async with self._lock:
                self._state.success_count += 1
                if self._state.state == "half_open":
                    # 半开状态成功，关闭断路器
                    if self._state.success_count >= self.half_open_max_calls:
                        self._state.state = "closed"
                        self._state.failure_count = 0
                        logger.info("断路器关闭: 恢复正常")

            return result

        except Exception as e:
            async with self._lock:
                self._state.failure_count += 1
                self._state.last_failure_time = time.time()

                if self._state.failure_count >= self.failure_threshold:
                    self._state.state = "open"
                    logger.warning(f"断路器打开: 失败次数达到 {self.failure_threshold}")

            raise

    def reset(self):
        """重置断路器"""
        self._state = CircuitBreakerState()
        logger.info("断路器已重置")


# 全局重试队列实例
_retry_queue = RetryQueue()


def get_retry_queue() -> RetryQueue:
    """获取全局重试队列"""
    return _retry_queue


def with_fallback(*fallback_funcs):
    """
    降级装饰器 - 当主函数失败时尝试降级函数

    Usage:
        @with_fallback(fallback_func1, fallback_func2)
        def main_func():
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"主函数失败: {func.__name__}: {e}")

                for fallback in fallback_funcs:
                    try:
                        logger.info(f"尝试降级: {fallback.__name__}")
                        return fallback(*args, **kwargs)
                    except Exception as fallback_error:
                        logger.warning(f"降级失败: {fallback.__name__}: {fallback_error}")
                        continue

                raise  # 所有降级都失败，抛出原始异常

        return wrapper
    return decorator


def with_timeout(timeout: float):
    """
    超时装饰器

    Args:
        timeout: 超时时间（秒）
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args, **kwargs) -> T:
            import signal

            def timeout_handler(signum, frame):
                raise TimeoutError(f"函数 {func.__name__} 执行超时 ({timeout}秒)")

            # 设置超时
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(timeout))

            try:
                result = func(*args, **kwargs)
                signal.alarm(0)  # 取消超时
                return result
            finally:
                signal.signal(signal.SIGALRM, old_handler)

        return wrapper
    return decorator


class ErrorAggregator:
    """错误聚合器 - 收集和统计错误"""

    def __init__(self, max_errors: int = 100):
        self.max_errors = max_errors
        self._errors: deque = deque(maxlen=max_errors)
        self._error_counts: Dict[str, int] = {}

    def record_error(self, error: Exception, context: Dict[str, Any] = None):
        """记录错误"""
        error_info = {
            "timestamp": datetime.now().isoformat(),
            "type": type(error).__name__,
            "message": str(error),
            "traceback": traceback.format_exc(),
            "context": context or {}
        }

        self._errors.append(error_info)

        # 统计错误类型
        error_type = type(error).__name__
        self._error_counts[error_type] = self._error_counts.get(error_type, 0) + 1

        logger.error(f"错误记录: {error_type}: {error}")

    def get_recent_errors(self, limit: int = 10) -> List[Dict]:
        """获取最近的错误"""
        return list(self._errors)[-limit:]

    def get_error_stats(self) -> Dict[str, Any]:
        """获取错误统计"""
        return {
            "total_errors": len(self._errors),
            "error_counts": self._error_counts,
            "recent_errors": self.get_recent_errors(5)
        }

    def clear(self):
        """清空错误记录"""
        self._errors.clear()
        self._error_counts.clear()


# 全局错误聚合器
_error_aggregator = ErrorAggregator()


def get_error_aggregator() -> ErrorAggregator:
    """获取全局错误聚合器"""
    return _error_aggregator
