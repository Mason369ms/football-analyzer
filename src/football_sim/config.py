"""配置管理模块 - 提供统一的配置管理"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings

from football_sim.logger import get_logger

logger = get_logger(__name__)


class DatabaseSettings(BaseSettings):
    """数据库配置"""
    path: Path = Field(
        default=Path("data/app_football.sqlite3"),
        description="主数据库路径"
    )
    pool_size: int = Field(default=5, description="连接池大小")
    journal_mode: str = Field(default="WAL", description="日志模式")
    cache_size: int = Field(default=4000, description="缓存大小 (KB)")

    class Config:
        env_prefix = "FOOTBALL_DB_"


class LLMSettings(BaseSettings):
    """LLM 配置"""
    provider: str = Field(default="", description="LLM 提供商")
    base_url: str = Field(default="", description="API 地址")
    model: str = Field(default="", description="模型名称")
    api_key: str = Field(default="", description="API 密钥")
    max_tokens: int = Field(default=8000, description="最大 token 数")
    temperature: float = Field(default=0.3, description="温度参数")
    timeout: int = Field(default=120, description="超时时间（秒）")

    class Config:
        env_prefix = "FOOTBALL_LLM_"


class ServerSettings(BaseSettings):
    """服务器配置"""
    host: str = Field(default="127.0.0.1", description="监听地址")
    port: int = Field(default=8766, description="监听端口")
    open_browser: bool = Field(default=True, description="是否自动打开浏览器")
    reload: bool = Field(default=False, description="是否启用热重载")

    class Config:
        env_prefix = "FOOTBALL_"


class AuthSettings(BaseSettings):
    """认证配置"""
    admin_user: str = Field(default="admin", description="管理员用户名")
    admin_password: str = Field(default="admin", description="管理员密码")
    session_ttl_days: int = Field(default=7, description="会话有效期（天）")
    password_iterations: int = Field(default=260000, description="密码哈希迭代次数")

    class Config:
        env_prefix = "FOOTBALL_ADMIN_"


class HTTPSettings(BaseSettings):
    """HTTP 客户端配置"""
    ssl_verify: bool = Field(default=True, description="是否验证 SSL 证书")
    retry_count: int = Field(default=3, description="重试次数")
    use_proxy: bool = Field(default=False, description="是否使用代理")
    timeout: int = Field(default=15, description="请求超时（秒）")

    class Config:
        env_prefix = "FOOTBALL_"


class CacheSettings(BaseSettings):
    """缓存配置"""
    enabled: bool = Field(default=True, description="是否启用缓存")
    analysis_ttl: int = Field(default=300, description="分析缓存 TTL（秒）")
    match_ttl: int = Field(default=600, description="比赛缓存 TTL（秒）")
    odds_ttl: int = Field(default=180, description="赔率缓存 TTL（秒）")
    max_size: int = Field(default=1000, description="最大缓存条目数")

    class Config:
        env_prefix = "FOOTBALL_CACHE_"


class LoggingSettings(BaseSettings):
    """日志配置"""
    level: str = Field(default="INFO", description="日志级别")
    json_format: bool = Field(default=False, description="是否使用 JSON 格式")
    log_file: Optional[Path] = Field(default=None, description="日志文件路径")

    @validator('level')
    def validate_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'日志级别必须是 {valid_levels} 之一')
        return v.upper()

    class Config:
        env_prefix = "FOOTBALL_LOG_"


class BackupSettings(BaseSettings):
    """备份配置"""
    enabled: bool = Field(default=True, description="是否启用自动备份")
    interval_hours: int = Field(default=24, description="备份间隔（小时）")
    backup_time: str = Field(default="03:00", description="备份时间")
    max_backups: int = Field(default=30, description="最大备份数量")
    compress: bool = Field(default=True, description="是否压缩备份")

    class Config:
        env_prefix = "FOOTBALL_BACKUP_"


class MonitoringSettings(BaseSettings):
    """监控配置"""
    enabled: bool = Field(default=True, description="是否启用监控")
    metrics_port: int = Field(default=9090, description="Metrics 端口")
    sentry_dsn: str = Field(default="", description="Sentry DSN")

    class Config:
        env_prefix = "FOOTBALL_MONITOR_"


class AppSettings(BaseSettings):
    """应用总配置"""
    # 子配置
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    http: HTTPSettings = Field(default_factory=HTTPSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    backup: BackupSettings = Field(default_factory=BackupSettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)

    # 全局配置
    data_dir: Path = Field(default=Path("data"), description="数据目录")
    reports_dir: Path = Field(default=Path("reports"), description="报告目录")
    debug: bool = Field(default=False, description="调试模式")

    class Config:
        env_prefix = "FOOTBALL_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def update_from_env(self):
        """从环境变量更新配置"""
        # Pydantic Settings 会自动从环境变量加载
        # 这个方法用于显式触发重新加载
        for field_name, field_info in self.__fields__.items():
            env_var = f"{self.Config.env_prefix}{field_name.upper()}"
            if env_var in os.environ:
                value = os.environ[env_var]
                setattr(self, field_name, value)
                logger.debug(f"配置更新: {field_name} = {value}")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（隐藏敏感信息）"""
        data = self.dict()

        # 隐藏 API Key
        if 'llm' in data and 'api_key' in data['llm']:
            key = data['llm']['api_key']
            if key and len(key) > 8:
                data['llm']['api_key'] = f"{key[:4]}...{key[-4:]}"

        # 隐藏密码
        if 'auth' in data and 'admin_password' in data['auth']:
            data['auth']['admin_password'] = "***"

        return data


# 全局配置实例
_settings: Optional[AppSettings] = None


def get_settings() -> AppSettings:
    """获取全局配置实例"""
    global _settings
    if _settings is None:
        _settings = AppSettings()
        logger.info("配置初始化完成")
    return _settings


def reload_settings() -> AppSettings:
    """重新加载配置"""
    global _settings
    _settings = None
    return get_settings()


def get_database_path() -> Path:
    """获取数据库路径"""
    settings = get_settings()
    db_path = settings.data_dir / "app_football.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def get_user_database_path(username: str) -> Path:
    """获取用户数据库路径"""
    settings = get_settings()
    db_path = settings.data_dir / "users" / username / "history.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def get_matches_dir() -> Path:
    """获取比赛数据目录"""
    settings = get_settings()
    matches_dir = settings.data_dir / "matches"
    matches_dir.mkdir(parents=True, exist_ok=True)
    return matches_dir


def get_reports_dir() -> Path:
    """获取报告目录"""
    settings = get_settings()
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    return settings.reports_dir


# 配置验证
def validate_config() -> List[str]:
    """验证配置，返回警告信息"""
    warnings = []
    settings = get_settings()

    # 检查 LLM 配置
    if not settings.llm.base_url:
        warnings.append("未配置 LLM API 地址，分析功能将不可用")
    elif not settings.llm.api_key:
        warnings.append("未配置 LLM API Key，分析功能将不可用")

    # 检查数据库路径
    db_path = get_database_path()
    if not db_path.parent.exists():
        warnings.append(f"数据库目录不存在: {db_path.parent}")

    # 检查安全配置
    if settings.auth.admin_password == "admin":
        warnings.append("使用默认管理员密码，请尽快修改")

    if not settings.http.ssl_verify:
        warnings.append("SSL 验证已禁用，存在安全风险")

    return warnings


# 初始化配置
def init_config():
    """初始化配置"""
    settings = get_settings()

    # 创建必要的目录
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "users").mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "matches").mkdir(parents=True, exist_ok=True)

    # 验证配置
    warnings = validate_config()
    for warning in warnings:
        logger.warning(f"配置警告: {warning}")

    logger.info("配置初始化完成")
    return settings


# 导出常用配置
__all__ = [
    'AppSettings',
    'get_settings',
    'reload_settings',
    'get_database_path',
    'get_user_database_path',
    'get_matches_dir',
    'get_reports_dir',
    'validate_config',
    'init_config',
]
