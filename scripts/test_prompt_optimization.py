#!/usr/bin/env python3
"""测试优化后的提示词效果"""
import sys
from pathlib import Path

# 添加源码路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from football_sim.history_db import load_dashboard_config
from football_sim.analysis.llm_analyzer import analyze_match
from football_sim.data_sources.match_store import list_match_dirs

def test_improved_prompt():
    """测试优化后的提示词"""

    print("=" * 70)
    print("🧪 测试优化后的提示词效果")
    print("=" * 70)

    # 加载配置
    db_path = Path("data/users/default/history.sqlite3")
    config = load_dashboard_config(db_path)

    print(f"\n📋 LLM 配置:")
    print(f"   模型: {config.get('llm_model')}")
    print(f"   URL: {config.get('llm_base_url')}")

    # 获取一场比赛进行测试
    date_dir = Path("data/matches/2026-06-04")
    match_dirs = list_match_dirs(date_dir)

    if not match_dirs:
        print("❌ 未找到比赛数据")
        return

    # 选择第一场比赛
    test_match = match_dirs[0]
    print(f"\n🏟️  测试比赛: {test_match.name}")

    # 分析比赛
    print("\n🔍 开始分析...")
    try:
        analysis = analyze_match(test_match, config, use_full_data=True)

        print("\n" + "=" * 70)
        print("📊 分析结果")
        print("=" * 70)

        print(f"\n比赛: {analysis.home_team} vs {analysis.away_team}")
        print(f"联赛: {analysis.league}")

        print(f"\n🎯 预测:")
        print(f"   置信度: {analysis.confidence}")

        # 从 prediction_json 提取预测结果
        pred_json = analysis.prediction_json
        if pred_json:
            prediction = pred_json.get("prediction", {})
            outcome = prediction.get("outcome", "")
            score = prediction.get("score_prediction", "")
            goals = prediction.get("total_goals", "")

            # 标准化 outcome
            if "home" in outcome.lower() or "主胜" in outcome:
                outcome_cn = "主胜"
            elif "away" in outcome.lower() or "客胜" in outcome:
                outcome_cn = "客胜"
            elif "draw" in outcome.lower() or "平局" in outcome:
                outcome_cn = "平局"
            else:
                outcome_cn = outcome

            print(f"   方向: {outcome_cn} ({outcome})")
            print(f"   比分: {score}")
            print(f"   进球: {goals}")
        else:
            print("   ⚠️  未提取到预测 JSON")

        # 检查是否有平局或客胜的可能
        analysis_text = analysis.analysis_text
        print(f"\n📝 分析文本预览:")
        print("-" * 70)
        # 打印前 500 字符
        print(analysis_text[:500] + "..." if len(analysis_text) > 500 else analysis_text)
        print("-" * 70)

        # 统计关键词出现次数
        draw_count = analysis_text.count("平局") + analysis_text.count("draw")
        away_count = analysis_text.count("客胜") + analysis_text.count("away_win")
        home_count = analysis_text.count("主胜") + analysis_text.count("home_win")

        print(f"\n📈 关键词统计:")
        print(f"   主胜: {home_count} 次")
        print(f"   平局: {draw_count} 次")
        print(f"   客胜: {away_count} 次")

        if draw_count > 0 or away_count > 0:
            print("\n✅ 优化成功！分析中考虑了平局和客胜的可能性")
        else:
            print("\n⚠️  优化可能不够，分析仍然只关注主胜")

    except Exception as e:
        print(f"\n❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 70)
    print("💡 优化内容:")
    print("=" * 70)
    print("""
1. ✅ 增加"分析原则"部分，强调客观中立
2. ✅ 明确要求考虑三种结果（主胜、平局、客胜）
3. ✅ 增加赔率分析要求，必须计算隐含概率
4. ✅ 增加预测决策流程，避免盲目选主胜
5. ✅ 增加常见错误提醒，明确禁止默认主胜
6. ✅ 强调平局的重要性，特别提到友谊赛和低进球比赛

现在可以重新分析比赛，看看是否会有更多平局和客胜的预测。
    """)


if __name__ == "__main__":
    test_improved_prompt()
