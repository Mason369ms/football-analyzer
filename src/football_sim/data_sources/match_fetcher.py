import random
from datetime import datetime
from typing import Any, Dict, List

from football_sim.data_sources.http_client import get_random_user_agent, safe_get

from football_sim.models import FootballMatch

# 竞彩URL
API_URL_TEMPLATE = "https://mapi.shemen365.com/new-match/jc/football-list?date={date}&app_type=4"
# 比赛详情URL（用于获取比赛结果）
MATCH_DETAIL_URL = "https://api.shemen365.com/new-match/detail/football?match_id={match_id}&app_type=4"


def _resolve_date(date_str: str) -> str:
    if date_str in ("today", "now", ""):
        return datetime.now().strftime("%Y-%m-%d")
    return date_str


def fetch_match_list(date_str: str = "today") -> Dict[str, Any]:
    date = _resolve_date(date_str)
    url = API_URL_TEMPLATE.format(date=date)
    headers = {"User-Agent": get_random_user_agent()}
    resp = safe_get(url, timeout=15, headers=headers)
    resp.raise_for_status()
    return resp.json()


def parse_match_list(data: Dict[str, Any], date_str: str = "today") -> List[FootballMatch]:
    date = _resolve_date(date_str)
    matches: List[FootballMatch] = []
    match_list = data.get("data", {}).get("match_list", {}).get(date, [])
    for m in match_list:
        match_info = m.get("match_info", {})
        team_info = m.get("team_info", {})
        tournament_info = m.get("tournament_info", {})
        lottery_info = m.get("lottery_info", {})

        matches.append(FootballMatch(
            match_id=str(match_info.get("match_id", "")),
            league=tournament_info.get("tournament_name", ""),
            home_team=team_info.get("home_team_name", ""),
            away_team=team_info.get("away_team_name", ""),
            match_time=match_info.get("match_time", ""),
            round=str(lottery_info.get("round", "")),
            home_score=int(match_info["home_team_score"]) if match_info.get("home_team_score") not in (None, "") else None,
            away_score=int(match_info["away_team_score"]) if match_info.get("away_team_score") not in (None, "") else None,
            is_end=bool(match_info.get("is_end", False)),
        ))
    return matches


def fetch_and_parse_matches(date_str: str = "today") -> List[FootballMatch]:
    data = fetch_match_list(date_str)
    return parse_match_list(data, date_str)


def fetch_match_result(match_id: str) -> Dict[str, Any]:
    """获取单场比赛结果"""
    url = MATCH_DETAIL_URL.format(match_id=match_id)
    headers = {"User-Agent": get_random_user_agent()}
    resp = safe_get(url, timeout=15, headers=headers)
    resp.raise_for_status()
    return resp.json()


def parse_match_result(data: Dict[str, Any], match_id: str) -> Dict[str, Any]:
    """解析比赛结果"""
    if data.get("code") != 0:
        return {"match_id": match_id, "error": "API error"}

    match_data = data.get("data", {}).get("match_info", {})
    if not match_data:
        return {"match_id": match_id, "error": "No match data"}

    home_score = match_data.get("home_score")
    away_score = match_data.get("away_score")
    half_home = match_data.get("home_half_time_score")
    half_away = match_data.get("away_half_time_score")

    # 判断比赛结果
    result = ""
    if home_score is not None and away_score is not None:
        home_score = int(home_score)
        away_score = int(away_score)
        if home_score > away_score:
            result = "主胜"
        elif home_score < away_score:
            result = "客胜"
        else:
            result = "平局"

    return {
        "match_id": match_id,
        "home_score": home_score,
        "away_score": away_score,
        "result": result,
        "half_home_score": int(half_home) if half_home is not None else None,
        "half_away_score": int(half_away) if half_away is not None else None,
        "fetched_at": datetime.now().isoformat(),
    }


def fetch_and_parse_result(match_id: str) -> Dict[str, Any]:
    """获取并解析比赛结果"""
    data = fetch_match_result(match_id)
    return parse_match_result(data, match_id)
