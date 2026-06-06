import json
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from football_sim.data_sources.match_store import load_match_data


def calc_implied_probability(home: float, draw: float, away: float) -> Dict[str, float]:
    if home <= 0 or draw <= 0 or away <= 0:
        return {"p_home": 0, "p_draw": 0, "p_away": 0, "margin": 0}
    s = 1 / home + 1 / draw + 1 / away
    return {
        "p_home": round((1 / home) / s * 100, 1),
        "p_draw": round((1 / draw) / s * 100, 1),
        "p_away": round((1 / away) / s * 100, 1),
        "margin": round((s - 1) * 100, 2),
    }


def calc_implied_probability_asian(home_odds: float, away_odds: float) -> Dict[str, float]:
    if home_odds <= 0 or away_odds <= 0:
        return {"p_home": 0, "p_away": 0, "margin": 0}
    s = 1 / home_odds + 1 / away_odds
    return {
        "p_home": round((1 / home_odds) / s * 100, 1),
        "p_away": round((1 / away_odds) / s * 100, 1),
        "margin": round((s - 1) * 100, 2),
    }


def detect_odds_movement(initial_odds: float, current_odds: float, threshold: float = 0.15) -> Dict[str, Any]:
    if initial_odds <= 0:
        return {"changed": False, "direction": "neutral", "幅度": 0}
    change = (current_odds - initial_odds) / initial_odds
    if abs(change) < threshold:
        return {"changed": False, "direction": "neutral", "幅度": round(change * 100, 2)}
    direction = "升" if change > 0 else "降"
    return {"changed": True, "direction": direction, "幅度": round(change * 100, 2)}


def compare_bookmakers(euro_odds_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not euro_odds_list:
        return {"count": 0, "均值": {}, "中位数": {}, "离群公司": []}

    home_vals = [o["home_win_odds"] for o in euro_odds_list if o.get("home_win_odds")]
    draw_vals = [o["draw_odds"] for o in euro_odds_list if o.get("draw_odds")]
    away_vals = [o["away_win_odds"] for o in euro_odds_list if o.get("away_win_odds")]

    result: Dict[str, Any] = {"count": len(euro_odds_list)}

    if home_vals:
        result["均值"] = {
            "主胜": round(statistics.mean(home_vals), 3),
            "平局": round(statistics.mean(draw_vals), 3) if draw_vals else 0,
            "客胜": round(statistics.mean(away_vals), 3) if away_vals else 0,
        }
        result["中位数"] = {
            "主胜": round(statistics.median(home_vals), 3),
            "平局": round(statistics.median(draw_vals), 3) if draw_vals else 0,
            "客胜": round(statistics.median(away_vals), 3) if away_vals else 0,
        }
        # 检测离群公司（超过 IQR*1.5）
        outliers = []
        for odds in euro_odds_list:
            company = odds.get("company_name", "")
            h = odds.get("home_win_odds", 0)
            if h and home_vals:
                q1 = statistics.median(sorted(home_vals)[:len(home_vals)//2+1])
                q3 = statistics.median(sorted(home_vals)[len(home_vals)//2:])
                iqr = q3 - q1
                if h < q1 - 1.5 * iqr or h > q3 + 1.5 * iqr:
                    outliers.append(company)
        result["离群公司"] = list(set(outliers))
    else:
        result["均值"] = {}
        result["中位数"] = {}
        result["离群公司"] = []

    return result


def analyze_euro_asian_consistency(
    euro_implied: Dict[str, float],
    asian_direction: str,
) -> str:
    p_home = euro_implied.get("p_home", 0)
    p_away = euro_implied.get("p_away", 0)
    if not p_home or not p_away:
        return "数据不足"
    euro_dir = "主队" if p_home > p_away + 5 else ("客队" if p_away > p_home + 5 else "中立")
    if euro_dir == "中立" or asian_direction == "中立":
        return "中立"
    if euro_dir == asian_direction:
        return "一致"
    return "分歧"


def _extract_euro_odds(match_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    odds_data = match_data.get("赔率变化数据", {})
    result = []
    for company, types in odds_data.items():
        euro_list = types.get("欧指", [])
        if euro_list:
            latest = euro_list[-1] if euro_list else {}
            result.append({
                "company_name": company,
                "home_win_odds": float(latest.get("home_win_odds", latest.get("current_left", 0)) or 0),
                "draw_odds": float(latest.get("draw_odds", latest.get("current_middle", 0)) or 0),
                "away_win_odds": float(latest.get("away_win_odds", latest.get("current_right", 0)) or 0),
                "changes": euro_list,
            })
    return result


def _extract_asian_odds(match_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    odds_data = match_data.get("赔率变化数据", {})
    result = []
    for company, types in odds_data.items():
        asian_list = types.get("亚盘", [])
        if asian_list:
            latest = asian_list[-1] if asian_list else {}
            result.append({
                "company_name": company,
                "home_win_odds": float(latest.get("home_win_odds", latest.get("current_left", 0)) or 0),
                "away_win_odds": float(latest.get("away_win_odds", latest.get("current_right", 0)) or 0),
                "handicap": latest.get("handicap", latest.get("ovalue0", "")),
                "changes": asian_list,
            })
    return result


def _extract_ou_odds(match_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    odds_data = match_data.get("赔率变化数据", {})
    result = []
    for company, types in odds_data.items():
        ou_list = types.get("大小球", [])
        if ou_list:
            latest = ou_list[-1] if ou_list else {}
            result.append({
                "company_name": company,
                "over_odds": float(latest.get("home_win_odds", latest.get("current_left", 0)) or 0),
                "under_odds": float(latest.get("away_win_odds", latest.get("current_right", 0)) or 0),
                "line": latest.get("handicap", latest.get("ovalue0", "")),
                "changes": ou_list,
            })
    return result


def _detect_movements(odds_list: List[Dict[str, Any]], odds_type: str) -> List[str]:
    alerts = []
    for odds in odds_list:
        changes = odds.get("changes", [])
        if len(changes) < 2:
            continue
        first = changes[0]
        last = changes[-1]
        if odds_type == "欧指":
            initial = float(first.get("home_win_odds", first.get("current_left", 0)) or 0)
            current = float(last.get("home_win_odds", last.get("current_left", 0)) or 0)
        elif odds_type == "亚盘":
            initial = float(first.get("home_win_odds", first.get("current_left", 0)) or 0)
            current = float(last.get("home_win_odds", last.get("current_left", 0)) or 0)
        else:
            initial = float(first.get("over_odds", first.get("home_win_odds", first.get("current_left", 0)) or 0) or 0)
            current = float(last.get("over_odds", last.get("home_win_odds", last.get("current_left", 0)) or 0) or 0)

        movement = detect_odds_movement(initial, current)
        if movement["changed"]:
            company = odds.get("company_name", "")
            alerts.append(f"{company} {odds_type} {movement['direction']} {abs(movement['幅度'])}%")
    return alerts


def _determine_asian_direction(asian_list: List[Dict[str, Any]]) -> str:
    if not asian_list:
        return "中立"
    home_total = sum(o.get("home_win_odds", 0) for o in asian_list)
    away_total = sum(o.get("away_win_odds", 0) for o in asian_list)
    if home_total > away_total * 1.05:
        return "主队"
    if away_total > home_total * 1.05:
        return "客队"
    return "中立"


def _determine_ou_direction(ou_list: List[Dict[str, Any]]) -> str:
    if not ou_list:
        return "中立"
    over_total = sum(o.get("over_odds", 0) for o in ou_list)
    under_total = sum(o.get("under_odds", 0) for o in ou_list)
    if over_total > under_total * 1.05:
        return "大球"
    if under_total > over_total * 1.05:
        return "小球"
    return "中立"


def generate_odds_summary(match_dir: Path) -> Dict[str, Any]:
    match_data = load_match_data(match_dir)
    meta = match_data.get("赛事信息", {})

    euro_list = _extract_euro_odds(match_data)
    asian_list = _extract_asian_odds(match_data)
    ou_list = _extract_ou_odds(match_data)

    euro_comparison = compare_bookmakers(euro_list)

    # 使用均值计算隐含概率
    avg = euro_comparison.get("均值", {})
    euro_implied = calc_implied_probability(
        avg.get("主胜", 0), avg.get("平局", 0), avg.get("客胜", 0)
    ) if avg else {}

    asian_direction = _determine_asian_direction(asian_list)
    ou_direction = _determine_ou_direction(ou_list)

    consistency = analyze_euro_asian_consistency(euro_implied, asian_direction) if euro_implied else "数据不足"

    movement_alerts = []
    movement_alerts.extend(_detect_movements(euro_list, "欧指"))
    movement_alerts.extend(_detect_movements(asian_list, "亚盘"))
    movement_alerts.extend(_detect_movements(ou_list, "大小球"))

    return {
        "match_id": meta.get("match_id", ""),
        "home_team": meta.get("home_team", ""),
        "away_team": meta.get("away_team", ""),
        "euro_implied": euro_implied,
        "euro_comparison": euro_comparison,
        "asian_direction": asian_direction,
        "ou_direction": ou_direction,
        "euro_asian_consistency": consistency,
        "movement_alerts": movement_alerts,
        "bookmaker_outliers": euro_comparison.get("离群公司", []),
    }


def generate_odds_report(match_dir: Path) -> str:
    summary = generate_odds_summary(match_dir)
    lines = [
        f"赔率分析报告: {summary['home_team']} vs {summary['away_team']}",
        "=" * 50,
    ]

    implied = summary.get("euro_implied", {})
    if implied:
        lines.extend([
            "",
            "【欧赔隐含概率（去水）】",
            f"  主胜: {implied.get('p_home', 0)}%",
            f"  平局: {implied.get('p_draw', 0)}%",
            f"  客胜: {implied.get('p_away', 0)}%",
            f"  返还率 margin: {implied.get('margin', 0)}%",
        ])

    comp = summary.get("euro_comparison", {})
    avg = comp.get("均值", {})
    if avg:
        lines.extend([
            "",
            "【多公司欧赔均值】",
            f"  主胜: {avg.get('主胜', 0)}  平局: {avg.get('平局', 0)}  客胜: {avg.get('客胜', 0)}",
            f"  公司数: {comp.get('count', 0)}",
        ])

    outliers = comp.get("离群公司", [])
    if outliers:
        lines.append(f"  离群公司: {', '.join(outliers)}")

    lines.extend([
        "",
        "【亚盘方向】: " + summary.get("asian_direction", ""),
        "【大小球方向】: " + summary.get("ou_direction", ""),
        "【欧亚一致性】: " + summary.get("euro_asian_consistency", ""),
    ])

    alerts = summary.get("movement_alerts", [])
    if alerts:
        lines.extend(["", "【赔率异常波动】"])
        for alert in alerts:
            lines.append(f"  - {alert}")

    return "\n".join(lines)
