#!/usr/bin/env python3
"""设置 LLM API Key"""
import sqlite3
import sys
from pathlib import Path

def set_api_key():
    """交互式设置 API Key"""

    db_path = Path("data/users/default/history.sqlite3")

    if not db_path.exists():
        print("❌ 数据库文件不存在，请先启动仪表盘")
        return

    print("=" * 60)
    print("🔧 设置 LLM API Key")
    print("=" * 60)
    print()
    print("当前配置:")
    print(f"  Base URL: https://token-plan-cn.xiaomimimo.com/v1")
    print(f"  Model: mimo-v2.5-pro")
    print()

    # 提示用户输入 API Key
    print("请输入你的 API Key:")
    print("(可以从 API 提供商的控制台获取)")
    print()

    api_key = input("API Key: ").strip()

    if not api_key:
        print("❌ API Key 不能为空")
        return

    print()
    print(f"即将保存 API Key: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else ''}")
    confirm = input("确认保存？(y/n): ").strip().lower()

    if confirm != 'y':
        print("已取消")
        return

    # 保存到数据库
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # 检查是否已存在
        cursor.execute("SELECT COUNT(*) FROM dashboard_config WHERE key = 'llm_api_key'")
        exists = cursor.fetchone()[0] > 0

        if exists:
            cursor.execute(
                "UPDATE dashboard_config SET value = ? WHERE key = 'llm_api_key'",
                (api_key,)
            )
        else:
            cursor.execute(
                "INSERT INTO dashboard_config (key, value) VALUES (?, ?)",
                ('llm_api_key', api_key)
            )

        conn.commit()
        conn.close()

        print()
        print("✅ API Key 已保存!")
        print()
        print("现在可以测试 LLM 调用:")
        print("  PYTHONPATH='src' python scripts/test_llm_analysis.py")

    except Exception as e:
        print(f"❌ 保存失败: {e}")


if __name__ == "__main__":
    set_api_key()
