#!/usr/bin/env python3
"""探索 API 支持的所有赔率公司"""
import asyncio
import aiohttp
import sys
from pathlib import Path

# 添加源码路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from football_sim.data_sources.http_client import get_random_user_agent
from football_sim.data_sources.odds_fetcher import ODDS_MERGE_URL, WHITELIST_COMPANY_IDS

async def fetch_all_companies(match_id: str = "13741823"):
    """获取 API 返回的所有赔率公司"""

    print("=" * 70)
    print("🔍 探索 API 支持的赔率公司")
    print("=" * 70)

    print(f"\n📋 当前白名单公司: {WHITELIST_COMPANY_IDS}")
    print(f"📋 测试比赛 ID: {match_id}")

    # 请求参数 - 需要指定 type_id
    # type_id: 1=亚盘, 2=欧指, 3=大小球
    # 我们获取欧指数据（type_id=2），因为这是最重要的
    params = {
        "match_id": match_id,
        "sport_id": 1,
        "type_id": 2,  # 欧指
        "app_type": 4,
    }

    headers = {
        "User-Agent": get_random_user_agent(),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": "https://m.shemen365.com/",
    }

    async with aiohttp.ClientSession() as session:
        try:
            print("\n📡 请求赔率合并数据...")
            async with session.get(ODDS_MERGE_URL, params=params, headers=headers,
                                   timeout=aiohttp.ClientTimeout(total=15)) as resp:
                resp.raise_for_status()
                data = await resp.json()

                if data.get("code") != 0:
                    print(f"❌ API 返回错误: {data.get('msg', '未知错误')}")
                    return

                book_list = data.get("data", {}).get("book_list", [])

                print(f"\n✅ 成功获取 {len(book_list)} 家公司的赔率数据")

                # 统计所有公司
                print("\n" + "=" * 70)
                print("📊 所有可用的赔率公司")
                print("=" * 70)

                all_companies = []

                for book in book_list:
                    book_id = int(book.get("book_id", 0))
                    book_name = book.get("book_name", "未知")

                    # 检查是否有欧指数据
                    euro_data = book.get("euro", {})
                    has_euro = bool(euro_data and euro_data.get("current_left"))

                    # 检查是否有亚盘数据
                    asian_data = book.get("asian", {})
                    has_asian = bool(asian_data and asian_data.get("current_left"))

                    # 检查是否有大小球数据
                    ou_data = book.get("ou", {})
                    has_ou = bool(ou_data and ou_data.get("current_left"))

                    is_whitelisted = book_id in WHITELIST_COMPANY_IDS

                    company_info = {
                        "id": book_id,
                        "name": book_name,
                        "has_euro": has_euro,
                        "has_asian": has_asian,
                        "has_ou": has_ou,
                        "is_whitelisted": is_whitelisted,
                    }

                    all_companies.append(company_info)

                    # 打印公司信息
                    status = "✅ 已在白名单" if is_whitelisted else "⬜ 未在白名单"
                    data_types = []
                    if has_euro:
                        data_types.append("欧指")
                    if has_asian:
                        data_types.append("亚盘")
                    if has_ou:
                        data_types.append("大小球")

                    print(f"\n   {book_id:>4} | {book_name:<12} | {status}")
                    print(f"        数据类型: {', '.join(data_types) if data_types else '无'}")

                # 统计
                print("\n" + "=" * 70)
                print("📈 统计信息")
                print("=" * 70)

                total = len(all_companies)
                whitelisted = len([c for c in all_companies if c["is_whitelisted"]])
                with_euro = len([c for c in all_companies if c["has_euro"]])
                with_asian = len([c for c in all_companies if c["has_asian"]])
                with_ou = len([c for c in all_companies if c["has_ou"]])

                print(f"\n   总公司数: {total}")
                print(f"   已在白名单: {whitelisted}")
                print(f"   有欧指数据: {with_euro}")
                print(f"   有亚盘数据: {with_asian}")
                print(f"   有大小球数据: {with_ou}")

                # 推荐新增公司
                print("\n" + "=" * 70)
                print("💡 推荐新增的公司（有完整数据且未在白名单）")
                print("=" * 70)

                recommended = [
                    c for c in all_companies
                    if not c["is_whitelisted"]
                    and c["has_euro"]
                    and c["has_asian"]
                    and c["has_ou"]
                ]

                if recommended:
                    print(f"\n找到 {len(recommended)} 家推荐公司:\n")
                    for c in recommended:
                        print(f"   {c['id']:>4} | {c['name']}")
                else:
                    print("\n未找到符合条件的推荐公司")

                # 有欧指数据的公司（最重要的）
                print("\n" + "=" * 70)
                print("🎯 有欧指数据的公司（最重要）")
                print("=" * 70)

                euro_companies = [
                    c for c in all_companies
                    if c["has_euro"]
                ]

                print(f"\n共 {len(euro_companies)} 家有欧指数据:\n")
                for c in euro_companies:
                    status = "✅" if c["is_whitelisted"] else "⬜"
                    print(f"   {status} {c['id']:>4} | {c['name']}")

                # 生成新的白名单建议
                print("\n" + "=" * 70)
                print("🔧 建议的新白名单配置")
                print("=" * 70)

                # 保留原有白名单
                new_whitelist = set(WHITELIST_COMPANY_IDS)

                # 添加有完整数据的公司（最多添加 5 家）
                added = 0
                for c in recommended:
                    if added >= 5:
                        break
                    if c["id"] not in new_whitelist:
                        new_whitelist.add(c["id"])
                        added += 1

                # 如果推荐不足，添加有欧指数据的公司
                if added < 5:
                    for c in euro_companies:
                        if added >= 5:
                            break
                        if c["id"] not in new_whitelist:
                            new_whitelist.add(c["id"])
                            added += 1

                print(f"\n当前白名单: {sorted(WHITELIST_COMPANY_IDS)}")
                print(f"建议白名单: {sorted(new_whitelist)}")
                print(f"新增: {len(new_whitelist) - len(WHITELIST_COMPANY_IDS)} 家")

                # 生成代码
                print("\n" + "=" * 70)
                print("📝 代码修改建议")
                print("=" * 70)

                company_names = []
                for c in all_companies:
                    if c["id"] in new_whitelist:
                        company_names.append(f"{c['id']}={c['name']}")

                print(f"""
在 src/football_sim/data_sources/odds_fetcher.py 中修改:

# 原白名单（5 家）
WHITELIST_COMPANY_IDS = {{31, 5, 7, 92, 533}}

# 新白名单（{len(new_whitelist)} 家）
WHITELIST_COMPANY_IDS = {new_whitelist}

# 公司说明:
""")
                for c in all_companies:
                    if c["id"] in new_whitelist:
                        print(f"# {c['id']:>4} = {c['name']}")

        except Exception as e:
            print(f"\n❌ 请求失败: {e}")
            import traceback
            traceback.print_exc()


async def main():
    """主函数"""

    # 使用一场比赛测试
    test_match_id = "13741823"

    print("🚀 开始探索赔率公司...")
    print(f"📋 测试比赛: 斯洛文尼亚 vs 塞浦路斯")

    await fetch_all_companies(test_match_id)

    print("\n" + "=" * 70)
    print("✅ 探索完成！")
    print("=" * 70)
    print("\n💡 下一步:")
    print("   1. 查看推荐的公司列表")
    print("   2. 修改 odds_fetcher.py 中的 WHITELIST_COMPANY_IDS")
    print("   3. 重新抓取赛事数据")
    print("   4. 测试新的赔率数据")


if __name__ == "__main__":
    asyncio.run(main())
