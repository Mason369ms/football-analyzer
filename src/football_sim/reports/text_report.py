from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from football_sim.analysis.odds_analyzer import generate_odds_summary
from football_sim.data_sources.match_store import load_match_data
from football_sim.models import MatchAnalysis


def generate_analysis_report(analysis: MatchAnalysis, output_dir: Optional[Path] = None) -> str:
    """生成分析报告文本"""
    lines = [
        f"足球赛事分析报告",
        f"=" * 50,
        f"",
        f"【赛事信息】",
        f"  联赛: {analysis.league}",
        f"  对阵: {analysis.home_team} vs {analysis.away_team}",
        f"  时间: {analysis.created_at or datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"  置信度: {analysis.confidence}/100",
        f"",
        f"【分析正文】",
        analysis.analysis_text,
    ]

    if analysis.brief_text:
        lines.extend([
            f"",
            f"【精简版】",
            analysis.brief_text,
        ])

    if analysis.prediction_json:
        import json
        lines.extend([
            f"",
            f"【结构化预测】",
            json.dumps(analysis.prediction_json, ensure_ascii=False, indent=2),
        ])

    report = "\n".join(lines)

    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = f"{analysis.league}_{analysis.home_team}_vs_{analysis.away_team}".replace(" ", "_")
        safe_name = "".join(c for c in safe_name if c.isalnum() or c in "_-")
        filename = f"analysis_{timestamp}_{safe_name}.txt"
        (output_dir / filename).write_text(report, encoding="utf-8")

    return report


def generate_match_summary(match_dir: Path) -> str:
    """生成单场比赛数据摘要"""
    match_data = load_match_data(match_dir)
    meta = match_data.get("赛事信息", {})

    lines = [
        f"赛事数据摘要",
        f"=" * 40,
        f"",
        f"赛事ID: {meta.get('match_id', '')}",
        f"联赛: {meta.get('league', '')}",
        f"对阵: {meta.get('home_team', '')} vs {meta.get('away_team', '')}",
        f"时间: {meta.get('match_time', '')}",
        f"",
    ]

    # 赔率摘要
    odds_summary = generate_odds_summary(match_dir)
    if odds_summary:
        euro = odds_summary.get("euro_implied", {})
        if euro:
            lines.extend([
                f"【欧赔隐含概率】",
                f"  主胜: {euro.get('p_home', 0)}%",
                f"  平局: {euro.get('p_draw', 0)}%",
                f"  客胜: {euro.get('p_away', 0)}%",
                f"  返还率: {euro.get('margin', 0)}%",
                f"",
            ])

        lines.extend([
            f"【方向判断】",
            f"  亚盘: {odds_summary.get('asian_direction', '')}",
            f"  大小球: {odds_summary.get('ou_direction', '')}",
            f"  欧亚一致性: {odds_summary.get('euro_asian_consistency', '')}",
            f"",
        ])

        alerts = odds_summary.get("movement_alerts", [])
        if alerts:
            lines.append("【赔率波动警告】")
            for alert in alerts:
                lines.append(f"  - {alert}")
            lines.append("")

    # 数据文件清单
    lines.append("【已抓取数据文件】")
    for key in match_data:
        if key and key != "赛事信息":
            data = match_data[key]
            if isinstance(data, dict) and "error" not in data:
                lines.append(f"  ✓ {key}")
            elif isinstance(data, list) and data:
                lines.append(f"  ✓ {key} ({len(data)} 条)")

    return "\n".join(lines)


def generate_daily_report(date_str: str, data_dir: Path, output_dir: Optional[Path] = None) -> str:
    """生成每日汇总报告"""
    from football_sim.data_sources.match_store import list_match_dirs, match_dir_to_match

    date_dir = data_dir / date_str
    if not date_dir.exists():
        return f"未找到 {date_str} 的赛事数据"

    match_dirs = list_match_dirs(date_dir)
    if not match_dirs:
        return f"{date_str} 无赛事数据"

    lines = [
        f"每日赛事汇总报告 - {date_str}",
        f"=" * 50,
        f"",
        f"共 {len(match_dirs)} 场赛事",
        f"",
    ]

    analyzed = 0
    for match_dir in match_dirs:
        match = match_dir_to_match(match_dir)
        if not match:
            continue

        odds_summary = generate_odds_summary(match_dir)
        euro = odds_summary.get("euro_implied", {})
        asian_dir = odds_summary.get("asian_direction", "")
        ou_dir = odds_summary.get("ou_direction", "")

        lines.append(f"【{match.league}】{match.home_team} vs {match.away_team}")
        if euro:
            lines.append(f"  欧赔: 主{euro.get('p_home', 0)}% 平{euro.get('p_draw', 0)}% 客{euro.get('p_away', 0)}%")
        if asian_dir or ou_dir:
            lines.append(f"  方向: 亚盘{asian_dir} 大小球{ou_dir}")
        lines.append("")

    report = "\n".join(lines)

    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"daily_report_{date_str}.txt"
        (output_dir / filename).write_text(report, encoding="utf-8")

    return report


def export_match_data_json(match_dir: Path, output_path: Path) -> Path:
    """导出赛事数据为 JSON 文件"""
    import json

    match_data = load_match_data(match_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(match_data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    return output_path
