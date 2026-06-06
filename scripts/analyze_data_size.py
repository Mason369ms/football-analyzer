#!/usr/bin/env python3
"""测试完整数据传递并生成统计报告"""
import sys
from pathlib import Path

# 添加源码路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import json
from football_sim.data_sources.match_store import load_match_data, list_match_dirs
from football_sim.prompts.match_analysis import build_user_prompt

def analyze_data_size(match_dir: Path, use_full_data: bool = True):
    """分析单场比赛的数据大小"""

    match_data = load_match_data(match_dir)
    meta = match_data.get("赛事信息", {})
    match_name = f"{meta.get('home_team', '?')} vs {meta.get('away_team', '?')}"

    print(f"\n{'='*60}")
    print(f"📊 赛事: {match_name}")
    print(f"{'='*60}")

    # 统计各个数据字段的大小
    data_fields = {
        "赛事信息": "赛事信息",
        "历史交锋": "两队比赛历史交锋数据",
        "近期战绩": "主客队近期比赛数据",
        "队员情报": "主客队队员、情报信息数据",
        "阵容天气": "比赛场地、天气、主客队队员上场信息(身价、位置)数据",
        "联赛积分": "联赛积分排名、近期状态(进球数、失球数)、未来赛事数据",
        "赔率变化": "赔率变化数据",
    }

    total_raw_size = 0
    field_sizes = {}

    for label, key in data_fields.items():
        data = match_data.get(key, {})
        if data:
            json_str = json.dumps(data, ensure_ascii=False, indent=2)
            size = len(json_str)
            total_raw_size += size
            field_sizes[label] = size
            print(f"  {label:10}: {size:>8,} 字符 ({size/1024:>6.1f} KB)")
        else:
            print(f"  {label:10}: {'无数据':>8}")

    print(f"  {'─'*40}")
    print(f"  {'总计':10}: {total_raw_size:>8,} 字符 ({total_raw_size/1024:>6.1f} KB)")

    # 构建 prompt 并统计实际传递的数据量
    user_prompt = build_user_prompt(match_data, use_full_data=use_full_data)
    prompt_size = len(user_prompt)

    # 计算 token 估算（粗略：中文约 1.5 字符/token，英文约 4 字符/token）
    # 这里使用保守估计：1 字符 ≈ 1 token
    estimated_tokens = prompt_size

    print(f"\n  📝 Prompt 大小: {prompt_size:,} 字符 (约 {estimated_tokens:,} tokens)")
    print(f"  📈 数据利用率: {prompt_size/total_raw_size*100:.1f}%")

    if use_full_data:
        print(f"  ✅ 模式: 完整数据传递")
    else:
        print(f"  ⚠️ 模式: 截断模式（限制 17,000 字符）")

    return {
        "match_name": match_name,
        "total_raw_size": total_raw_size,
        "prompt_size": prompt_size,
        "estimated_tokens": estimated_tokens,
        "field_sizes": field_sizes,
        "use_full_data": use_full_data,
    }


def main():
    """主函数"""

    # 指定日期目录
    date_dir = Path("data/matches/2026-06-04")

    if not date_dir.exists():
        print(f"❌ 数据目录不存在: {date_dir}")
        return

    match_dirs = list_match_dirs(date_dir)

    if not match_dirs:
        print(f"❌ 未找到赛事数据")
        return

    print(f"🏟️  发现 {len(match_dirs)} 场比赛")
    print(f"📅 日期: {date_dir.name}")

    # 统计所有比赛
    results_full = []
    results_truncated = []

    for match_dir in match_dirs[:3]:  # 只测试前 3 场
        result_full = analyze_data_size(match_dir, use_full_data=True)
        results_full.append(result_full)

        result_truncated = analyze_data_size(match_dir, use_full_data=False)
        results_truncated.append(result_truncated)

    # 汇总统计
    print(f"\n\n{'='*60}")
    print(f"📊 汇总统计（前 3 场比赛）")
    print(f"{'='*60}")

    total_raw = sum(r["total_raw_size"] for r in results_full)
    total_full = sum(r["prompt_size"] for r in results_full)
    total_truncated = sum(r["prompt_size"] for r in results_truncated)

    print(f"\n原始数据总量: {total_raw:>12,} 字符 ({total_raw/1024/1024:.2f} MB)")
    print(f"\n完整模式:")
    print(f"  Prompt 总量: {total_full:>12,} 字符 ({total_full/1024/1024:.2f} MB)")
    print(f"  数据利用率:  {total_full/total_raw*100:.1f}%")
    print(f"  估算 tokens: {total_full:>12,}")

    print(f"\n截断模式:")
    print(f"  Prompt 总量: {total_truncated:>12,} 字符 ({total_truncated/1024:.1f} KB)")
    print(f"  数据利用率:  {total_truncated/total_raw*100:.1f}%")
    print(f"  估算 tokens: {total_truncated:>12,}")

    print(f"\n💡 建议:")
    if total_full > 100000:
        print(f"  ⚠️  完整数据量较大（{total_full/1024:.0f} KB），请确保:")
        print(f"     1. LLM 模型支持足够的 context window（推荐 32K+ tokens）")
        print(f"     2. API 有足够的额度")
        print(f"     3. 网络连接稳定")
    else:
        print(f"  ✅ 数据量适中，可以使用完整模式获得更精准的分析")

    print(f"\n🔧 使用方式:")
    print(f"  # 完整数据模式（默认）")
    print(f"  python -m football_sim.cli analyze --date 2026-06-04")
    print(f"")
    print(f"  # 截断模式（适用于 token 受限的模型）")
    print(f"  python -m football_sim.cli analyze --date 2026-06-04 --truncated")


if __name__ == "__main__":
    main()
