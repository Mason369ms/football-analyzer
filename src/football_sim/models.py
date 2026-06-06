from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class FootballMatch:
    match_id: str
    league: str
    home_team: str
    away_team: str
    match_time: str
    round: str
    status: str = ""
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    is_end: bool = False

    @property
    def display_name(self) -> str:
        return f"{self.league} {self.home_team} vs {self.away_team}"


@dataclass(frozen=True)
class OddsSnapshot:
    match_id: str
    company_id: str
    company_name: str
    odds_type: str  # "欧指" / "亚盘" / "大小球"
    home_odds: float
    draw_odds: Optional[float]
    away_odds: float
    handicap: Optional[str] = None
    updated_at: str = ""


@dataclass(frozen=True)
class OddsChange:
    match_id: str
    company_id: str
    company_name: str
    odds_type: str
    changes: Tuple[Dict[str, Any], ...] = ()


@dataclass(frozen=True)
class MatchDetailBundle:
    match: FootballMatch
    history_battle: Dict[str, Any] = field(default_factory=dict)
    lately_record: Dict[str, Any] = field(default_factory=dict)
    report_info: Dict[str, Any] = field(default_factory=dict)
    lineup_info: Dict[str, Any] = field(default_factory=dict)
    data_analysis: Dict[str, Any] = field(default_factory=dict)
    odds_changes: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MatchAnalysis:
    match_id: str
    home_team: str
    away_team: str
    league: str
    analysis_text: str  # A版长文
    brief_text: str  # B版精简
    prediction_json: Dict[str, Any] = field(default_factory=dict)  # C版JSON
    confidence: int = 0
    created_at: str = ""


@dataclass(frozen=True)
class OddsAnalysisResult:
    match_id: str
    home_team: str
    away_team: str
    euro_implied: Dict[str, float] = field(default_factory=dict)  # p_home, p_draw, p_away, margin
    asian_direction: str = ""  # "主队" / "客队" / "中立"
    ou_direction: str = ""  # "大球" / "小球" / "中立"
    movement_alerts: Tuple[str, ...] = ()  # 赔率异常波动警告
    euro_asian_consistency: str = ""  # "一致" / "分歧"
    bookmaker_outliers: Tuple[str, ...] = ()  # 离群公司
    summary: str = ""
