#!/usr/bin/env python3
"""重新抓取赛事数据（使用扩展的赔率公司）"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# 添加源码路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from football_sim.data_sources.match_fetcher import fetch_and_parse_matches
from football_sim.data_sources.match_store import save_match_data
from football_sim.data_sources.odds_fetcher import fetch_all_matches_data, WHITELIST_COMPANY_IDS
from football_sim.history_db import init_history_db, record_match

async def refetch_with_more_companies(date_str: str = "2026-06-04"):
    """使用扩展的赔率公司重新抓取数据"""

    print("=" * 70)
    print("🔄 重新抓取赛事数据（扩展赔率公司）")
    print("=" * 70)

    print(f"\n📅 日期: {date_str}")
    print(f"📊 赔率公司数: {len(WHITELIST_COMPANY_IDS)} 家")
    print(f"📋 公司列表: {sorted(WHITELIST_COMPANY_IDS)}")

    # 初始化数据库
    db_path = Path("data/users/default/history.sqlite3")
    init_history_db(db_path)

    # 抓取赛事列表
    print("\n📡 步骤 1: 抓取赛事列表...")
    try:
        from football_sim.data_sources.match_fetcher import fetch_and_parse_matches
        matches = fetch_and_parse_matches(date_str)
        if asyncio.iscoroutine(matches):
            matches = await matches
        print(f"✅ 成功抓取 {len(matches)} 场比赛")
    except Exception as e:
        print(f"❌ 抓取赛事列表失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # 抓取每场比赛的详细数据
    print("\n📡 步骤 2: 抓取赛事详情和赔率数据...")
    matches_dir = Path("data/matches") / date_str
    matches_dir.mkdir(parents=True, exist_ok=True)

    success_count = 0
    fail_count = 0

    for idx, match in enumerate(matches, 1):
        print(f"\n[{idx}/{len(matches)}] {match.home_team} vs {match.away_team}")

        try:
            # 抓取完整数据（包括赔率）
            result = await fetch_all_matches_data([match])

            if result and len(result) > 0:
                match_data = result[0][1]  # result 是 [(match, data), ...]

                # 保存数据
                match_dir = save_match_data(match, match_data, matches_dir)

                # 记录到数据库
                record_match(db_path, {
                    "match_id": match.match_id,
                    "date": date_str,
                    "league": match.league,
                    "home_team": match.home_team,
                    "away_team": match.away_team,
                    "match_time": match.match_time,
                    "round_info": match.round,
                    "data_dir": str(match_dir),
                    "fetched_at": datetime.now().isoformat(),
                })

                # 统计赔率公司数
                odds_data = match_data.get("赔率变化数据", {})
                company_count = len(odds_data)

                print(f"   ✅ 成功 - {company_count} 家公司赔率数据")
                success_count += 1
            else:
                print(f"   ❌ 失败 - 未获取到数据")
                fail_count += 1

        except Exception as e:
            print(f"   ❌ 失败 - {e}")
            fail_count += 1

        # 避免请求过快
        await asyncio.sleep(0.5)

    # 统计结果
    print("\n" + "=" * 70)
    print("📊 抓取结果统计")
    print("=" * 70)

    print(f"\n✅ 成功: {success_count} 场")
    print(f"❌ 失败: {fail_count} 场")
    print(f"📊 总计: {len(matches)} 场")

    # 检查数据完整性
    print("\n" + "=" * 70)
    print("🔍 数据完整性检查")
    print("=" * 70)

    for match_dir in sorted(matches_dir.iterdir()):
        if match_dir.is_dir():
            odds_file = match_dir / "赔率变化数据.json"
            if odds_file.exists():
                import json
                with open(odds_file, encoding='utf-8') as f:
                    odds = json.load(f)
                print(f"\n   {match_dir.name}")
                print(f"      赔率公司: {len(odds)} 家")
                print(f"      公司列表: {list(odds.keys())[:5]}...")
            else:
                print(f"\n   {match_dir.name}")
                print(f"      ⚠️  无赔率数据")

    print("\n" + "=" * 70)
    print("✅ 重新抓取完成！")
    print("=" * 70)
    print("\n💡 下一步:")
    print("   1. 验证新的赔率数据")
    print("   2. 重新分析比赛")
    print("   3. 评估命中率是否有提升")


async def verify_odds_data(date_str: str = "2026-06-04"):
    """验证抓取的赔率数据"""

    print("\n" + "=" * 70)
    print("🔍 验证赔率数据")
    print("=" * 70)

    matches_dir = Path("data/matches") / date_str

    if not matches_dir.exists():
        print(f"❌ 数据目录不存在: {matches_dir}")
        return

    total_matches = 0
    total_companies = set()

    for match_dir in sorted(matches_dir.iterdir()):
        if not match_dir.is_dir():
            continue

        total_matches += 1
        odds_file = match_dir / "赔率变化数据.json"

        if not odds_file.exists():
            print(f"\n⚠️  {match_dir.name}: 无赔率数据")
            continue

        import json
        with open(odds_file, encoding='utf-8') as f:
            odds = json.load(f)

        companies = list(odds.keys())
        total_companies.update(companies)

        print(f"\n✅ {match_dir.name}")
        print(f"   公司数: {len(companies)}")
        print(f"   公司: {', '.join(companies[:5])}{'...' if len(companies) > 5 else ''}")

    print(f"\n📊 总体统计:")
    print(f"   比赛场次: {total_matches}")
    print(f"   赔率公司种类: {len(total_companies)}")
    print(f"   所有公司: {sorted(total_companies)}")


async def main():
    """主函数"""

    import argparse

    parser = argparse.ArgumentParser(description='重新抓取赛事数据')
    parser.add_argument('--date', default='2026-06-04', help='日期 (YYYY-MM-DD)')
    parser.add_argument('--verify-only', action='store_true', help='只验证数据，不重新抓取')

    args = parser.parse_args()

    if args.verify_only:
        await verify_odds_data(args.date)
    else:
        await refetch_with_more_companies(args.date)
        await verify_odds_data(args.date)


if __name__ == "__main__":
    asyncio.run(main())
