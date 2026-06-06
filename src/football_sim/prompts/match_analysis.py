SYSTEM_PROMPT = """你是"足球数据分析工作台"。严格基于用户提供的数据文件（ZIP内多JSON）进行分析与预测，禁止臆造或引入外部具体数值。允许采用通用方法论（Elo、Poisson、赔率隐含概率、盘口走位等）作为分析框架；一切数值型证据以用户文件为锚点。

### 核心纪律
- 文件为准：文件数值优先；联网情报仅作定性/验证
- 整数模式：展示层概率四舍五入，用最大余数法校准到100%
- 三项统一：胜平负↔比分↔大小球逻辑一致；若不统一，给出不统一说明

### 分析原则（重要！）
- **客观中立**：不要有预设立场，不要偏向主队或强队
- **基于数据**：所有结论必须有赔率数据或历史数据支撑
- **考虑三种结果**：必须客观评估主胜、平局、客胜的可能性
- **警惕热门**：当赔率显示热门方（低赔方）时，要考虑爆冷可能
- **平局不可忽视**：很多比赛会以平局收场，特别是：
  - 实力接近的球队
  - 友谊赛
  - 低进球预期的比赛
  - 赔率显示平局概率较高的比赛

### 赔率分析要求（关键！）
- **必须计算赔率隐含概率**：使用公式 P = 1/odds / Σ(1/odds)
- **以赔率为锚**：预测方向必须与赔率隐含概率最高的选项一致
- **欧赔去水**：计算概率前先计算 S=Σ(1/odds) 剔除返还率
- **赔率聚合**：以文件中出现的全部公司为样本
- **欧亚一致性**：欧指低赔端与亚盘方向一致→置信度↑；分歧→列为风险
- **识别庄家意图**：关注初盘到即时盘的变化趋势
- **注意平局赔率**：如果平局赔率较低（如 3.0 以下），平局是重要选项

### 预测决策流程
1. **计算赔率隐含概率**：主胜概率、平局概率、客胜概率
2. **分析历史数据**：近期战绩、交锋记录、主客场表现
3. **综合判断**：选择概率最高的结果作为预测方向
4. **不要盲目选主胜**：只有当主胜概率明显高于平局和客胜时才选主胜

### 输出格式
同时提供：
A) 长文可读版 — 完整分析（基础信息、赔率分析、历史交锋、近期状态、阵容情报、核心预测、逻辑评估）
B) 精简推荐版 — 必须明确给出以下三项预测：
   - 胜平负方向（主胜/平局/客胜）
   - 预测比分（如 2-1）
   - 总进球数（如 3球，或 2-3球）
   - 信心指数（0-100）
C) 机器可读JSON — 必须包含以下三个顶层字段：
```json
{
  "prediction": {
    "outcome": "home_win / draw / away_win",
    "score_prediction": "2-1",
    "total_goals": "3"
  },
  "confidence": 75
}
```

### Skill 预测融合
- match-odds-predictor 已基于本地赔率数据进行预测
- 参考 skill 输出的胜平负概率、总进球预测、比分建议
- 若 skill 预测与本地赔率分析一致，置信度上调 5%
- 若不一致，需在分析中说明分歧原因

### 可信度评分
Overall_Confidence(0-100) = 0.35*DataCompleteness + 0.30*OddsConsensus + 0.20*LineupCertainty + 0.15*WebConfidence

### 常见错误提醒
- ❌ 不要默认选主胜，要基于数据分析
- ❌ 不要忽视平局，很多比赛是平局
- ❌ 不要只看球队名气，要看实际状态和赔率
- ✅ 必须计算赔率隐含概率
- ✅ 必须分析平局的可能性
- ✅ 预测必须有数据支撑
"""


def build_user_prompt(match_data: dict, odds_summary: dict = None, skill_prediction: dict = None, use_full_data: bool = True) -> str:
    import json

    parts = ["【任务】对以下赛事进行数据驱动的赛前分析与预测，并给出明确推荐方向"]
    parts.append("【模式】整数模式=开启；多公司=全量纳入")
    parts.append("")

    # 赛事基本信息
    meta = match_data.get("赛事信息", {})
    if meta:
        parts.append(f"## 赛事信息")
        parts.append(f"- 联赛: {meta.get('league', '')}")
        parts.append(f"- 对阵: {meta.get('home_team', '')} vs {meta.get('away_team', '')}")
        parts.append(f"- 开赛时间: {meta.get('match_time', '')}")
        parts.append(f"- 轮次: {meta.get('round', '')}")
        parts.append("")

    # 赔率摘要
    if odds_summary:
        parts.append("## 赔率分析摘要")
        euro_implied = odds_summary.get("euro_implied", {})
        if euro_implied:
            parts.append(f"- 欧赔隐含概率: 主胜{euro_implied.get('p_home',0)}% 平局{euro_implied.get('p_draw',0)}% 客胜{euro_implied.get('p_away',0)}%")
            parts.append(f"- 返还率margin: {euro_implied.get('margin',0)}%")
        parts.append(f"- 亚盘方向: {odds_summary.get('asian_direction', '')}")
        parts.append(f"- 大小球方向: {odds_summary.get('ou_direction', '')}")
        parts.append(f"- 欧亚一致性: {odds_summary.get('euro_asian_consistency', '')}")
        alerts = odds_summary.get("movement_alerts", [])
        if alerts:
            parts.append(f"- 赔率波动警告: {'; '.join(alerts)}")
        outliers = odds_summary.get("bookmaker_outliers", [])
        if outliers:
            parts.append(f"- 离群公司: {', '.join(outliers)}")
        parts.append("")

    # Skill 赔率预测参考
    if skill_prediction:
        parts.append("## Skill 赔率预测参考（match-odds-predictor）")
        pred = skill_prediction.get("prediction", {})
        wdl = pred.get("win_draw_lose", {})
        if wdl:
            parts.append(f"- 推荐方向: {wdl.get('outcome', '')} (概率 {wdl.get('probability', 0)}%)")
            parts.append(f"  主胜: {wdl.get('home_prob', 0)}% | 平局: {wdl.get('draw_prob', 0)}% | 客胜: {wdl.get('away_prob', 0)}%")
        tg = pred.get("total_goals", {})
        if tg:
            parts.append(f"- 总进球预测: {tg.get('prediction', '')} ({tg.get('direction', '')})")
        if pred.get("score_prediction"):
            parts.append(f"- 比分建议: {pred.get('score_prediction', '')}")
        parts.append(f"- Skill 置信度: {skill_prediction.get('confidence', 0)}")
        notes = skill_prediction.get("notes", [])
        if notes:
            parts.append(f"- 补充说明: {'; '.join(notes)}")
        parts.append("")

    # 数据长度限制配置
    # use_full_data=True: 传递完整数据（推荐用于强大模型）
    # use_full_data=False: 使用截断限制（适用于 token 受限的模型）
    limits = {
        "历史交锋": 999999 if use_full_data else 3000,
        "近期战绩": 999999 if use_full_data else 3000,
        "队员情报": 999999 if use_full_data else 2000,
        "阵容天气": 999999 if use_full_data else 2000,
        "联赛积分": 999999 if use_full_data else 2000,
        "赔率变化": 999999 if use_full_data else 5000,
    }

    # JSON 序列化配置：使用压缩格式减少 token 消耗
    json_kwargs = {
        "ensure_ascii": False,
        "separators": (',', ':') if use_full_data else (', ', ': '),  # 压缩格式
    }

    # 历史交锋
    h2h = match_data.get("两队比赛历史交锋数据", {})
    if h2h and not isinstance(h2h, dict) or (isinstance(h2h, dict) and "error" not in h2h):
        parts.append("## 历史交锋数据")
        h2h_str = json.dumps(h2h, **json_kwargs)
        if len(h2h_str) > limits["历史交锋"]:
            # 如果超出限制，使用 indent=2 的格式
            h2h_str = json.dumps(h2h, ensure_ascii=False, indent=2)
        parts.append(h2h_str[:limits["历史交锋"]])
        parts.append("")

    # 近期战绩
    lately = match_data.get("主客队近期比赛数据", {})
    if lately and not isinstance(lately, dict) or (isinstance(lately, dict) and "error" not in lately):
        parts.append("## 近期比赛数据")
        lately_str = json.dumps(lately, **json_kwargs)
        if len(lately_str) > limits["近期战绩"]:
            lately_str = json.dumps(lately, ensure_ascii=False, indent=2)
        parts.append(lately_str[:limits["近期战绩"]])
        parts.append("")

    # 阵容情报
    report = match_data.get("主客队队员、情报信息数据", {})
    if report and not isinstance(report, dict) or (isinstance(report, dict) and "error" not in report):
        parts.append("## 队员情报信息")
        report_str = json.dumps(report, **json_kwargs)
        if len(report_str) > limits["队员情报"]:
            report_str = json.dumps(report, ensure_ascii=False, indent=2)
        parts.append(report_str[:limits["队员情报"]])
        parts.append("")

    # 阵容/天气
    lineup = match_data.get("比赛场地、天气、主客队队员上场信息(身价、位置)数据", {})
    if lineup and not isinstance(lineup, dict) or (isinstance(lineup, dict) and "error" not in lineup):
        parts.append("## 阵容/天气/场地信息")
        lineup_str = json.dumps(lineup, **json_kwargs)
        if len(lineup_str) > limits["阵容天气"]:
            lineup_str = json.dumps(lineup, ensure_ascii=False, indent=2)
        parts.append(lineup_str[:limits["阵容天气"]])
        parts.append("")

    # 联赛积分
    analysis = match_data.get("联赛积分排名、近期状态(进球数、失球数)、未来赛事数据", {})
    if analysis and not isinstance(analysis, dict) or (isinstance(analysis, dict) and "error" not in analysis):
        parts.append("## 联赛积分与状态")
        analysis_str = json.dumps(analysis, **json_kwargs)
        if len(analysis_str) > limits["联赛积分"]:
            analysis_str = json.dumps(analysis, ensure_ascii=False, indent=2)
        parts.append(analysis_str[:limits["联赛积分"]])
        parts.append("")

    # 赔率变化原始数据
    odds_raw = match_data.get("赔率变化数据", {})
    if odds_raw:
        parts.append("## 赔率变化数据（各公司）")
        odds_str = json.dumps(odds_raw, **json_kwargs)
        if len(odds_str) > limits["赔率变化"]:
            odds_str = json.dumps(odds_raw, ensure_ascii=False, indent=2)
        parts.append(odds_str[:limits["赔率变化"]])
        parts.append("")

    parts.append("【需要输出】A长文可读版 + B精简推荐版 + C机器可读JSON")
    parts.append("【注意】文件数值优先；如数据缺失请分别列示")

    return "\n".join(parts)


def build_odds_intent_prompt(match_data: dict, odds_summary: dict, use_full_data: bool = True) -> str:
    import json

    parts = ["【任务】专项分析本场比赛的赔率变化，识别庄家意图"]
    parts.append("")

    meta = match_data.get("赛事信息", {})
    if meta:
        parts.append(f"## 赛事: {meta.get('home_team', '')} vs {meta.get('away_team', '')} ({meta.get('league', '')})")
        parts.append("")

    parts.append("## 赔率分析摘要")
    parts.append(json.dumps(odds_summary, ensure_ascii=False, indent=2))
    parts.append("")

    odds_raw = match_data.get("赔率变化数据", {})
    if odds_raw:
        parts.append("## 赔率变化原始数据")

        # 根据 use_full_data 决定是否截断
        odds_limit = 999999 if use_full_data else 8000

        # 使用压缩格式减少 token 消耗
        if use_full_data:
            odds_str = json.dumps(odds_raw, ensure_ascii=False, separators=(',', ':'))
        else:
            odds_str = json.dumps(odds_raw, ensure_ascii=False, indent=2)

        parts.append(odds_str[:odds_limit])
        parts.append("")

    parts.append("请分析：")
    parts.append("1. 各公司初盘到即时盘的变化趋势及幅度")
    parts.append("2. 欧赔/亚盘/大小球三者之间的信号是否一致")
    parts.append("3. 是否存在异常波动（单边升水/降水、盘口跳变）")
    parts.append("4. 庄家可能的意图判断（诱上/诱下/真实调整）")
    parts.append("5. 对投注方向的建议")

    return "\n".join(parts)
