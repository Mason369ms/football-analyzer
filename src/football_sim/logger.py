"""结构化日志模块 - 提供 JSON 格式的日志输出"""

import logging
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class JSONFormatter(logging.Formatter):
    """JSON 格式的日志格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # 添加异常信息
        if record.exc_info and record.exc_info[0] is not None:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }

        # 添加额外字段
        if hasattr(record, 'extra_data') and record.extra_data:
            log_data.update(record.extra_data)

        return json.dumps(log_data, ensure_ascii=False, default=str)


class ColoredFormatter(logging.Formatter):
    """带颜色的控制台日志格式化器"""

    COLORS = {
        'DEBUG': '\033[36m',    # 青色
        'INFO': '\033[32m',     # 绿色
        'WARNING': '\033[33m',  # 黄色
        'ERROR': '\033[31m',    # 红色
        'CRITICAL': '\033[35m', # 紫色
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        level = f"{color}{record.levelname:<8}{self.RESET}"
        name = f"\033[34m{record.name}\033[0m"
        message = record.getMessage()

        log_line = f"{timestamp} | {level} | {name} | {message}"

        if record.exc_info and record.exc_info[0] is not None:
            log_line += "\n" + self.formatException(record.exc_info)

        return log_line


def setup_logging(
    level: int = logging.INFO,
    json_format: bool = False,
    log_file: Optional[Path] = None
) -> None:
    """
    配置全局日志系统

    Args:
        level: 日志级别
        json_format: 是否使用 JSON 格式（生产环境推荐）
        log_file: 日志文件路径（可选）
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 清除现有的处理器
    root_logger.handlers = []

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    if json_format:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(ColoredFormatter())

    root_logger.addHandler(console_handler)

    # 文件处理器（可选）
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(str(log_file), encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)

    # 设置第三方库的日志级别
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的 logger

    Args:
        name: logger 名称，通常使用 __name__

    Returns:
        配置好的 logger 实例
    """
    return logging.getLogger(name)


class LoggerMixin:
    """日志混入类，为类提供 logger 属性"""

    @property
    def logger(self) -> logging.Logger:
        return get_logger(self.__class__.__name__)


def log_function_call(logger: Optional[logging.Logger] = None):
    """
    函数调用日志装饰器

    Args:
        logger: 可选的 logger 实例
    """
    def decorator(func):
        import functools

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            _logger = logger or get_logger(func.__module__)
            func_name = func.__name__

            _logger.debug(f"调用函数 {func_name}", extra={
                'extra_data': {
                    'function': func_name,
                    'args': str(args)[:200],
                    'kwargs': str(kwargs)[:200]
                }
            })

            try:
                result = func(*args, **kwargs)
                _logger.debug(f"函数 {func_name} 执行成功")
                return result
            except Exception as e:
                _logger.error(f"函数 {func_name} 执行失败: {e}", exc_info=True)
                raise

        return wrapper
    return decorator


# 初始化默认日志配置
setup_logging(level=logging.INFO, json_format=False)
