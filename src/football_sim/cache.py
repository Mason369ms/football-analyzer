"""缓存模块 - 提供内存缓存和缓存失效策略"""

import hashlib
import json
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar

from football_sim.logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: float
    ttl: int  # 秒
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)

    @property
    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl

    def touch(self):
        """更新访问时间"""
        self.access_count += 1
        self.last_accessed = time.time()


class TTLCache:
    """带 TTL（生存时间）的 LRU 缓存"""

    def __init__(self, maxsize: int = 1000, ttl: int = 300):
        """
        初始化缓存

        Args:
            maxsize: 最大缓存条目数
            ttl: 默认 TTL（秒）
        """
        self.maxsize = maxsize
        self.default_ttl = ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired:
                del self._cache[key]
                self._misses += 1
                return None

            # 移到末尾（LRU）
            self._cache.move_to_end(key)
            entry.touch()
            self._hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存值"""
        with self._lock:
            # 如果 key 已存在，先删除
            if key in self._cache:
                del self._cache[key]

            # 检查是否需要淘汰
            while len(self._cache) >= self.maxsize:
                self._cache.popitem(last=False)  # 淘汰最久未使用的

            entry = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                ttl=ttl or self.default_ttl
            )
            self._cache[key] = entry
            logger.debug(f"缓存设置: {key[:50]}...")

    def delete(self, key: str) -> bool:
        """删除缓存条目"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> int:
        """清空缓存"""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            logger.info(f"缓存已清空: {count} 条")
            return count

    def invalidate_by_prefix(self, prefix: str) -> int:
        """按前缀失效缓存"""
        with self._lock:
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(prefix)]
            for key in keys_to_remove:
                del self._cache[key]
            if keys_to_remove:
                logger.debug(f"缓存失效: {len(keys_to_remove)} 条 (前缀: {prefix})")
            return len(keys_to_remove)

    def cleanup_expired(self) -> int:
        """清理过期条目"""
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired
            ]
            for key in expired_keys:
                del self._cache[key]
            if expired_keys:
                logger.debug(f"清理过期缓存: {len(expired_keys)} 条")
            return len(expired_keys)

    @property
    def size(self) -> int:
        """当前缓存大小"""
        return len(self._cache)

    @property
    def hit_rate(self) -> float:
        """缓存命中率"""
        total = self._hits + self._misses
        return (self._hits / total * 100) if total > 0 else 0.0

    @property
    def stats(self) -> Dict[str, Any]:
        """缓存统计信息"""
        return {
            "size": self.size,
            "maxsize": self.maxsize,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{self.hit_rate:.1f}%",
            "default_ttl": self.default_ttl
        }


# 全局缓存实例
_analysis_cache = TTLCache(maxsize=1000, ttl=300)  # 5 分钟
_match_cache = TTLCache(maxsize=500, ttl=600)  # 10 分钟
_config_cache = TTLCache(maxsize=100, ttl=900)  # 15 分钟
_odds_cache = TTLCache(maxsize=2000, ttl=180)  # 3 分钟


def get_analysis_cache() -> TTLCache:
    """获取分析缓存实例"""
    return _analysis_cache


def get_match_cache() -> TTLCache:
    """获取比赛缓存实例"""
    return _match_cache


def get_config_cache() -> TTLCache:
    """获取配置缓存实例"""
    return _config_cache


def get_odds_cache() -> TTLCache:
    """获取赔率缓存实例"""
    return _odds_cache


def generate_cache_key(*args, **kwargs) -> str:
    """生成缓存键"""
    key_parts = [str(arg) for arg in args]
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    key_str = "|".join(key_parts)

    # 如果 key 太长，使用 hash
    if len(key_str) > 200:
        return hashlib.md5(key_str.encode()).hexdigest()
    return key_str


def cached(
    cache: TTLCache,
    key_prefix: str = "",
    ttl: Optional[int] = None,
    key_func: Optional[Callable] = None
):
    """
    缓存装饰器

    Args:
        cache: 缓存实例
        key_prefix: 缓存键前缀
        ttl: 自定义 TTL（秒）
        key_func: 自定义缓存键生成函数
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # 生成缓存键
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = generate_cache_key(*args, **kwargs)

            if key_prefix:
                cache_key = f"{key_prefix}:{cache_key}"

            # 尝试从缓存获取
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"缓存命中: {cache_key[:50]}...")
                return cached_value

            # 执行函数
            result = func(*args, **kwargs)

            # 缓存结果
            if result is not None:  # 不缓存 None 值
                cache.set(cache_key, result, ttl)
                logger.debug(f"缓存设置: {cache_key[:50]}...")

            return result

        # 添加缓存管理方法
        wrapper.cache = cache
        wrapper.cache_key_prefix = key_prefix

        def invalidate(*args, **kwargs):
            """手动失效缓存"""
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = generate_cache_key(*args, **kwargs)

            if key_prefix:
                cache_key = f"{key_prefix}:{cache_key}"

            return cache.delete(cache_key)

        wrapper.invalidate = invalidate

        def invalidate_all():
            """失效所有前缀匹配的缓存"""
            if key_prefix:
                return cache.invalidate_by_prefix(key_prefix)
            return 0

        wrapper.invalidate_all = invalidate_all

        return wrapper
    return decorator


def invalidate_match_caches(match_id: str) -> Dict[str, int]:
    """
    使指定比赛的所有相关缓存失效

    Args:
        match_id: 比赛 ID

    Returns:
        各缓存失效的条目数
    """
    results = {
        "analysis": _analysis_cache.invalidate_by_prefix(match_id),
        "match": _match_cache.invalidate_by_prefix(match_id),
        "odds": _odds_cache.invalidate_by_prefix(match_id),
    }

    total = sum(results.values())
    if total > 0:
        logger.info(f"比赛缓存失效: {match_id}, 共 {total} 条")

    return results


def invalidate_all_caches() -> Dict[str, int]:
    """使所有缓存失效"""
    results = {
        "analysis": _analysis_cache.clear(),
        "match": _match_cache.clear(),
        "config": _config_cache.clear(),
        "odds": _odds_cache.clear(),
    }

    total = sum(results.values())
    logger.info(f"所有缓存已清空: 共 {total} 条")

    return results


def get_all_cache_stats() -> Dict[str, Any]:
    """获取所有缓存的统计信息"""
    return {
        "analysis": _analysis_cache.stats,
        "match": _match_cache.stats,
        "config": _config_cache.stats,
        "odds": _odds_cache.stats,
        "total_size": (
            _analysis_cache.size +
            _match_cache.size +
            _config_cache.size +
            _odds_cache.size
        )
    }


# 定期清理过期缓存
class CacheCleanupThread(threading.Thread):
    """缓存清理线程"""

    def __init__(self, interval: int = 60):
        super().__init__(daemon=True)
        self.interval = interval
        self._stop_event = threading.Event()

    def run(self):
        logger.info(f"缓存清理线程启动 (间隔: {self.interval}秒)")
        while not self._stop_event.is_set():
            try:
                self._cleanup_all()
            except Exception as e:
                logger.error(f"缓存清理失败: {e}")
            self._stop_event.wait(self.interval)

    def _cleanup_all(self):
        """清理所有缓存的过期条目"""
        total = 0
        total += _analysis_cache.cleanup_expired()
        total += _match_cache.cleanup_expired()
        total += _config_cache.cleanup_expired()
        total += _odds_cache.cleanup_expired()

        if total > 0:
            logger.debug(f"清理过期缓存: {total} 条")

    def stop(self):
        """停止清理线程"""
        self._stop_event.set()


# 全局清理线程实例
_cleanup_thread: Optional[CacheCleanupThread] = None


def start_cache_cleanup(interval: int = 60) -> None:
    """启动缓存清理线程"""
    global _cleanup_thread
    if _cleanup_thread is None or not _cleanup_thread.is_alive():
        _cleanup_thread = CacheCleanupThread(interval)
        _cleanup_thread.start()
        logger.info("缓存清理线程已启动")


def stop_cache_cleanup() -> None:
    """停止缓存清理线程"""
    global _cleanup_thread
    if _cleanup_thread and _cleanup_thread.is_alive():
        _cleanup_thread.stop()
        _cleanup_thread.join(timeout=5)
        logger.info("缓存清理线程已停止")
