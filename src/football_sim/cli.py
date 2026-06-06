import argparse
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="football-sim",
        description="足球赛事数据分析系统",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # fetch-matches
    fetch = subparsers.add_parser("fetch-matches", help="抓取赛事列表")
    fetch.add_argument("--date", default="today", help="日期（today 或 YYYY-MM-DD）")
    fetch.add_argument("--with-odds", action="store_true", help="同时抓取赔率和详情数据")
    fetch.add_argument("--output", default="data/matches", help="输出目录")
    fetch.add_argument("--db-path", default="", help="数据库路径（默认 data/users/default/history.sqlite3）")
    fetch.set_defaults(func=_fetch_matches)

    # fetch-details
    details = subparsers.add_parser("fetch-details", help="抓取赛事详情和赔率")
    details.add_argument("--date", required=True, help="日期（YYYY-MM-DD）")
    details.add_argument("--match-id", default="", help="指定赛事ID（不传则抓取当日全部）")
    details.add_argument("--output", default="data/matches", help="输出目录")
    details.add_argument("--db-path", default="", help="数据库路径（默认 data/users/default/history.sqlite3）")
    details.set_defaults(func=_fetch_details)

    # analyze
    analyze = subparsers.add_parser("analyze", help="LLM 分析赛事")
    analyze.add_argument("--date", default="", help="日期（YYYY-MM-DD）")
    analyze.add_argument("--match-dir", default="", help="单场赛事数据目录")
    analyze.add_argument("--match-id", default="", help="赛事ID（从数据库查询对应目录）")
    analyze.add_argument("--match-ids", default="", help="多个赛事ID，用逗号分隔（批量分析）")
    analyze.add_argument("--db-path", default="", help="数据库路径（默认 data/users/default/history.sqlite3）")
    analyze.add_argument("--odds-only", action="store_true", help="仅分析赔率意图")
    analyze.add_argument("--truncated", action="store_true", help="使用截断模式（适用于 token 受限的模型，默认使用完整数据）")
    analyze.set_defaults(func=_analyze)

    # odds-report
    odds = subparsers.add_parser("odds-report", help="生成赔率分析报告")
    odds.add_argument("--date", default="today", help="日期")
    odds.add_argument("--match-dir", default="", help="单场赛事数据目录")
    odds.set_defaults(func=_odds_report)

    # fetch-results
    results_cmd = subparsers.add_parser("fetch-results", help="获取比赛结果")
    results_cmd.add_argument("--match-id", default="", help="指定赛事ID")
    results_cmd.add_argument("--date", default="", help="获取指定日期所有已分析赛事的结果")
    results_cmd.add_argument("--db-path", default="", help="数据库路径（默认 data/users/default/history.sqlite3）")
    results_cmd.set_defaults(func=_fetch_results)

    # dashboard
    dash = subparsers.add_parser("dashboard", help="启动 Web 仪表盘")
    dash.add_argument("--reports", default="reports/latest", help="报告目录")
    dash.add_argument("--host", default="127.0.0.1", help="监听地址")
    dash.add_argument("--port", type=int, default=8765, help="监听端口")
    dash.add_argument("--server", choices=("auto", "stdlib", "fastapi"), default="auto", help="Web服务类型")
    dash.add_argument("--open", dest="open_browser", action="store_true", help="自动打开浏览器")
    dash.add_argument("--no-open", dest="open_browser", action="store_false", help="不自动打开浏览器")
    dash.set_defaults(func=_dashboard, open_browser=False)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


def _fetch_matches(args) -> None:
    from football_sim.data_sources.match_fetcher import fetch_and_parse_matches
    from football_sim.data_sources.match_store import save_match_data
    from football_sim.data_sources.odds_fetcher import fetch_all_matches_data
    from football_sim.history_db import init_history_db, record_match

    date_str = args.date
    if date_str == "today":
        date_str = datetime.now().strftime("%Y-%m-%d")

    print(f"抓取 {date_str} 赛事列表...")
    matches = fetch_and_parse_matches(date_str)
    print(f"共 {len(matches)} 场赛事")

    if not matches:
        return

    base_dir = Path(args.output) / date_str
    db_path = Path(args.db_path) if args.db_path else Path("data/users") / "default" / "history.sqlite3"
    init_history_db(db_path)

    if args.with_odds:
        print("抓取赔率和详情数据...")
        results = asyncio.run(fetch_all_matches_data(matches))
        for match, data in results:
            match_dir = save_match_data(match, data, base_dir)
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
            print(f"  已保存: {match_dir}")
    else:
        for match in matches:
            match_dir = save_match_data(match, {}, base_dir)
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
            print(f"  {match.display_name}")

    print("完成")


def _fetch_details(args) -> None:
    from football_sim.data_sources.match_fetcher import fetch_and_parse_matches
    from football_sim.data_sources.match_store import list_match_dirs, match_dir_to_match, save_match_data
    from football_sim.data_sources.odds_fetcher import fetch_all_matches_data

    date_str = args.date
    base_dir = Path(args.output) / date_str

    if args.match_id:
        # 从已有目录找到对应赛事
        match_dirs = list_match_dirs(base_dir)
        target_match = None
        for md in match_dirs:
            m = match_dir_to_match(md)
            if m and m.match_id == args.match_id:
                target_match = m
                break
        if not target_match:
            print(f"未找到赛事 {args.match_id}")
            return
        matches = [target_match]
    else:
        # 先获取赛事列表
        matches = fetch_and_parse_matches(date_str)

    print(f"抓取 {len(matches)} 场赛事详情...")
    results = asyncio.run(fetch_all_matches_data(matches))
    for match, data in results:
        match_dir = save_match_data(match, data, base_dir)
        print(f"  已保存: {match_dir}")

    print("完成")


def _analyze(args) -> None:
    from football_sim.analysis.llm_analyzer import analyze_match, analyze_odds_intent
    from football_sim.analysis.odds_analyzer import generate_odds_report
    from football_sim.data_sources.match_store import list_match_dirs
    from football_sim.history_db import load_dashboard_config, record_analysis, load_matches

    db_path = Path(args.db_path) if args.db_path else Path("data/users") / "default" / "history.sqlite3"
    llm_config = load_dashboard_config(db_path)

    # 确定数据传递模式
    use_full_data = not args.truncated
    mode_str = "完整数据" if use_full_data else "截断模式"
    print(f"📊 数据模式: {mode_str}")

    if args.match_dir:
        match_dirs = [Path(args.match_dir)]
    elif args.match_ids:
        # 批量分析多个赛事
        match_id_list = [mid.strip() for mid in args.match_ids.split(",") if mid.strip()]
        matches = load_matches(db_path, limit=1000)
        match_dirs = []
        for mid in match_id_list:
            match = next((m for m in matches if m.get("match_id") == mid), None)
            if match and match.get("data_dir"):
                match_dirs.append(Path(match["data_dir"]))
            else:
                print(f"⚠️  未找到赛事 {mid}，跳过")
        if not match_dirs:
            print("未找到任何有效赛事")
            return
    elif args.match_id:
        # 根据 match_id 从数据库查询对应的 data_dir
        matches = load_matches(db_path, limit=1000)
        match = next((m for m in matches if m.get("match_id") == args.match_id), None)
        if match and match.get("data_dir"):
            match_dirs = [Path(match["data_dir"])]
        else:
            print(f"未找到赛事 {args.match_id}")
            return
    elif args.date:
        date_dir = Path("data/matches") / args.date
        match_dirs = list_match_dirs(date_dir)
    else:
        print("请指定 --date、--match-dir、--match-id 或 --match-ids")
        return

    print(f"🏟️  共 {len(match_dirs)} 场比赛")

    success_count = 0
    fail_count = 0

    for i, match_dir in enumerate(match_dirs, 1):
        if args.odds_only:
            print(f"\n[{i}/{len(match_dirs)}] 赔率意图分析: {match_dir.name}")
            try:
                result = analyze_odds_intent(match_dir, llm_config, use_full_data=use_full_data)
                print(result)
            except Exception as e:
                print(f"  ❌ 分析失败: {e}")
                fail_count += 1
        else:
            print(f"\n[{i}/{len(match_dirs)}] 完整分析: {match_dir.name}")
            try:
                analysis = analyze_match(match_dir, llm_config, use_full_data=use_full_data)
                print(analysis.analysis_text)

                # 从 prediction_json 提取预测结果（兼容多种 LLM 输出格式）
                from football_sim.analysis.llm_analyzer import _extract_prediction_from_json
                prediction_outcome, prediction_score, prediction_goals = _extract_prediction_from_json(
                    analysis.prediction_json,
                    analysis_text=analysis.analysis_text,
                )

                record_analysis(db_path, {
                    "match_id": analysis.match_id,
                    "analysis_type": "full",
                    "home_team": analysis.home_team,
                    "away_team": analysis.away_team,
                    "league": analysis.league,
                    "confidence": analysis.confidence,
                    "prediction_json": str(analysis.prediction_json),
                    "analysis_text": analysis.analysis_text,
                    "brief_text": analysis.brief_text,
                    "created_at": datetime.now().isoformat(),
                    "prediction_outcome": prediction_outcome,
                    "prediction_score": prediction_score,
                    "prediction_goals": prediction_goals,
                    "data_mode": mode_str,
                })
                success_count += 1
                print(f"  ✅ 分析完成")
            except Exception as e:
                print(f"  ❌ 分析失败: {e}")
                fail_count += 1

    print(f"\n{'='*50}")
    print(f"📊 批量分析完成: 成功 {success_count} 场，失败 {fail_count} 场")


def _odds_report(args) -> None:
    from football_sim.analysis.odds_analyzer import generate_odds_report
    from football_sim.data_sources.match_store import list_match_dirs

    if args.match_dir:
        print(generate_odds_report(Path(args.match_dir)))
        return

    date_str = args.date
    if date_str == "today":
        date_str = datetime.now().strftime("%Y-%m-%d")

    date_dir = Path("data/matches") / date_str
    match_dirs = list_match_dirs(date_dir)
    if not match_dirs:
        print(f"未找到 {date_str} 的赛事数据")
        return

    for match_dir in match_dirs:
        try:
            report = generate_odds_report(match_dir)
            print(report)
            print()
        except Exception as e:
            print(f"  {match_dir.name}: {e}")


def _fetch_results(args) -> None:
    from football_sim.data_sources.match_fetcher import fetch_and_parse_matches, fetch_match_list, parse_match_list
    from football_sim.history_db import (
        load_analyses,
        record_match_result,
        get_hit_statistics,
        load_match_result,
    )
    from pathlib import Path

    db_path = Path(args.db_path) if args.db_path else Path("data/users/default/history.sqlite3")

    # 收集所有需要查结果的 match_id
    analyses = load_analyses(db_path, limit=200)
    pending_ids = set()
    analysis_map = {}
    for a in analyses:
        mid = a.get("match_id", "")
        if not mid:
            continue
        existing = load_match_result(db_path, mid)
        if not existing or existing.get("result") is None:
            pending_ids.add(mid)
            analysis_map[mid] = a

    if not pending_ids:
        print("所有分析记录都已有比赛结果，无需更新")
        stats = get_hit_statistics(db_path)
        print(f"命中率统计: {stats['hit']}/{stats['hit']+stats['miss']} = {stats['hit_rate']}%")
        return

    print(f"待查询结果的比赛: {len(pending_ids)} 场")

    # 从赛事列表 API 获取比分（按分析记录的日期范围查询）
    from datetime import datetime
    date_set = set()
    for a in analyses:
        ca = a.get("created_at", "")
        if ca:
            date_set.add(ca[:10])

    # 也查今天和昨天
    date_set.add(datetime.now().strftime("%Y-%m-%d"))
    from datetime import timedelta
    date_set.add((datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"))

    found = 0
    for date_str in sorted(date_set, reverse=True):
        if not pending_ids:
            break
        try:
            data = fetch_match_list(date_str)
            matches = parse_match_list(data, date_str)
            for m in matches:
                if m.match_id in pending_ids and m.is_end and m.home_score is not None and m.away_score is not None:
                    result_type = "主胜" if m.home_score > m.away_score else ("客胜" if m.away_score > m.home_score else "平局")
                    result = {
                        "match_id": m.match_id,
                        "home_score": m.home_score,
                        "away_score": m.away_score,
                        "result": result_type,
                        "fetched_at": datetime.now().isoformat(),
                    }
                    record_match_result(db_path, result)
                    a_info = analysis_map.get(m.match_id, {})
                    print(f"  {m.home_team} vs {m.away_team}: {m.home_score}-{m.away_score} ({result_type})")
                    pending_ids.discard(m.match_id)
                    found += 1
        except Exception as e:
            print(f"  查询 {date_str} 失败: {e}")

    if pending_ids:
        print(f"  未获取到结果: {len(pending_ids)} 场（可能尚未结束或 API 无数据）")
        for mid in list(pending_ids)[:5]:
            a_info = analysis_map.get(mid, {})
            print(f"    - {a_info.get('home_team','?')} vs {a_info.get('away_team','?')} (match_id={mid})")

    print(f"共获取 {found} 场比赛结果")

    # 显示统计
    stats = get_hit_statistics(db_path)
    print(f"命中率统计: {stats['hit']}/{stats['hit']+stats['miss']} = {stats['hit_rate']}%")


def _dashboard(args) -> None:
    from football_sim.dashboard import serve_dashboard

    if args.server == "fastapi":
        try:
            from football_sim.fastapi_app import serve_fastapi_dashboard
            serve_fastapi_dashboard(
                reports_dir=Path(args.reports),
                host=args.host,
                port=args.port,
                open_browser=args.open_browser,
            )
        except RuntimeError as exc:
            print(f"{exc}")
            return
        return
    if args.server == "auto":
        try:
            from football_sim.fastapi_app import serve_fastapi_dashboard
            serve_fastapi_dashboard(
                reports_dir=Path(args.reports),
                host=args.host,
                port=args.port,
                open_browser=args.open_browser,
            )
            return
        except RuntimeError as exc:
            print(f"{exc}，已切换到内置本地服务。")
    serve_dashboard(
        reports_dir=Path(args.reports),
        host=args.host,
        port=args.port,
        open_browser=args.open_browser,
    )


if __name__ == "__main__":
    raise SystemExit(main())
