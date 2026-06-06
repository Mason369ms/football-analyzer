import json
import re
from pathlib import Path
from typing import Any, Dict, Generator, Optional, Tuple

import httpx

from football_sim.analysis.odds_analyzer import generate_odds_summary
from football_sim.data_sources.match_store import load_match_data, match_dir_to_match
from football_sim.models import MatchAnalysis
from football_sim.prompts.match_analysis import SYSTEM_PROMPT, build_odds_intent_prompt, build_user_prompt

# 未配置 LLM 时的提示信息
LLM_NOT_CONFIGURED_MSG = """
⚠️ 未配置 LLM API，无法进行分析。

请在仪表盘的「AI 配置」区域填写以下信息：
  • Provider: 如 openai、deepseek 等
  • Base URL: 如 https://api.openai.com/v1
  • Model: 如 gpt-4、deepseek-chat 等
  • API Key: 你的 API 密钥（必填）

填写完成后点击「保存配置」，然后重新点击分析按钮。

💡 快速设置 API Key：
   PYTHONPATH='src' python scripts/set_api_key.py
"""


def _check_llm_config(llm_config: Dict[str, str]) -> bool:
    """检查 LLM 配置是否完整"""
    base_url = llm_config.get("llm_base_url", "").strip()
    model = llm_config.get("llm_model", "").strip()
    api_key = llm_config.get("llm_api_key", "").strip()
    return bool(base_url and model and api_key)


def _get_llm_config(db_path: Path) -> Dict[str, str]:
    from football_sim.history_db import load_dashboard_config
    return load_dashboard_config(db_path)


def call_llm(
    system_prompt: str,
    user_prompt: str,
    llm_config: Dict[str, str],
    max_tokens: int = 8000,
) -> str:
    base_url = llm_config.get("llm_base_url", "").rstrip("/")
    model = llm_config.get("llm_model", "").strip()
    api_key = llm_config.get("llm_api_key", "").strip()

    if not base_url or not model:
        raise ValueError("未配置 LLM API（请在仪表盘配置页面设置 base_url 和 model）")

    if not api_key:
        raise ValueError(
            "未配置 API Key！\n"
            "请在仪表盘的「AI 配置」页面填写 API Key，\n"
            "或运行: PYTHONPATH='src' python scripts/set_api_key.py"
        )

    url = f"{base_url}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }

    try:
        with httpx.Client(timeout=120) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as e:
        # 提供更详细的错误信息
        error_msg = f"LLM API 调用失败: {e.response.status_code}"
        try:
            error_detail = e.response.json()
            if "error" in error_detail:
                error_msg += f" - {error_detail['error'].get('message', '')}"
        except:
            error_msg += f" - {e.response.text[:200]}"
        raise ValueError(error_msg) from e


def call_llm_stream(
    system_prompt: str,
    user_prompt: str,
    llm_config: Dict[str, str],
    max_tokens: int = 8000,
) -> Generator[str, None, None]:
    base_url = llm_config.get("llm_base_url", "").rstrip("/")
    model = llm_config.get("llm_model", "").strip()
    api_key = llm_config.get("llm_api_key", "").strip()

    if not base_url or not model:
        raise ValueError("未配置 LLM API")

    url = f"{base_url}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.3,
        "stream": True,
    }

    try:
        with httpx.Client(timeout=120) as client:
            with client.stream("POST", url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue
    except httpx.HTTPStatusError as e:
        error_msg = f"LLM API 流式调用失败: {e.response.status_code}"
        try:
            error_detail = e.response.json()
            if "error" in error_detail:
                error_msg += f" - {error_detail['error'].get('message', '')}"
        except:
            error_msg += f" - {e.response.text[:200]}"
        raise ValueError(error_msg) from e


def analyze_match(match_dir: Path, llm_config: Dict[str, str], use_full_data: bool = True) -> MatchAnalysis:
    match_dir = Path(match_dir)
    match_data = load_match_data(match_dir)
    meta = match_data.get("赛事信息", {})

    # 检查 LLM 配置
    if not _check_llm_config(llm_config):
        return MatchAnalysis(
            match_id=meta.get("match_id", ""),
            home_team=meta.get("home_team", ""),
            away_team=meta.get("away_team", ""),
            league=meta.get("league", ""),
            analysis_text=LLM_NOT_CONFIGURED_MSG,
            brief_text="未配置 LLM API",
            prediction_json={},
            confidence=0,
        )

    # 调用 skill 获取赔率预测
    skill_prediction = {}
    try:
        from football_sim.analysis.skill_predictor import call_match_odds_predictor
        skill_prediction = call_match_odds_predictor(match_dir)
    except Exception as e:
        print(f"Skill 预测失败（将使用纯 LLM 分析）: {e}")

    odds_summary = generate_odds_summary(match_dir)
    user_prompt = build_user_prompt(match_data, odds_summary, skill_prediction=skill_prediction, use_full_data=use_full_data)
    result_text = call_llm(SYSTEM_PROMPT, user_prompt, llm_config)

    # 尝试从结果中提取 JSON 部分
    prediction_json = _extract_json_from_text(result_text)

    # 提取置信度（兼容多种 JSON 格式）
    confidence = _extract_confidence(prediction_json)

    return MatchAnalysis(
        match_id=meta.get("match_id", ""),
        home_team=meta.get("home_team", ""),
        away_team=meta.get("away_team", ""),
        league=meta.get("league", ""),
        analysis_text=result_text,
        brief_text=_extract_brief(result_text),
        prediction_json=prediction_json,
        confidence=confidence,
    )


def analyze_match_stream(match_dir: Path, llm_config: Dict[str, str], use_full_data: bool = True) -> Generator[str, None, None]:
    # 检查 LLM 配置
    if not _check_llm_config(llm_config):
        yield LLM_NOT_CONFIGURED_MSG
        return

    match_dir = Path(match_dir)
    match_data = load_match_data(match_dir)
    odds_summary = generate_odds_summary(match_dir)
    user_prompt = build_user_prompt(match_data, odds_summary, use_full_data=use_full_data)
    yield from call_llm_stream(SYSTEM_PROMPT, user_prompt, llm_config)


def analyze_odds_intent(match_dir: Path, llm_config: Dict[str, str], use_full_data: bool = True) -> str:
    # 检查 LLM 配置
    if not _check_llm_config(llm_config):
        return LLM_NOT_CONFIGURED_MSG

    match_dir = Path(match_dir)
    match_data = load_match_data(match_dir)
    odds_summary = generate_odds_summary(match_dir)
    user_prompt = build_odds_intent_prompt(match_data, odds_summary, use_full_data=use_full_data)
    system = "你是赔率分析专家。基于提供的赔率数据，分析庄家意图和投注建议。"
    return call_llm(system, user_prompt, llm_config, max_tokens=4000)


def batch_analyze(
    date_dir: Path,
    llm_config: Dict[str, str],
    match_dirs: Optional[list] = None,
    use_full_data: bool = True,
) -> list:
    from football_sim.data_sources.match_store import list_match_dirs

    if match_dirs is None:
        match_dirs = list_match_dirs(date_dir)

    results = []
    for match_dir in match_dirs:
        try:
            analysis = analyze_match(match_dir, llm_config, use_full_data=use_full_data)
            results.append(analysis)
            print(f"  分析完成: {analysis.home_team} vs {analysis.away_team}")
        except Exception as e:
            print(f"  分析失败: {match_dir.name} -> {e}")
    return results


def _try_parse_json_candidates(text: str) -> Dict[str, Any]:
    """用括号计数法找到文本中所有顶级 JSON 候选，返回最大的有效 JSON dict。"""
    candidates: list = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == '{':
            depth = 0
            start = i
            in_string = False
            escape = False
            while i < n:
                ch = text[i]
                if escape:
                    escape = False
                elif ch == '\\' and in_string:
                    escape = True
                elif ch == '"' and not escape:
                    in_string = not in_string
                elif not in_string:
                    if ch == '{':
                        depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0:
                            candidates.append(text[start:i + 1])
                            break
                i += 1
        i += 1

    # 按长度降序排列，取最大的有效 JSON
    candidates.sort(key=len, reverse=True)
    for candidate in candidates:
        try:
            result = json.loads(candidate)
            if isinstance(result, dict) and len(result) >= 2:
                return result
        except json.JSONDecodeError:
            continue
    # 降级：返回任何有效 JSON（即使字段少）
    for candidate in candidates:
        try:
            result = json.loads(candidate)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            continue
    return {}


def _extract_json_from_text(text: str) -> Dict[str, Any]:
    import re

    # 策略1: 匹配 ```json ... ``` 代码块
    json_pattern = r'```json\s*(.*?)\s*```'
    match = re.search(json_pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 策略2: 匹配各种中文标记后的 JSON
    alt_markers = [
        r'【\s*C版\s*(?:JSON|json)?\s*】\s*',
        r'【\s*机器可读\s*(?:JSON|json)?\s*】\s*',
        r'C\s*\)\s*',
        r'###\s*C\s*',
        r'【\s*结构化预测\s*】\s*',
    ]
    for marker in alt_markers:
        m = re.search(marker + r'(\{.*)', text, re.DOTALL)
        if m:
            candidate = m.group(1)
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                # 标记后的文本可能只含部分 JSON，用括号计数法截取
                result = _try_parse_json_candidates(candidate)
                if result:
                    return result

    # 策略3: 括号计数法全文扫描
    result = _try_parse_json_candidates(text)
    if result:
        return result

    return {}


def _extract_confidence(prediction_json: Dict[str, Any]) -> int:
    """从 prediction_json 中提取置信度，兼容多种 JSON 格式"""
    # 格式1: 根级别 confidence
    confidence = prediction_json.get("confidence")
    if isinstance(confidence, (int, float)):
        return int(confidence)
    # 格式1b: confidence 是字典，取 overall 值
    if isinstance(confidence, dict) and isinstance(confidence.get("overall"), (int, float)):
        return int(confidence["overall"])

    # 格式1c: confidence_metrics 字典
    confidence_metrics = prediction_json.get("confidence_metrics")
    if isinstance(confidence_metrics, dict):
        if isinstance(confidence_metrics.get("overall"), (int, float)):
            return int(confidence_metrics["overall"])
        if isinstance(confidence_metrics.get("confidence"), (int, float)):
            return int(confidence_metrics["confidence"])
        # 尝试任意以 confidence 或 score 结尾的键
        for key in confidence_metrics:
            if "confidence" in key.lower() or "score" in key.lower():
                val = confidence_metrics[key]
                if isinstance(val, (int, float)):
                    return int(val)

    # 格式2: prediction.confidence_score 或 prediction.confidence
    prediction = prediction_json.get("prediction", {})
    if isinstance(prediction, dict):
        if isinstance(prediction.get("confidence_score"), (int, float)):
            return int(prediction["confidence_score"])
        if isinstance(prediction.get("confidence"), (int, float)):
            return int(prediction["confidence"])
        # prediction.confidence 是字典
        pred_conf = prediction.get("confidence")
        if isinstance(pred_conf, dict) and isinstance(pred_conf.get("overall"), (int, float)):
            return int(pred_conf["overall"])

    # 格式3: analysis_summary.confidence
    summary = prediction_json.get("analysis_summary", {})
    if isinstance(summary, dict):
        if isinstance(summary.get("confidence"), (int, float)):
            return int(summary["confidence"])

    return 0


def _extract_brief(text: str) -> str:
    lines = text.split("\n")
    brief_lines = []
    in_brief = False
    for line in lines:
        lower = line.lower().strip()
        if "精简" in lower or "简版" in lower or "投放" in lower or "b." in lower:
            in_brief = True
            continue
        if in_brief:
            if line.strip().startswith("#") or "机器可读" in lower or "json" in lower or "c." in lower:
                break
            if line.strip():
                brief_lines.append(line.strip())
    return "\n".join(brief_lines[:5]) if brief_lines else text[:200]


# ── 预测结果提取（兼容 LLM 多种输出格式） ──────────────────────────

_OUTCOME_KEYS = {
    "outcome", "direction", "prediction", "result",
    "胜平负", "方向", "推荐方向", "推荐", "核心方向",
    "recommended_outcome", "predicted_outcome", "match_outcome",
    "win_draw_lose", "主客方向",
}

_OUTCOME_VALUES = {
    "主胜", "平局", "客胜",
    "home_win", "draw", "away_win",
    "home", "draw", "away",
    "h", "d", "a",
    "1", "x", "2",
}

_OUTCOME_MAP = {
    "home_win": "主胜", "draw": "平局", "away_win": "客胜",
    "home": "主胜", "away": "客胜",
    "h": "主胜", "d": "平局", "a": "客胜",
    "1": "主胜", "x": "平局", "2": "客胜",
    "主胜": "主胜", "平局": "平局", "客胜": "客胜",
}

_SCORE_KEYS = {
    "score_prediction", "score", "predicted_score", "scoreline",
    "比分", "比分预测", "推荐比分", "核心比分", "预测比分",
    "recommended_score", "predicted_scoreline", "exact_score",
}

_GOALS_KEYS = {
    "total_goals", "goals", "predicted_goals", "goal_count",
    "进球数", "总进球", "进球预测", "总进球数", "预测进球",
    "进球", "total", "over_under",
}


def _normalize_outcome(raw: str) -> str:
    """将各种 outcome 表示统一为中文"""
    if not raw:
        return ""
    s = str(raw).strip()
    # 直接匹配
    if s in _OUTCOME_MAP:
        return _OUTCOME_MAP[s]
    # 包含匹配
    lower = s.lower()
    if "主胜" in s or "home_win" in lower or lower == "home":
        return "主胜"
    if "客胜" in s or "away_win" in lower or lower == "away":
        return "客胜"
    if "平局" in s or "draw" in lower:
        return "平局"
    # 尝试只取第一个有效值（可能格式如 "主胜(55%)"）
    m = re.search(r'(主胜|平局|客胜|home_win|draw|away_win)', s, re.IGNORECASE)
    if m:
        return _OUTCOME_MAP.get(m.group(1).lower(), m.group(1))
    return s


def _find_outcome_in_dict(d: Dict[str, Any], depth: int = 0) -> str:
    """递归搜索 dict 中匹配预测方向的字段"""
    if depth > 5 or not isinstance(d, dict):
        return ""
    for key, val in d.items():
        key_lower = key.lower() if isinstance(key, str) else ""
        # key 匹配
        if key_lower in _OUTCOME_KEYS or any(k in key_lower for k in ("outcome", "方向", "推荐", "胜平负", "prediction")):
            if isinstance(val, str) and val.strip():
                normalized = _normalize_outcome(val)
                if normalized in ("主胜", "平局", "客胜"):
                    return normalized
            if isinstance(val, dict):
                result = _find_outcome_in_dict(val, depth + 1)
                if result:
                    return result
        # 值是 dict → 继续递归
        if isinstance(val, dict):
            result = _find_outcome_in_dict(val, depth + 1)
            if result:
                return result
    return ""


def _find_score_in_dict(d: Dict[str, Any], depth: int = 0) -> str:
    """递归搜索 dict 中匹配比分预测的字段"""
    if depth > 5 or not isinstance(d, dict):
        return ""
    for key, val in d.items():
        key_lower = key.lower() if isinstance(key, str) else ""
        # key 匹配比分相关
        if key_lower in _SCORE_KEYS or any(k in key_lower for k in ("score", "比分", "scoreline")):
            if isinstance(val, str) and re.match(r'\d{1,2}[-:]\d{1,2}', val.strip()):
                return val.strip().replace(":", "-")
            if isinstance(val, (list, tuple)) and len(val) == 2:
                try:
                    return f"{int(val[0])}-{int(val[1])}"
                except (ValueError, TypeError):
                    pass
        # 值是 dict → 继续递归
        if isinstance(val, dict):
            result = _find_score_in_dict(val, depth + 1)
            if result:
                return result
    return ""


def _find_goals_in_dict(d: Dict[str, Any], depth: int = 0) -> str:
    """递归搜索 dict 中匹配总进球预测的字段"""
    if depth > 5 or not isinstance(d, dict):
        return ""
    for key, val in d.items():
        key_lower = key.lower() if isinstance(key, str) else ""
        # key 匹配进球相关
        if key_lower in _GOALS_KEYS or any(k in key_lower for k in ("goal", "进球", "total_goal")):
            if isinstance(val, str) and val.strip():
                # 标准化：提取数字或常见格式如 "2-3球" / "3球以上" / "2球以下" / "大2.5" / "小2.5"
                return val.strip()
            if isinstance(val, (int, float)):
                return str(int(val))
            if isinstance(val, dict) and depth < 4:
                # 常见嵌套: total_goals.prediction / total_goals.direction
                pred = val.get("prediction", val.get("direction", ""))
                if isinstance(pred, str) and pred.strip():
                    return pred.strip()
                if isinstance(pred, (int, float)):
                    return str(int(pred))
        # 值是 dict → 继续递归
        if isinstance(val, dict):
            result = _find_goals_in_dict(val, depth + 1)
            if result:
                return result
    return ""


def _extract_prediction_from_text(text: str) -> Tuple[str, str, str]:
    """从 analysis_text 中用正则提取预测方向、比分和进球数（JSON 完全解析失败时的兜底）"""
    outcome = ""
    score = ""
    goals = ""

    # 提取方向
    patterns_outcome = [
        r'(?:方向|推荐方向|胜平负|核心方向|推荐)[：:\s]*(主胜|平局|客胜)',
        r'(?:outcome|prediction|direction)[：:\s]*(home_win|draw|away_win)',
    ]
    for pat in patterns_outcome:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            outcome = _normalize_outcome(m.group(1))
            break

    # 提取比分
    patterns_score = [
        r'(?:比分|比分预测|推荐比分|核心比分|预测比分)[：:\s]*(\d{1,2}[-:]\d{1,2})',
        r'(?:score|scoreline|predicted_score)[：:\s]*(\d{1,2}[-:]\d{1,2})',
    ]
    for pat in patterns_score:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            score = m.group(1).replace(":", "-")
            break

    # 提取进球数
    patterns_goals = [
        r'(?:进球数|总进球|进球预测|总进球数|预测进球)[：:\s]*(\d{1,2}(?:[-~]\d{1,2})?球?(?:以上|以下)?)',
        r'(?:total[_ ]?goals|predicted[_ ]?goals)[：:\s]*(\d{1,2}(?:[-~]\d{1,2})?)',
    ]
    for pat in patterns_goals:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            goals = m.group(1)
            break

    return outcome, score, goals


def _extract_prediction_from_json(
    prediction_json: Dict[str, Any],
    analysis_text: str = "",
) -> Tuple[str, str, str]:
    """从各种 JSON 格式中提取 prediction_outcome, prediction_score, prediction_goals

    当 JSON 为空时，回退到 analysis_text 正则提取。
    """
    outcome = ""
    score = ""
    goals = ""

    def _normalize_score(raw: Any) -> str:
        """将各种比分格式标准化为 'X-Y' 字符串"""
        if isinstance(raw, str):
            s = raw.strip().replace(":", "-")
            if re.match(r'^\d{1,2}-\d{1,2}$', s):
                return s
            return s
        if isinstance(raw, (list, tuple)) and len(raw) == 2:
            try:
                return f"{int(raw[0])}-{int(raw[1])}"
            except (ValueError, TypeError):
                pass
        return ""

    # ── 已有路径（最高优先级） ──
    pred = prediction_json.get("prediction", {})
    if isinstance(pred, dict):
        # 路径1: prediction.outcome
        if pred.get("outcome"):
            outcome = pred["outcome"]
        # 路径2: prediction.win_draw_lose.outcome
        wdl = pred.get("win_draw_lose", {})
        if isinstance(wdl, dict) and wdl.get("outcome") and not outcome:
            outcome = wdl["outcome"]
        # 比分
        raw_score = pred.get("score_prediction", "") or pred.get("score", "")
        if raw_score:
            score = _normalize_score(raw_score)
        # 进球数
        raw_goals = pred.get("total_goals", "")
        if raw_goals:
            if isinstance(raw_goals, dict):
                goals = str(raw_goals.get("prediction", raw_goals.get("direction", "")))
            elif isinstance(raw_goals, (int, float)):
                goals = str(int(raw_goals))
            elif isinstance(raw_goals, str):
                goals = raw_goals.strip()

    # ── 广泛 key 搜索 ──
    if not outcome:
        outcome = _find_outcome_in_dict(prediction_json)
    if not score:
        score = _find_score_in_dict(prediction_json)
    if not goals:
        goals = _find_goals_in_dict(prediction_json)

    # ── 标准化 ──
    outcome = _normalize_outcome(outcome)

    # ── 兜底：从 analysis_text 正则提取 ──
    if not outcome or not score or not goals:
        text_outcome, text_score, text_goals = _extract_prediction_from_text(analysis_text)
        if not outcome:
            outcome = text_outcome
        if not score:
            score = text_score
        if not goals:
            goals = text_goals

    return outcome, score, goals
