#!/usr/bin/env python3
"""验证完整数据传递给 LLM"""
import sys
from pathlib import Path

# 添加源码路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import json
from football_sim.data_sources.match_store import load_match_data
from football_sim.prompts.match_analysis import build_user_prompt

def verify_full_data_passing():
    """验证完整数据传递"""

    # 选择一场比赛
    match_dir = Path("data/matches/2026-06-04/周四201_国际友谊_斯洛文尼亚_vs_塞浦路斯")

    if not match_dir.exists():
        print("❌ 比赛数据目录不存在")
        return

    print("="*70)
    print("🔍 验证完整数据传递")
    print("="*70)

    # 1. 加载原始数据
    match_data = load_match_data(match_dir)

    print("\n📁 原始数据文件:")
    for key in match_data.keys():
        data = match_data[key]
        size = len(json.dumps(data, ensure_ascii=False, indent=2))
        print(f"  ✓ {key}: {size:,} 字符")

    # 2. 构建完整模式的 prompt
    prompt_full = build_user_prompt(match_data, use_full_data=True)

    # 3. 构建截断模式的 prompt
    prompt_truncated = build_user_prompt(match_data, use_full_data=False)

    print(f"\n📊 Prompt 大小对比:")
    print(f"  完整模式: {len(prompt_full):>10,} 字符 ({len(prompt_full)/1024:.1f} KB)")
    print(f"  截断模式: {len(prompt_truncated):>10,} 字符 ({len(prompt_truncated)/1024:.1f} KB)")
    print(f"  数据量比: {len(prompt_full)/len(prompt_truncated):.1f}x")

    # 4. 验证各个数据字段是否完整包含
    print(f"\n✅ 数据完整性验证:")

    data_fields = {
        "历史交锋": "两队比赛历史交锋数据",
        "近期战绩": "主客队近期比赛数据",
        "队员情报": "主客队队员、情报信息数据",
        "阵容天气": "比赛场地、天气、主客队队员上场信息(身价、位置)数据",
        "联赛积分": "联赛积分排名、近期状态(进球数、失球数)、未来赛事数据",
        "赔率变化": "赔率变化数据",
    }

    all_passed = True

    for label, key in data_fields.items():
        original_data = match_data.get(key, {})
        if not original_data:
            print(f"  ⚪ {label}: 原始数据为空")
            continue

        # 将原始数据序列化为 JSON（使用和 build_user_prompt 相同的格式）
        original_json = json.dumps(original_data, ensure_ascii=False, separators=(',', ':'))
        original_size = len(original_json)

        # 计算在 prompt 中的数据大小（从 section header 到下一个 section）
        section_start = f"## {label}"
        if label == "历史交锋":
            section_start = "## 历史交锋数据"
        elif label == "近期战绩":
            section_start = "## 近期比赛数据"
        elif label == "队员情报":
            section_start = "## 队员情报信息"
        elif label == "阵容天气":
            section_start = "## 阵容/天气/场地信息"
        elif label == "联赛积分":
            section_start = "## 联赛积分与状态"
        elif label == "赔率变化":
            section_start = "## 赔率变化数据（各公司）"

        # 查找 section 在 prompt 中的位置
        start_idx = prompt_full.find(section_start)
        if start_idx == -1:
            print(f"  ✗ {label}: 未在 prompt 中找到")
            all_passed = False
            continue

        # 查找下一个 section 的位置
        next_section_idx = prompt_full.find("\n## ", start_idx + len(section_start))
        if next_section_idx == -1:
            next_section_idx = prompt_full.find("\n【", start_idx + len(section_start))
        if next_section_idx == -1:
            next_section_idx = len(prompt_full)

        # 提取实际包含的数据
        included_data = prompt_full[start_idx:next_section_idx]
        included_size = len(included_data)

        # 计算数据保留率
        # 去掉 section header 的大小
        header_size = len(section_start) + 50  # 估算 header + 换行符
        data_only_size = max(0, included_size - header_size)
        retention_rate = data_only_size / original_size * 100 if original_size > 0 else 0

        if retention_rate >= 90:
            print(f"  ✓ {label}: {retention_rate:.1f}% 保留 ({data_only_size:,}/{original_size:,} 字符)")
        elif retention_rate >= 50:
            print(f"  ⚠️ {label}: {retention_rate:.1f}% 保留 ({data_only_size:,}/{original_size:,} 字符)")
            all_passed = False
        else:
            print(f"  ✗ {label}: {retention_rate:.1f}% 保留 ({data_only_size:,}/{original_size:,} 字符)")
            all_passed = False

    print(f"\n{'='*70}")

    if all_passed:
        print("✅ 验证通过：所有数据字段都完整传递给 LLM")
    else:
        print("⚠️  部分数据可能被截断，请检查配置")

    # 5. 保存 prompt 样本供检查
    output_file = Path("test_output_full_prompt.txt")
    output_file.write_text(prompt_full[:5000], encoding="utf-8")  # 只保存前 5000 字符
    print(f"\n💾 Prompt 样本已保存到: {output_file}")
    print(f"   (前 5000 字符，完整大小: {len(prompt_full):,} 字符)")

    # 6. 显示 prompt 结构
    print(f"\n📋 Prompt 结构预览:")
    lines = prompt_full.split('\n')
    section_headers = [line for line in lines if line.startswith('##') or line.startswith('【')]
    for header in section_headers[:15]:
        print(f"  {header}")
    if len(section_headers) > 15:
        print(f"  ... 还有 {len(section_headers) - 15} 个章节")

    print(f"\n💡 使用方式:")
    print(f"  # 默认使用完整数据模式（推荐）")
    print(f"  python -m football_sim.cli analyze --date 2026-06-04")
    print(f"")
    print(f"  # 如果 token 受限，使用截断模式")
    print(f"  python -m football_sim.cli analyze --date 2026-06-04 --truncated")


if __name__ == "__main__":
    verify_full_data_passing()
