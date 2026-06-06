#!/usr/bin/env python3
"""数据完整性评估报告"""
import json
from pathlib import Path
from typing import Dict, List, Any

def assess_data_completeness(match_dir: Path) -> Dict[str, Any]:
    """评估比赛数据的完整性"""

    assessment = {
        "match_dir": str(match_dir),
        "files": {},
        "completeness": {},
        "missing_critical": [],
        "missing_optional": [],
        "recommendations": [],
    }

    # 定义必须字段和可选字段
    critical_fields = {
        "赛事基本信息": {
            "file": "赛事信息.json",
            "required": ["match_id", "league", "home_team", "away_team", "match_time"],
        },
        "赔率数据": {
            "file": "赔率变化数据.json",
            "required": ["欧指", "亚盘", "大小球"],
            "note": "至少需要 3 家公司的赔率数据",
        },
        "历史交锋": {
            "file": "两队比赛历史交锋数据.json",
            "required": ["match_id", "home_team_name", "away_team_name", "home_team_score"],
            "note": "至少需要 3-5 场交锋记录",
        },
        "近期战绩": {
            "file": "主客队近期比赛数据.json",
            "required": ["home_history_match", "away_history_match"],
            "note": "主客队各至少 5-10 场近期比赛",
        },
    }

    optional_fields = {
        "阵容情报": {
            "file": "主客队队员、情报信息数据.json",
            "fields": ["player_injury", "wonderful_report"],
            "note": "伤停信息和赛事情报",
        },
        "场地天气": {
            "file": "比赛场地、天气、主客队队员上场信息(身价、位置)数据.json",
            "fields": ["stadium_cn_name", "weather", "temperature", "has_lineup"],
            "note": "球场、天气、阵容",
        },
        "联赛积分": {
            "file": "联赛积分排名、近期状态(进球数、失球数)、未来赛事数据.json",
            "fields": ["table_score_rank", "tech_state"],
            "note": "积分榜和技术统计",
        },
    }

    # 检查必须字段
    print("\n🔍 检查必须数据...")
    for category, config in critical_fields.items():
        file_path = match_dir / config["file"]

        if not file_path.exists():
            assessment["missing_critical"].append(f"{category}: 文件不存在 ({config['file']})")
            assessment["completeness"][category] = {"status": "❌ 缺失", "score": 0}
            continue

        with open(file_path, encoding='utf-8') as f:
            data = json.load(f)

        # 检查必需字段
        missing = []
        if isinstance(data, dict):
            for field in config["required"]:
                if field not in data:
                    missing.append(field)
        elif isinstance(data, list) and data:
            for field in config["required"]:
                if field not in data[0]:
                    missing.append(field)

        if missing:
            assessment["missing_critical"].append(f"{category}: 缺少字段 {missing}")
            assessment["completeness"][category] = {
                "status": "⚠️ 部分缺失",
                "score": 50,
                "missing": missing,
            }
        else:
            assessment["completeness"][category] = {"status": "✅ 完整", "score": 100}

        assessment["files"][config["file"]] = {
            "exists": True,
            "size": file_path.stat().st_size,
            "note": config.get("note", ""),
        }

    # 检查可选字段
    print("🔍 检查可选数据...")
    for category, config in optional_fields.items():
        file_path = match_dir / config["file"]

        if not file_path.exists():
            assessment["missing_optional"].append(f"{category}: 文件不存在")
            assessment["completeness"][category] = {"status": "⚪ 无数据", "score": 0}
            continue

        with open(file_path, encoding='utf-8') as f:
            data = json.load(f)

        # 检查字段是否有实际内容
        available = []
        empty = []

        if isinstance(data, dict):
            for field in config["fields"]:
                value = data.get(field)
                if value and value != "" and value != [] and value != {} and value != 0:
                    available.append(field)
                else:
                    empty.append(field)

        score = int(len(available) / len(config["fields"]) * 100) if config["fields"] else 0

        if score >= 80:
            status = "✅ 完整"
        elif score >= 50:
            status = "⚠️ 部分可用"
        else:
            status = "❌ 严重不足"

        assessment["completeness"][category] = {
            "status": status,
            "score": score,
            "available": available,
            "empty": empty,
        }

        if empty:
            assessment["missing_optional"].append(f"{category}: 空字段 {empty}")

        assessment["files"][config["file"]] = {
            "exists": True,
            "size": file_path.stat().st_size,
            "note": config.get("note", ""),
        }

    # 生成建议
    print("\n💡 生成改进建议...")

    # 检查赔率公司数量
    odds_file = match_dir / "赔率变化数据.json"
    if odds_file.exists():
        with open(odds_file, encoding='utf-8') as f:
            odds = json.load(f)
        if len(odds) < 3:
            assessment["recommendations"].append(
                f"赔率公司不足：当前 {len(odds)} 家，建议至少 3-5 家"
            )

    # 检查近期比赛数量
    recent_file = match_dir / "主客队近期比赛数据.json"
    if recent_file.exists():
        with open(recent_file, encoding='utf-8') as f:
            recent = json.load(f)
        home_count = len(recent.get("home_history_match", []))
        away_count = len(recent.get("away_history_match", []))
        if home_count < 5 or away_count < 5:
            assessment["recommendations"].append(
                f"近期比赛不足：主队 {home_count} 场，客队 {away_count} 场，建议各 10 场以上"
            )

    # 检查交锋记录数量
    h2h_file = match_dir / "两队比赛历史交锋数据.json"
    if h2h_file.exists():
        with open(h2h_file, encoding='utf-8') as f:
            h2h = json.load(f)
        if len(h2h) < 3:
            assessment["recommendations"].append(
                f"历史交锋不足：当前 {len(h2h)} 场，建议至少 5 场"
            )

    # 检查阵容信息
    venue_file = match_dir / "比赛场地、天气、主客队队员上场信息(身价、位置)数据.json"
    if venue_file.exists():
        with open(venue_file, encoding='utf-8') as f:
            venue = json.load(f)
        if not venue.get("has_lineup"):
            assessment["recommendations"].append(
                "缺少首发阵容信息：影响分析准确性"
            )
        if not venue.get("weather") or venue.get("weather") == "未知":
            assessment["recommendations"].append(
                "缺少天气信息：可能影响比赛（雨战、高温等）"
            )

    return assessment


def print_assessment(assessment: Dict[str, Any]):
    """打印评估报告"""

    print("\n" + "=" * 70)
    print("📊 数据完整性评估报告")
    print("=" * 70)

    # 计算总分
    scores = [v.get("score", 0) for v in assessment["completeness"].values()]
    total_score = sum(scores) / len(scores) if scores else 0

    print(f"\n📈 总体评分: {total_score:.1f}/100")

    if total_score >= 80:
        print("✅ 数据完整性良好，可以支持专业分析")
    elif total_score >= 60:
        print("⚠️ 数据基本可用，但部分关键信息缺失")
    else:
        print("❌ 数据严重不足，需要补充才能进行有效分析")

    # 必须数据状态
    print("\n📋 必须数据:")
    for category, info in assessment["completeness"].items():
        if category in ["赛事基本信息", "赔率数据", "历史交锋", "近期战绩"]:
            print(f"   {info['status']} {category}")
            if info.get("missing"):
                print(f"      缺失: {', '.join(info['missing'])}")

    # 可选数据状态
    print("\n📋 可选数据:")
    for category, info in assessment["completeness"].items():
        if category in ["阵容情报", "场地天气", "联赛积分"]:
            print(f"   {info['status']} {category}")
            if info.get("empty"):
                print(f"      空字段: {', '.join(info['empty'])}")

    # 缺失的关键数据
    if assessment["missing_critical"]:
        print("\n❌ 缺失的关键数据:")
        for missing in assessment["missing_critical"]:
            print(f"   • {missing}")

    # 缺失的可选数据
    if assessment["missing_optional"]:
        print("\n⚠️ 缺失的可选数据:")
        for missing in assessment["missing_optional"]:
            print(f"   • {missing}")

    # 改进建议
    if assessment["recommendations"]:
        print("\n💡 改进建议:")
        for i, rec in enumerate(assessment["recommendations"], 1):
            print(f"   {i}. {rec}")

    # 文件统计
    print("\n📁 文件统计:")
    total_size = 0
    for filename, info in assessment["files"].items():
        size_kb = info["size"] / 1024
        total_size += size_kb
        print(f"   • {filename}: {size_kb:.1f} KB")

    print(f"   总大小: {total_size:.1f} KB")

    return total_score


def main():
    """主函数"""

    # 检查所有比赛
    date_dir = Path("data/matches/2026-06-04")

    if not date_dir.exists():
        print("❌ 数据目录不存在")
        return

    match_dirs = sorted([d for d in date_dir.iterdir() if d.is_dir()])

    print(f"🏟️  发现 {len(match_dirs)} 场比赛")

    all_scores = []

    for match_dir in match_dirs[:3]:  # 只检查前 3 场
        print(f"\n\n{'='*70}")
        print(f"🔍 检查: {match_dir.name}")
        print('='*70)

        assessment = assess_data_completeness(match_dir)
        score = print_assessment(assessment)
        all_scores.append(score)

    # 汇总统计
    print("\n\n" + "=" * 70)
    print("📊 汇总统计")
    print("=" * 70)

    avg_score = sum(all_scores) / len(all_scores) if all_scores else 0
    print(f"\n平均数据完整性评分: {avg_score:.1f}/100")

    if avg_score >= 80:
        print("\n✅ 结论: 数据完整性良好，可以支持专业分析")
        print("   主要问题可能在于提示词或 LLM 模型能力")
    elif avg_score >= 60:
        print("\n⚠️ 结论: 数据基本可用，但需要补充部分关键信息")
        print("   建议优先补充:")
        print("   1. 更多赔率公司数据（3-5 家以上）")
        print("   2. 更多近期比赛数据（10 场以上）")
        print("   3. 首发阵容信息")
        print("   4. 天气和场地信息")
    else:
        print("\n❌ 结论: 数据严重不足，需要大幅补充")
        print("   当前数据可能无法支撑准确的比赛分析")

    print("\n💡 数据补充建议:")
    print("   1. 检查数据源 API 是否提供了更多字段")
    print("   2. 考虑增加更多赔率公司（如 BWIN、Pinnacle 等）")
    print("   3. 抓取首发阵容和伤停信息")
    print("   4. 获取天气预报数据")
    print("   5. 增加联赛积分榜详细数据")


if __name__ == "__main__":
    main()
