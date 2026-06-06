import asyncio
import os
import random
import ssl
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from football_sim.data_sources.http_client import get_random_user_agent
from football_sim.models import FootballMatch

# SSL 验证控制
SSL_VERIFY = os.environ.get("FOOTBALL_SSL_VERIFY", "true").lower() != "false"
# 代理控制
USE_PROXY = os.environ.get("FOOTBALL_USE_PROXY", "false").lower() == "true"

# 赔率合并详情URL
ODDS_MERGE_URL = "https://api.shemen365.com/new-match/detail/odds/merge-detail"
# 赔率变化详情URL
ODDS_DETAIL_URL = "https://api.shemen365.com/new-match/detail/odds/detail/list"

# 白名单公司（扩展到 10 家主要公司）
# 原有 5 家：31=365, 5=威廉, 7=立博, 92=澳门, 533=易胜博
# 新增 5 家：6=韦德, 8=Interwetten, 9=BWIN, 79=Betfair, 110=利记
WHITELIST_COMPANY_IDS = {31, 5, 7, 92, 533, 6, 8, 9, 79, 110}

# 公司说明：
# 31 = 36*（Bet365）- 全球最大博彩公司
# 5 = 威廉**（William Hill）- 英国老牌博彩
# 7 = 立*（Ladbrokes）- 英国主流博彩
# 92 = 澳*（澳门彩票）- 亚洲市场
# 533 = 易**（易胜博）- 亚洲市场
# 6 = 韦*（韦德）- 欧洲主流博彩
# 8 = Inter*（Interwetten）- 国际博彩，赔率精准
# 9 = Bw*（BWIN）- 欧洲大型博彩
# 79 = Be*fair（Betfair）- 专业博彩交易所，赔率最具参考价值
# 110 = 利*（利记）- 亚洲市场

# 额外数据URL模板
EXTRA_URLS = {
    "history_battle": "https://api.shemen365.com/new-match/football/detail/history-battle?match_id={match_id}&app_type=4",
    "lately_record": "https://api.shemen365.com/new-match/football/detail/lately-record?match_id={match_id}&app_type=4",
    "report_info": "https://mapi.shemen365.com/new-article/report/info?match_id={match_id}&sport_id=1&app_type=4",
    "lineup_info": "https://api.shemen365.com/mongo/match/lineup/football?match_id={match_id}&sport_id=1&app_type=4",
    "data_analysis": "https://api.shemen365.com/new-match/football/detail/data-analysis?match_id={match_id}&app_type=4",
}


def parse_match_details(details: Dict[str, Any], match_id: str, type_id: int) -> List[Dict[str, Any]]:
    if details.get("code") != 0:
        return []
    book_list = details.get("data", {}).get("book_list", [])
    parsed = []
    for book in book_list:
        if int(book.get("book_id", 0)) not in WHITELIST_COMPANY_IDS:
            continue
        parsed.append({
            "match_id": match_id,
            "company_id": book["book_id"],
            "company_name": book["book_name"],
            "handicap": book.get("ovalue0"),
            "home_win_odds": float(book.get("current_left", 0)),
            "draw_odds": float(book["current_middle"]) if book.get("current_middle") else None,
            "away_win_odds": float(book.get("current_right", 0)),
            "type_id": type_id,
        })
    return parsed


async def fetch_odds_changes(
    session: aiohttp.ClientSession,
    match_id: str,
    company_id: str,
    type_id: int,
    semaphore: asyncio.Semaphore,
) -> List[Dict[str, Any]]:
    params = {
        "match_id": match_id,
        "book_id": company_id,
        "sport_id": 1,
        "type_id": type_id,
        "sort_type": "desc",
        "scene": "pc_detail",
        "app_type": 4,
    }
    headers = {
        "User-Agent": get_random_user_agent(),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": "https://m.shemen365.com/",
    }
    try:
        async with semaphore:
            async with session.get(ODDS_DETAIL_URL, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                resp.raise_for_status()
                data = await resp.json()
                detail_list = data.get("data", {}).get("detail_list", [])
                for item in detail_list:
                    if "update_time" in item:
                        item["update_time"] = datetime.fromtimestamp(item["update_time"]).strftime("%Y-%m-%d %H:%M:%S")
                return detail_list
    except Exception as e:
        print(f"赔率变化请求失败: match_id={match_id} company_id={company_id} type_id={type_id} -> {e}")
        return []


async def process_company_details(
    session: aiohttp.ClientSession,
    match_id: str,
    company_id: str,
    company_name: str,
    type_id: int,
    semaphore: asyncio.Semaphore,
) -> Tuple[Dict[str, str], Dict[str, list]]:
    changes = await fetch_odds_changes(session, match_id, company_id, type_id, semaphore)
    odds_changes: Dict[str, list] = {}
    if changes:
        type_map = {1: "亚盘", 2: "欧指", 3: "大小球"}
        key = type_map.get(type_id, "")
        if key:
            odds_changes[key] = changes
    return {"id": company_id, "name": company_name}, odds_changes


async def fetch_match_detail_data(session: aiohttp.ClientSession, match_id: str) -> Optional[Dict[str, Any]]:
    url = f"https://api.shemen365.com/match/football/new-detail?match_id={match_id}&app_type=4"
    headers = {"User-Agent": get_random_user_agent()}
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10), headers=headers) as resp:
            resp.raise_for_status()
            data = await resp.json()
            data = data.get("data", {})
            data.pop("odds_info", None)
            return data
    except Exception as e:
        print(f"获取比赛详细数据失败 match_id={match_id}: {e}")
        return None


async def fetch_and_process(session: aiohttp.ClientSession, url: str, semaphore: asyncio.Semaphore) -> Any:
    headers = {"User-Agent": get_random_user_agent()}
    try:
        async with semaphore:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10), headers=headers) as resp:
                resp.raise_for_status()
                return await resp.json()
    except Exception as e:
        print(f"请求失败: {url} -> {e}")
        raise


async def process_history_battle(session: aiohttp.ClientSession, match_id: str, semaphore: asyncio.Semaphore) -> Any:
    url = EXTRA_URLS["history_battle"].format(match_id=match_id)
    data = await fetch_and_process(session, url, semaphore)
    if data.get("code") == 0:
        match_list = data.get("data", {}).get("match_list", [])
        for item in match_list:
            sub_id = item.get("match_id")
            detail = await fetch_match_detail_data(session, sub_id)
            if detail:
                item["detail_data"] = detail
        return match_list
    return {"error": "数据获取失败"}


async def process_lately_record(session: aiohttp.ClientSession, match_id: str, semaphore: asyncio.Semaphore) -> Any:
    url = EXTRA_URLS["lately_record"].format(match_id=match_id)
    data = await fetch_and_process(session, url, semaphore)
    if data.get("code") == 0:
        content = data.get("data", {})
        for key in ("away_history_match", "home_history_match"):
            for item in content.get(key, []):
                sub_id = item.get("match_id")
                detail = await fetch_match_detail_data(session, sub_id)
                if detail:
                    item["detail_data"] = detail
        return content
    return {"error": "数据获取失败"}


async def process_simple(session: aiohttp.ClientSession, match_id: str, key: str, semaphore: asyncio.Semaphore) -> Any:
    url = EXTRA_URLS[key].format(match_id=match_id)
    data = await fetch_and_process(session, url, semaphore)
    if data.get("code") == 0:
        return data.get("data", {})
    return {"error": "数据获取失败"}


async def fetch_additional_data(session: aiohttp.ClientSession, match_id: str, semaphore: asyncio.Semaphore) -> Dict[str, Any]:
    tasks = [
        process_history_battle(session, match_id, semaphore),
        process_lately_record(session, match_id, semaphore),
        process_simple(session, match_id, "report_info", semaphore),
        process_simple(session, match_id, "lineup_info", semaphore),
        process_simple(session, match_id, "data_analysis", semaphore),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    keys = ["history_battle", "lately_record", "report_info", "lineup_info", "data_analysis"]
    additional: Dict[str, Any] = {}
    for result, key in zip(results, keys):
        if isinstance(result, Exception):
            additional[key] = {"error": str(result)}
        else:
            additional[key] = result
    return additional


def clean_complete_data(complete_data: Dict[str, Any]) -> Dict[str, Any]:
    fields_to_remove = {
        "sport_id", "odds_list", "status", "status_code", "home_team_id",
        "away_team_id", "tournament_id", "season_id", "reverse", "neutral", "corner",
    }

    def remove_fields(item_list: Any) -> None:
        if isinstance(item_list, list):
            for item in item_list:
                if isinstance(item, dict):
                    for field in fields_to_remove:
                        item.pop(field, None)

    history_battle = complete_data.get("两队比赛历史交锋数据", {})
    lately_record = complete_data.get("主客队近期比赛数据", {})
    data_analysis = complete_data.get("联赛积分排名、近期状态(进球数、失球数)、未来赛事数据", {})

    remove_fields(history_battle)
    remove_fields(lately_record.get("away_history_match", []))
    remove_fields(lately_record.get("home_history_match", []))

    if isinstance(data_analysis, dict):
        data_analysis.pop("odds_preview", None)

    return {
        "两队比赛历史交锋数据": history_battle,
        "主客队近期比赛数据": lately_record,
        "主客队队员、情报信息数据": complete_data.get("主客队队员、情报信息数据", {}),
        "比赛场地、天气、主客队队员上场信息(身价、位置)数据": complete_data.get("比赛场地、天气、主客队队员上场信息(身价、位置)数据", {}),
        "联赛积分排名、近期状态(进球数、失球数)、未来赛事数据": data_analysis,
        "赔率变化数据": complete_data.get("赔率变化数据", {}),
    }


async def fetch_match_full_data(
    session: aiohttp.ClientSession,
    match: FootballMatch,
    semaphore: asyncio.Semaphore,
) -> Dict[str, Any]:
    match_id = match.match_id

    # 获取三种赔率类型的公司数据
    company_lists: Dict[int, list] = {}
    for type_id in (1, 2, 3):
        url = f"{ODDS_MERGE_URL}?match_id={match_id}&type_id={type_id}&sport_id=1&app_type=4"
        try:
            async with semaphore:
                headers = {"User-Agent": get_random_user_agent()}
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10), headers=headers) as resp:
                    resp.raise_for_status()
                    details = await resp.json()
                    company_lists[type_id] = parse_match_details(details, match_id, type_id)
        except Exception as e:
            print(f"赔率获取失败 match={match_id} type={type_id}: {e}")
            company_lists[type_id] = []

    # 收集所有公司
    all_companies: Dict[str, Dict] = {}
    for type_id, companies in company_lists.items():
        for company in companies:
            cid = company["company_id"]
            if cid not in all_companies:
                all_companies[cid] = {
                    "company_name": company["company_name"],
                    "company_id": cid,
                }

    # 获取每个公司三种赔率变化
    odds_tasks = []
    for cid, cinfo in all_companies.items():
        for type_id in (1, 2, 3):
            odds_tasks.append(
                process_company_details(session, match_id, cid, cinfo["company_name"], type_id, semaphore)
            )

    odds_results = await asyncio.gather(*odds_tasks, return_exceptions=True)

    match_odds_data: Dict[str, Dict] = {}
    for result in odds_results:
        if isinstance(result, Exception):
            continue
        company_info, odds_data = result
        cname = company_info["name"]
        if cname not in match_odds_data:
            match_odds_data[cname] = {"亚盘": [], "欧指": [], "大小球": []}
        for key in ("亚盘", "欧指", "大小球"):
            if key in odds_data:
                match_odds_data[cname][key] = odds_data[key]

    # 获取额外数据
    additional = await fetch_additional_data(session, match_id, semaphore)

    complete_data = {
        "两队比赛历史交锋数据": additional.get("history_battle", {}),
        "主客队近期比赛数据": additional.get("lately_record", {}),
        "主客队队员、情报信息数据": additional.get("report_info", {}),
        "比赛场地、天气、主客队队员上场信息(身价、位置)数据": additional.get("lineup_info", {}),
        "联赛积分排名、近期状态(进球数、失球数)、未来赛事数据": additional.get("data_analysis", {}),
        "赔率变化数据": match_odds_data,
    }

    return clean_complete_data(complete_data)


def _create_ssl_context() -> ssl.SSLContext:
    """创建 SSL 上下文，支持跳过验证。"""
    if SSL_VERIFY:
        return ssl.create_default_context()
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


async def fetch_all_matches_data(matches: List[FootballMatch]) -> List[Tuple[FootballMatch, Dict[str, Any]]]:
    semaphore = asyncio.Semaphore(5)
    results: List[Tuple[FootballMatch, Dict[str, Any]]] = []

    ssl_context = _create_ssl_context()
    # 禁用代理以避免 SSL 干扰（trust_env=False 不从环境变量读取代理配置）
    connector = aiohttp.TCPConnector(ssl=ssl_context)

    async with aiohttp.ClientSession(connector=connector, trust_env=USE_PROXY) as session:
        for match in matches:
            try:
                data = await fetch_match_full_data(session, match, semaphore)
                results.append((match, data))
                print(f"  已获取: {match.display_name}")
            except Exception as e:
                print(f"  获取失败: {match.display_name} -> {e}")
                results.append((match, {"error": str(e)}))
            await asyncio.sleep(random.uniform(0.5, 1.5))

    return results
