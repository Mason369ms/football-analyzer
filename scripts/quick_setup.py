#!/usr/bin/env python3
"""快速设置 LLM 配置"""
import sqlite3
import sys
from pathlib import Path

def quick_setup(api_key: str = None, base_url: str = None, model: str = None):
    """快速设置 LLM 配置"""

    db_path = Path("data/users/default/history.sqlite3")

    if not db_path.exists():
        print("❌ 数据库文件不存在")
        print("请先启动仪表盘: python -m football_sim.cli dashboard")
        return False

    # 默认配置
    default_config = {
        'llm_provider': 'openai',
        'llm_base_url': 'https://token-plan-cn.xiaomimimo.com/v1',
        'llm_model': 'mimo-v2.5-pro',
    }

    # 如果提供了参数，使用提供的值
    config = default_config.copy()
    if base_url:
        config['llm_base_url'] = base_url.rstrip('/')
    if model:
        config['llm_model'] = model.strip()

    if not api_key:
        print("❌ 必须提供 API Key")
        print("用法: python scripts/quick_setup.py YOUR_API_KEY")
        print("或: python scripts/quick_setup.py --key YOUR_API_KEY --model MODEL_NAME")
        return False

    config['llm_api_key'] = api_key.strip()

    # 保存到数据库
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # 确保表存在
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dashboard_config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # 更新或插入配置
        for key, value in config.items():
            cursor.execute(
                "INSERT OR REPLACE INTO dashboard_config (key, value) VALUES (?, ?)",
                (key, value)
            )

        conn.commit()
        conn.close()

        print("✅ LLM 配置已保存!")
        print()
        print("配置详情:")
        print(f"  Provider: {config['llm_provider']}")
        print(f"  Base URL: {config['llm_base_url']}")
        print(f"  Model: {config['llm_model']}")
        print(f"  API Key: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else ''}")
        print()
        print("现在可以测试:")
        print("  PYTHONPATH='src' python scripts/test_llm_analysis.py")

        return True

    except Exception as e:
        print(f"❌ 保存失败: {e}")
        return False


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='快速设置 LLM 配置')
    parser.add_argument('api_key', nargs='?', help='API Key')
    parser.add_argument('--key', '-k', help='API Key')
    parser.add_argument('--url', '-u', help='Base URL')
    parser.add_argument('--model', '-m', help='Model name')

    args = parser.parse_args()

    api_key = args.api_key or args.key

    if not api_key:
        print("请提供 API Key:")
        print("  python scripts/quick_setup.py YOUR_API_KEY")
        print()
        print("或使用选项:")
        print("  python scripts/quick_setup.py --key YOUR_API_KEY --model MODEL_NAME")
        sys.exit(1)

    success = quick_setup(
        api_key=api_key,
        base_url=args.url,
        model=args.model
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
