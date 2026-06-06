#!/usr/bin/env python3
"""修复 LLM 配置 - 清理模型名称中的空格"""
import sqlite3
from pathlib import Path

def fix_llm_config():
    """修复 LLM 配置中的模型名称空格问题"""

    db_paths = [
        Path("data/users/default/history.sqlite3"),
        Path("data/users/admin/history.sqlite3"),
        Path("data/app_football.sqlite3"),
    ]

    for db_path in db_paths:
        if not db_path.exists():
            continue

        print(f"\n检查数据库: {db_path}")

        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # 读取当前配置
            cursor.execute("SELECT key, value FROM dashboard_config WHERE key LIKE 'llm_%'")
            rows = cursor.fetchall()

            if not rows:
                print("   未找到 LLM 配置")
                conn.close()
                continue

            print("   当前配置:")
            config = {}
            for key, value in rows:
                config[key] = value
                print(f"   {key}: {repr(value)}")

            # 修复模型名称
            if "llm_model" in config:
                old_model = config["llm_model"]
                new_model = old_model.strip()

                if old_model != new_model:
                    print(f"\n   🔧 修复模型名称:")
                    print(f"      旧值: {repr(old_model)}")
                    print(f"      新值: {repr(new_model)}")

                    cursor.execute(
                        "UPDATE dashboard_config SET value = ? WHERE key = 'llm_model'",
                        (new_model,)
                    )
                    conn.commit()
                    print("   ✅ 已修复!")
                else:
                    print("\n   ✅ 模型名称格式正确")

            # 同时检查 base_url
            if "llm_base_url" in config:
                old_url = config["llm_base_url"]
                new_url = old_url.strip().rstrip("/")

                if old_url != new_url:
                    print(f"\n   🔧 修复 Base URL:")
                    print(f"      旧值: {repr(old_url)}")
                    print(f"      新值: {repr(new_url)}")

                    cursor.execute(
                        "UPDATE dashboard_config SET value = ? WHERE key = 'llm_base_url'",
                        (new_url,)
                    )
                    conn.commit()
                    print("   ✅ 已修复!")

            conn.close()

        except Exception as e:
            print(f"   ❌ 处理失败: {e}")

    print("\n" + "=" * 60)
    print("💡 修复完成！请重新运行分析测试:")
    print("   PYTHONPATH='src' python -m football_sim.cli analyze --date 2026-06-01")


if __name__ == "__main__":
    fix_llm_config()
