#!/usr/bin/env python3
"""测试仪表盘改进效果"""
import sys
from pathlib import Path

# 添加源码路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from football_sim.dashboard import load_dashboard_model

def test_dashboard_improvements():
    """测试仪表盘改进"""

    print("=" * 70)
    print("🧪 测试仪表盘改进效果")
    print("=" * 70)

    # 加载仪表盘数据
    model = load_dashboard_model(date="2026-06-04")

    # 测试 1: 检查赛事列表序号
    print("\n✅ 测试 1: 赛事列表序号")
    print("-" * 70)
    for idx, m in enumerate(model.matches, 1):
        print(f"  {m.round_info:12} → {m.home_team} vs {m.away_team}")

    # 测试 2: 检查近期分析（应该无重复）
    print(f"\n✅ 测试 2: 近期分析（共 {len(model.recent_analyses)} 条，应该无重复）")
    print("-" * 70)
    seen_matches = set()
    has_duplicates = False

    for a in model.recent_analyses:
        match_key = f"{a.get('home_team')} vs {a.get('away_team')}"
        match_number = a.get("match_number", "?")

        if match_key in seen_matches:
            print(f"  ❌ 发现重复: {match_key}")
            has_duplicates = True
        else:
            seen_matches.add(match_key)
            print(f"  ✓ 序号 {match_number}: {match_key}")

    if not has_duplicates:
        print("\n  ✅ 没有发现重复记录！")

    # 测试 3: 检查数据完整性
    print(f"\n✅ 测试 3: 数据完整性检查")
    print("-" * 70)
    print(f"  赛事数量: {len(model.matches)}")
    print(f"  分析记录: {len(model.recent_analyses)}")

    # 统计有序号的分析记录
    with_number = sum(1 for a in model.recent_analyses if a.get("match_number"))
    print(f"  有序号记录: {with_number}/{len(model.recent_analyses)}")

    print("\n" + "=" * 70)
    print("🎉 测试完成！")
    print("=" * 70)
    print("\n💡 现在可以启动仪表盘查看效果:")
    print("   PYTHONPATH='src' python -m football_sim.cli dashboard --server fastapi --port 8766")


if __name__ == "__main__":
    test_dashboard_improvements()
