#!/usr/bin/env python3
"""测试 LLM 分析功能"""
import sys
from pathlib import Path

# 添加源码路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from football_sim.history_db import load_dashboard_config
from football_sim.analysis.llm_analyzer import call_llm

def test_llm_analysis():
    """测试 LLM 分析功能"""

    # 加载配置
    db_path = Path("data/users/default/history.sqlite3")
    if not db_path.exists():
        print("❌ 配置数据库不存在")
        return

    config = load_dashboard_config(db_path)

    print("📋 测试 LLM API 调用...")
    print(f"   Base URL: {config.get('llm_base_url')}")
    print(f"   Model: {config.get('llm_model')}")
    print()

    # 简单的测试 prompt
    system_prompt = "你是一个 AI 助手。"
    user_prompt = "请用一句话介绍足球比赛的越位规则。"

    try:
        print("🚀 发送测试请求...")
        result = call_llm(system_prompt, user_prompt, config, max_tokens=200)

        print("✅ LLM 调用成功!")
        print()
        print("📝 模型响应:")
        print("-" * 60)
        print(result)
        print("-" * 60)
        print()
        print("💡 现在可以尝试分析实际比赛:")
        print("   PYTHONPATH='src' python -m football_sim.cli analyze --date 2026-06-01")

    except ValueError as e:
        print(f"❌ LLM 调用失败: {e}")
        print()
        print("可能的原因:")
        print("1. 模型名称不正确")
        print("2. API Key 无效或额度不足")
        print("3. 请求参数不被支持")
        print()
        print("建议:")
        print("- 检查 API 提供商的文档")
        print("- 确认模型名称是否正确 (如 mimo-v2.5-pro)")
        print("- 验证 API Key 是否有效")
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_llm_analysis()
