#!/usr/bin/env python3
"""LLM API 诊断脚本 - 测试 API 连接和配置"""
import sys
from pathlib import Path

# 添加源码路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import httpx
import json

def diagnose_llm_config():
    """诊断 LLM 配置问题"""

    # 从数据库读取配置 - 尝试多个可能的路径
    config = {}
    db_paths = [
        Path("data/app_football.sqlite3"),
        Path("data/users/default/history.sqlite3"),
        Path("data/users/admin/history.sqlite3"),
    ]

    print("🔍 查找 LLM 配置...")
    for db_path in db_paths:
        if db_path.exists():
            print(f"   检查: {db_path}")
            try:
                from football_sim.history_db import load_dashboard_config
                config = load_dashboard_config(db_path)
                if config.get("llm_base_url"):
                    print(f"   ✅ 在 {db_path} 中找到配置")
                    break
            except Exception as e:
                print(f"   ⚠️ 读取失败: {e}")
                continue

    if not config.get("llm_base_url"):
        print("\n❌ 未找到 LLM 配置")
        print("   请在仪表盘的「AI 配置」页面设置:")
        print("   1. 启动仪表盘: python -m football_sim.cli dashboard")
        print("   2. 访问 http://127.0.0.1:8766")
        print("   3. 点击「AI 配置」填写 LLM API 信息")
        print("   4. 点击「保存配置」")
        return

    print("\n📋 当前 LLM 配置:")
    print(f"   Base URL: {config.get('llm_base_url', '未设置')}")
    print(f"   Model: {config.get('llm_model', '未设置')}")
    print(f"   API Key: {'已设置' if config.get('llm_api_key') else '未设置'}")
    print()

    base_url = config.get("llm_base_url", "").strip().rstrip("/")
    model = config.get("llm_model", "").strip()
    api_key = config.get("llm_api_key", "").strip()

    if not base_url or not model:
        print("❌ 配置不完整: base_url 和 model 不能为空")
        return

    # 测试 1: 检查 URL 格式
    print("🔍 测试 1: URL 格式检查")
    if not base_url.startswith("http"):
        print(f"   ❌ URL 格式错误: {base_url}")
        print("   应该以 http:// 或 https:// 开头")
        return
    print(f"   ✅ URL 格式正确: {base_url}")
    print()

    # 测试 2: 测试 API 连接
    print("🔍 测试 2: API 连接测试")
    url = f"{base_url}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    # 先发送一个最小的请求测试连接
    test_payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 10,
    }

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(url, json=test_payload, headers=headers)
            print(f"   HTTP 状态码: {resp.status_code}")

            if resp.status_code == 200:
                print("   ✅ API 连接成功!")
                data = resp.json()
                if "choices" in data and len(data["choices"]) > 0:
                    print(f"   模型响应: {data['choices'][0]['message']['content'][:100]}")
            elif resp.status_code == 400:
                print("   ❌ 400 Bad Request - 请求格式错误")
                print(f"   响应内容: {resp.text}")
                print()
                print("   可能的原因:")
                print("   1. 模型名称错误 (当前: {})".format(model))
                print("   2. API 不支持某些参数 (temperature, max_tokens 等)")
                print("   3. 请求格式与 API 不兼容")

                # 尝试不带 temperature 参数
                print()
                print("   🔧 尝试修复: 移除 temperature 参数...")
                test_payload_simple = {
                    "model": model,
                    "messages": [{"role": "user", "content": "Hello"}],
                    "max_tokens": 10,
                }
                resp2 = client.post(url, json=test_payload_simple, headers=headers)
                if resp2.status_code == 200:
                    print("   ✅ 成功! 问题在于 temperature 参数")
                    print("   建议: 修改 llm_analyzer.py 移除 temperature 参数")
                else:
                    print(f"   ❌ 仍然失败: {resp2.status_code}")
                    print(f"   响应: {resp2.text}")

                    # 尝试更简单的请求
                    print()
                    print("   🔧 尝试修复: 使用最简请求格式...")
                    test_payload_minimal = {
                        "model": model,
                        "messages": [{"role": "user", "content": "Hi"}],
                    }
                    resp3 = client.post(url, json=test_payload_minimal, headers=headers)
                    if resp3.status_code == 200:
                        print("   ✅ 成功! 问题在于 max_tokens 或其他参数")
                    else:
                        print(f"   ❌ 仍然失败: {resp3.status_code}")
                        print(f"   响应: {resp3.text}")

            elif resp.status_code == 401:
                print("   ❌ 401 Unauthorized - API Key 错误")
                print("   请检查 API Key 是否正确")
            elif resp.status_code == 404:
                print("   ❌ 404 Not Found - API 端点不存在")
                print(f"   当前 URL: {url}")
                print("   请检查 Base URL 是否正确")
            elif resp.status_code == 429:
                print("   ❌ 429 Too Many Requests - 请求过于频繁")
                print("   请稍后再试")
            else:
                print(f"   ❌ 请求失败: {resp.status_code}")
                print(f"   响应: {resp.text}")

    except httpx.ConnectError:
        print("   ❌ 连接失败: 无法连接到 API 服务器")
        print("   请检查:")
        print("   1. Base URL 是否正确")
        print("   2. 网络连接是否正常")
        print("   3. API 服务器是否可访问")
    except httpx.TimeoutException:
        print("   ❌ 连接超时: API 服务器响应超时")
        print("   请检查网络连接或稍后再试")
    except Exception as e:
        print(f"   ❌ 请求异常: {e}")

    print()
    print("=" * 60)
    print("💡 常见解决方案:")
    print("1. 确认模型名称正确 (如 deepseek-chat, gpt-4 等)")
    print("2. 确认 Base URL 格式正确 (如 https://api.deepseek.com/v1)")
    print("3. 确认 API Key 有效且有足够额度")
    print("4. 如果使用第三方 API，可能需要调整请求参数")
    print("5. 查看 API 文档确认支持的参数和格式")


if __name__ == "__main__":
    diagnose_llm_config()
