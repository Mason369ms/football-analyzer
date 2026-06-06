"""调用 match-odds-predictor skill 进行赔率预测"""

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from football_sim.data_sources.match_store import pack_match_dir_to_zip


def call_match_odds_predictor(match_dir: Path) -> Dict[str, Any]:
    """
    调用 match-odds-predictor skill 进行赔率预测（仅本地数据）

    Args:
        match_dir: 赛事数据目录

    Returns:
        预测结果字典，包含：
        - win_draw_lose: 胜平负预测
        - total_goals: 总进球预测
        - score_prediction: 比分预测
        - confidence: 置信度
    """
    from football_sim.data_sources.match_store import load_match_data
    from football_sim.analysis.odds_analyzer import generate_odds_summary

    # 加载本地数据
    match_data = load_match_data(match_dir)
    odds_summary = generate_odds_summary(match_dir)
    meta = match_data.get("赛事信息", {})

    # 基于本地赔率数据生成预测（模拟 skill 输出）
    prediction = _generate_local_prediction(match_data, odds_summary, meta)

    return prediction


def _generate_local_prediction(
    match_data: Dict[str, Any],
    odds_summary: Dict[str, Any],
    meta: Dict[str, Any],
) -> Dict[str, Any]:
    """
    基于本地赔率数据生成预测（模拟 match-odds-predictor skill 输出）

    这是一个简化版本，实际 skill 会融合 Polymarket/odds-api-io 数据。
    """
    euro_implied = odds_summary.get("euro_implied", {})
    asian_direction = odds_summary.get("asian_direction", "")
    ou_direction = odds_summary.get("ou_direction", "")
    consistency = odds_summary.get("euro_asian_consistency", "")

    # 基于欧赔隐含概率判断胜平负方向
    p_home = euro_implied.get("p_home", 0)
    p_draw = euro_implied.get("p_draw", 0)
    p_away = euro_implied.get("p_away", 0)

    if p_home >= p_draw and p_home >= p_away:
        outcome = "主胜"
        outcome_prob = p_home
    elif p_away >= p_draw and p_away >= p_home:
        outcome = "客胜"
        outcome_prob = p_away
    else:
        outcome = "平局"
        outcome_prob = p_draw

    # 计算置信度
    confidence = int(outcome_prob)
    if consistency == "一致":
        confidence = min(100, confidence + 5)
    elif consistency == "分歧":
        confidence = max(0, confidence - 5)

    # 总进球预测（基于大小球方向）
    total_goals = "2-3球"
    if ou_direction and "大" in ou_direction:
        total_goals = "3球以上"
    elif ou_direction and "小" in ou_direction:
        total_goals = "2球以下"

    # 比分预测（简化）
    if outcome == "主胜":
        score_prediction = "2-1" if p_home < 60 else "2-0"
    elif outcome == "客胜":
        score_prediction = "1-2" if p_away < 60 else "0-2"
    else:
        score_prediction = "1-1"

    return {
        "match_id": meta.get("match_id", ""),
        "home_team": meta.get("home_team", ""),
        "away_team": meta.get("away_team", ""),
        "league": meta.get("league", ""),
        "prediction": {
            "win_draw_lose": {
                "outcome": outcome,
                "probability": round(outcome_prob, 1),
                "home_prob": p_home,
                "draw_prob": p_draw,
                "away_prob": p_away,
            },
            "total_goals": {
                "prediction": total_goals,
                "direction": ou_direction or "中立",
            },
            "score_prediction": score_prediction,
        },
        "confidence": confidence,
        "data_source": "local_odds",
        "notes": [
            f"亚盘方向: {asian_direction or '未知'}",
            f"欧亚一致性: {consistency or '未知'}",
        ],
    }
