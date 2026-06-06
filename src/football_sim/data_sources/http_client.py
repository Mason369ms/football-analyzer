"""HTTP 客户端工具模块，提供 SSL 容错和重试机制。"""

import os
import random
import ssl
import time
from typing import Optional
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.util.ssl_ import create_urllib3_context


# 环境变量配置
SSL_VERIFY = os.environ.get("FOOTBALL_SSL_VERIFY", "true").lower() != "false"
RETRY_COUNT = int(os.environ.get("FOOTBALL_RETRY_COUNT", "3"))
# 默认禁用代理（可通过环境变量覆盖）
USE_PROXY = os.environ.get("FOOTBALL_USE_PROXY", "false").lower() == "true"


class SSLAdapter(HTTPAdapter):
    """自定义 SSL 适配器，支持 TLS 1.2/1.3 和证书跳过。"""

    def __init__(self, *args, verify: bool = True, **kwargs):
        self._verify = verify
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.maximum_version = ssl.TLSVersion.TLSv1_3
        context.options |= ssl.OP_LEGACY_SERVER_CONNECT
        if not self._verify:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        kwargs["ssl_context"] = context
        return super().init_poolmanager(*args, **kwargs)


_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Android 10; Mobile; rv:68.0) Gecko/68.0 Firefox/68.0",
]


def get_random_user_agent() -> str:
    return random.choice(_USER_AGENTS)


def create_session(
    retries: int = RETRY_COUNT,
    verify: Optional[bool] = None,
    use_proxy: Optional[bool] = None,
) -> requests.Session:
    """创建带 SSL 容错和重试机制的 Session。

    Args:
        retries: 重试次数，默认从环境变量 FOOTBALL_RETRY_COUNT 读取
        verify: SSL 验证开关，默认从环境变量 FOOTBALL_SSL_VERIFY 读取
        use_proxy: 是否使用代理，默认从环境变量 FOOTBALL_USE_PROXY 读取（默认禁用）
    """
    if verify is None:
        verify = SSL_VERIFY
    if use_proxy is None:
        use_proxy = USE_PROXY

    session = requests.Session()
    session.verify = verify

    # 禁用代理（默认行为，避免代理干扰 SSL）
    if not use_proxy:
        session.trust_env = False
        session.proxies = {"http": None, "https": None}

    # 配置重试策略
    retry_strategy = Retry(
        total=retries,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )

    # 使用自定义 SSL 适配器
    adapter = SSLAdapter(max_retries=retry_strategy, verify=verify)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


def safe_get(url: str, timeout: int = 15, headers: Optional[dict] = None) -> requests.Response:
    """带重试的安全 GET 请求。

    遇到 SSL 错误时自动尝试禁用验证后重试。
    """
    if headers is None:
        headers = {}
    headers.setdefault("User-Agent", get_random_user_agent())

    session = create_session()
    try:
        return session.get(url, timeout=timeout, headers=headers)
    except (requests.exceptions.SSLError, requests.exceptions.ConnectionError) as e:
        session.close()
        # SSL 或连接错误时尝试禁用验证
        session = create_session(verify=False)
        for attempt in range(3):
            try:
                time.sleep(1 * (attempt + 1))
                return session.get(url, timeout=timeout, headers=headers)
            except (requests.exceptions.SSLError, requests.exceptions.ConnectionError):
                if attempt == 2:
                    raise
                continue
        return session.get(url, timeout=timeout, headers=headers)
    finally:
        session.close()
