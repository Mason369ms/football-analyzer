"""数据导出模块 - 提供 PDF、Excel 等格式的报告导出"""

import json
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

from football_sim.logger import get_logger

logger = get_logger(__name__)

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    logger.warning("pandas 未安装，Excel 导出功能将不可用")

try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
    logger.warning("weasyprint 未安装，PDF 导出功能将不可用")


# PDF 模板
PDF_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: Arial, "Microsoft YaHei", sans-serif;
            margin: 40px;
            color: #172033;
            line-height: 1.6;
        }}
        .header {{
            text-align: center;
            border-bottom: 3px solid #1d4ed8;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            color: #1d4ed8;
            margin: 0;
            font-size: 28px;
        }}
        .header .subtitle {{
            color: #667085;
            font-size: 14px;
            margin-top: 10px;
        }}
        .section {{
            margin-bottom: 25px;
        }}
        .section h2 {{
            color: #172033;
            border-bottom: 2px solid #d7dde5;
            padding-bottom: 8px;
            font-size: 18px;
        }}
        .info-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin: 15px 0;
        }}
        .info-item {{
            background: #f8f9fb;
            padding: 12px;
            border-radius: 6px;
            border-left: 4px solid #1d4ed8;
        }}
        .info-item .label {{
            color: #667085;
            font-size: 12px;
            margin-bottom: 4px;
        }}
        .info-item .value {{
            font-size: 16px;
            font-weight: 600;
        }}
        .prediction-box {{
            background: #ecfdf5;
            border: 1px solid #a7f3d0;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }}
        .prediction-box h3 {{
            color: #065f46;
            margin-top: 0;
        }}
        .prediction-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin-top: 15px;
        }}
        .prediction-item {{
            text-align: center;
            background: #fff;
            padding: 15px;
            border-radius: 6px;
            border: 1px solid #d1fae5;
        }}
        .prediction-item .pred-label {{
            color: #667085;
            font-size: 12px;
            margin-bottom: 8px;
        }}
        .prediction-item .pred-value {{
            font-size: 24px;
            font-weight: 700;
            color: #065f46;
        }}
        .analysis-content {{
            background: #fff;
            border: 1px solid #d7dde5;
            padding: 20px;
            border-radius: 8px;
            white-space: pre-wrap;
            font-size: 14px;
            line-height: 1.8;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #d7dde5;
            text-align: center;
            color: #667085;
            font-size: 12px;
        }}
        .confidence-bar {{
            width: 100%;
            height: 20px;
            background: #e5e7eb;
            border-radius: 10px;
            overflow: hidden;
            margin: 10px 0;
        }}
        .confidence-fill {{
            height: 100%;
            background: linear-gradient(90deg, #1d4ed8, #3b82f6);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #fff;
            font-size: 12px;
            font-weight: 600;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{league}: {home_team} vs {away_team}</h1>
        <div class="subtitle">
            赛事分析报告 | 生成时间: {generated_at}
        </div>
    </div>

    <div class="section">
        <h2>赛事信息</h2>
        <div class="info-grid">
            <div class="info-item">
                <div class="label">联赛</div>
                <div class="value">{league}</div>
            </div>
            <div class="info-item">
                <div class="label">比赛时间</div>
                <div class="value">{match_time}</div>
            </div>
            <div class="info-item">
                <div class="label">主队</div>
                <div class="value">{home_team}</div>
            </div>
            <div class="info-item">
                <div class="label">客队</div>
                <div class="value">{away_team}</div>
            </div>
        </div>
    </div>

    <div class="section">
        <h2>预测结果</h2>
        <div class="prediction-box">
            <h3>核心预测</h3>
            <div class="prediction-grid">
                <div class="prediction-item">
                    <div class="pred-label">胜平负</div>
                    <div class="pred-value">{prediction_outcome}</div>
                </div>
                <div class="prediction-item">
                    <div class="pred-label">比分</div>
                    <div class="pred-value">{prediction_score}</div>
                </div>
                <div class="prediction-item">
                    <div class="pred-label">进球数</div>
                    <div class="pred-value">{prediction_goals}</div>
                </div>
            </div>
        </div>

        <div style="margin-top: 20px;">
            <p><strong>置信度: {confidence}%</strong></p>
            <div class="confidence-bar">
                <div class="confidence-fill" style="width: {confidence}%">{confidence}%</div>
            </div>
        </div>
    </div>

    <div class="section">
        <h2>详细分析</h2>
        <div class="analysis-content">{analysis_text}</div>
    </div>

    <div class="footer">
        <p>此报告由 Football Analyzer 自动生成</p>
        <p>报告 ID: {analysis_id} | 生成时间: {generated_at}</p>
    </div>
</body>
</html>
"""


class ReportExporter:
    """报告导出器"""

    def __init__(self, output_dir: Optional[Path] = None):
        """
        初始化导出器

        Args:
            output_dir: 输出目录，默认为 reports/exports
        """
        self.output_dir = output_dir or Path("reports/exports")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_pdf(
        self,
        analysis_data: Dict[str, Any],
        filename: Optional[str] = None
    ) -> Path:
        """
        导出 PDF 报告

        Args:
            analysis_data: 分析数据
            filename: 文件名，默认自动生成

        Returns:
            生成的 PDF 文件路径
        """
        if not WEASYPRINT_AVAILABLE:
            raise RuntimeError("weasyprint 未安装，无法生成 PDF。请运行: pip install weasyprint")

        # 准备模板数据
        template_data = {
            "league": analysis_data.get("league", ""),
            "home_team": analysis_data.get("home_team", ""),
            "away_team": analysis_data.get("away_team", ""),
            "match_time": analysis_data.get("match_time", "未知"),
            "prediction_outcome": analysis_data.get("prediction_outcome", "未知"),
            "prediction_score": analysis_data.get("prediction_score", "未知"),
            "prediction_goals": analysis_data.get("prediction_goals", "未知"),
            "confidence": analysis_data.get("confidence", 0),
            "analysis_text": analysis_data.get("analysis_text", ""),
            "analysis_id": analysis_data.get("id", ""),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        # 渲染 HTML
        html_content = PDF_TEMPLATE.format(**template_data)

        # 生成文件名
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            home = template_data["home_team"].replace(" ", "_")
            away = template_data["away_team"].replace(" ", "_")
            filename = f"analysis_{home}_vs_{away}_{timestamp}.pdf"

        output_path = self.output_dir / filename

        # 生成 PDF
        HTML(string=html_content).write_pdf(str(output_path))

        logger.info(f"PDF 报告已生成: {output_path}")
        return output_path

    def export_excel(
        self,
        analyses: List[Dict[str, Any]],
        filename: Optional[str] = None
    ) -> Path:
        """
        导出 Excel 报告

        Args:
            analyses: 分析记录列表
            filename: 文件名，默认自动生成

        Returns:
            生成的 Excel 文件路径
        """
        if not PANDAS_AVAILABLE:
            raise RuntimeError("pandas 未安装，无法生成 Excel。请运行: pip install pandas openpyxl")

        # 生成文件名
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"analyses_export_{timestamp}.xlsx"

        output_path = self.output_dir / filename

        # 准备数据
        data = []
        for analysis in analyses:
            data.append({
                "ID": analysis.get("id", ""),
                "比赛 ID": analysis.get("match_id", ""),
                "联赛": analysis.get("league", ""),
                "主队": analysis.get("home_team", ""),
                "客队": analysis.get("away_team", ""),
                "预测方向": analysis.get("prediction_outcome", ""),
                "预测比分": analysis.get("prediction_score", ""),
                "预测进球": analysis.get("prediction_goals", ""),
                "置信度": analysis.get("confidence", 0),
                "分析时间": analysis.get("created_at", ""),
                "命中状态": analysis.get("hit_status", ""),
                "实际比分": f"{analysis.get('home_score', '')}-{analysis.get('away_score', '')}" if analysis.get('home_score') is not None else "",
            })

        # 创建 DataFrame
        df = pd.DataFrame(data)

        # 写入 Excel
        with pd.ExcelWriter(str(output_path), engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='分析记录', index=False)

            # 设置列宽
            worksheet = writer.sheets['分析记录']
            for i, col in enumerate(df.columns):
                max_length = max(df[col].astype(str).apply(len).max(), len(col)) + 2
                worksheet.column_dimensions[chr(65 + i)].width = min(max_length, 50)

        logger.info(f"Excel 报告已生成: {output_path}")
        return output_path

    def export_json(
        self,
        data: Any,
        filename: Optional[str] = None,
        pretty: bool = True
    ) -> Path:
        """
        导出 JSON 数据

        Args:
            data: 要导出的数据
            filename: 文件名，默认自动生成
            pretty: 是否格式化

        Returns:
            生成的 JSON 文件路径
        """
        # 生成文件名
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"data_export_{timestamp}.json"

        output_path = self.output_dir / filename

        # 写入 JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            if pretty:
                json.dump(data, f, ensure_ascii=False, indent=2)
            else:
                json.dump(data, f, ensure_ascii=False)

        logger.info(f"JSON 数据已导出: {output_path}")
        return output_path

    def export_csv(
        self,
        analyses: List[Dict[str, Any]],
        filename: Optional[str] = None
    ) -> Path:
        """
        导出 CSV 数据

        Args:
            analyses: 分析记录列表
            filename: 文件名，默认自动生成

        Returns:
            生成的 CSV 文件路径
        """
        if not PANDAS_AVAILABLE:
            raise RuntimeError("pandas 未安装，无法生成 CSV。请运行: pip install pandas")

        # 生成文件名
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"analyses_export_{timestamp}.csv"

        output_path = self.output_dir / filename

        # 准备数据
        data = []
        for analysis in analyses:
            data.append({
                "ID": analysis.get("id", ""),
                "比赛 ID": analysis.get("match_id", ""),
                "联赛": analysis.get("league", ""),
                "主队": analysis.get("home_team", ""),
                "客队": analysis.get("away_team", ""),
                "预测方向": analysis.get("prediction_outcome", ""),
                "预测比分": analysis.get("prediction_score", ""),
                "预测进球": analysis.get("prediction_goals", ""),
                "置信度": analysis.get("confidence", 0),
                "分析时间": analysis.get("created_at", ""),
                "命中状态": analysis.get("hit_status", ""),
            })

        # 创建 DataFrame
        df = pd.DataFrame(data)

        # 写入 CSV
        df.to_csv(str(output_path), index=False, encoding='utf-8-sig')

        logger.info(f"CSV 数据已导出: {output_path}")
        return output_path


# 全局导出器实例
_exporter: Optional[ReportExporter] = None


def get_exporter() -> ReportExporter:
    """获取全局导出器"""
    global _exporter
    if _exporter is None:
        _exporter = ReportExporter()
    return _exporter


def export_analysis_pdf(analysis_data: Dict[str, Any]) -> Path:
    """导出分析报告为 PDF"""
    return get_exporter().export_pdf(analysis_data)


def export_analyses_excel(analyses: List[Dict[str, Any]]) -> Path:
    """导出分析记录为 Excel"""
    return get_exporter().export_excel(analyses)


def export_analyses_json(analyses: List[Dict[str, Any]]) -> Path:
    """导出分析记录为 JSON"""
    return get_exporter().export_json(analyses)


def export_analyses_csv(analyses: List[Dict[str, Any]]) -> Path:
    """导出分析记录为 CSV"""
    return get_exporter().export_csv(analyses)


# 导出
__all__ = [
    'ReportExporter',
    'get_exporter',
    'export_analysis_pdf',
    'export_analyses_excel',
    'export_analyses_json',
    'export_analyses_csv',
]
