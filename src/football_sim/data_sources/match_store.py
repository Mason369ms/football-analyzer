import json
import os
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from football_sim.models import FootballMatch


def _sanitize_name(name: str) -> str:
    sanitized = re.sub(r'[\\/:*?"<>|]+', "_", str(name))
    return sanitized.strip().rstrip(".")


def match_dir_name(match: FootballMatch) -> str:
    return _sanitize_name(f"{match.round}_{match.league}_{match.home_team}_vs_{match.away_team}")


def save_match_data(match: FootballMatch, clean_data: Dict[str, Any], base_dir: Path) -> Path:
    date_dir = Path(base_dir)
    date_dir.mkdir(parents=True, exist_ok=True)
    match_dir = date_dir / match_dir_name(match)
    match_dir.mkdir(parents=True, exist_ok=True)

    for key, value in clean_data.items():
        file_name = f"{_sanitize_name(key)}.json"
        file_path = match_dir / file_name
        file_path.write_text(json.dumps(value, ensure_ascii=False, indent=4), encoding="utf-8")

    # 保存赛事元信息
    meta = {
        "match_id": match.match_id,
        "league": match.league,
        "home_team": match.home_team,
        "away_team": match.away_team,
        "match_time": match.match_time,
        "round": match.round,
    }
    (match_dir / "赛事信息.json").write_text(json.dumps(meta, ensure_ascii=False, indent=4), encoding="utf-8")

    return match_dir


def save_match_zip(match: FootballMatch, clean_data: Dict[str, Any], output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_name = f"{match_dir_name(match)}.zip"
    zip_path = output_dir / zip_name

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for key, value in clean_data.items():
            json_str = json.dumps(value, ensure_ascii=False, indent=4)
            zipf.writestr(f"{_sanitize_name(key)}.json", json_str.encode("utf-8"))
        # 元信息
        meta = {
            "match_id": match.match_id,
            "league": match.league,
            "home_team": match.home_team,
            "away_team": match.away_team,
            "match_time": match.match_time,
            "round": match.round,
        }
        zipf.writestr("赛事信息.json", json.dumps(meta, ensure_ascii=False, indent=4).encode("utf-8"))

    return zip_path


def load_match_data(match_dir: Path) -> Dict[str, Any]:
    match_dir = Path(match_dir)
    data: Dict[str, Any] = {}
    for json_file in sorted(match_dir.glob("*.json")):
        try:
            data[json_file.stem] = json.loads(json_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
    return data


def list_match_dirs(date_dir: Path) -> List[Path]:
    date_dir = Path(date_dir)
    if not date_dir.exists():
        return []
    return sorted([d for d in date_dir.iterdir() if d.is_dir()])


def match_dir_to_match(match_dir: Path) -> Optional[FootballMatch]:
    meta_path = match_dir / "赛事信息.json"
    if not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return FootballMatch(
            match_id=meta.get("match_id", ""),
            league=meta.get("league", ""),
            home_team=meta.get("home_team", ""),
            away_team=meta.get("away_team", ""),
            match_time=meta.get("match_time", ""),
            round=meta.get("round", ""),
        )
    except (json.JSONDecodeError, OSError):
        return None


def pack_match_dir_to_zip(match_dir: Path) -> Path:
    """将赛事目录打包为 zip 文件，返回 zip 路径"""
    match_dir = Path(match_dir)
    zip_path = match_dir.with_suffix(".zip")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for json_file in sorted(match_dir.glob("*.json")):
            zipf.write(json_file, json_file.name)

    return zip_path
