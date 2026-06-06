import os
import sys
import traceback
from pathlib import Path
from typing import Optional, Sequence


def application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def configure_import_path(root: Optional[Path] = None) -> None:
    root_path = Path(root or application_root())
    src_path = root_path / "src"
    if src_path.exists():
        src_text = str(src_path)
        if src_text not in sys.path:
            sys.path.insert(0, src_text)


def ensure_runtime_dirs(root: Path) -> None:
    root_path = Path(root)
    for directory in (
        root_path / "data" / "matches",
        root_path / "data" / "users",
        root_path / "reports" / "latest",
        root_path / "reports" / "users",
    ):
        directory.mkdir(parents=True, exist_ok=True)


def run_cli(argv: Optional[Sequence[str]] = None) -> int:
    configure_import_path()
    from football_sim.cli import main as cli_main

    return cli_main(list(argv or ()))


def run_dashboard(
    root: Optional[Path] = None,
    host: str = "127.0.0.1",
    port: int = 8766,
    open_browser: bool = True,
) -> None:
    root_path = Path(root or application_root())
    configure_import_path(root_path)
    ensure_runtime_dirs(root_path)
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if getattr(sys, "frozen", False):
        os.environ["FOOTBALL_CLI_EXE"] = sys.executable

    try:
        from football_sim.fastapi_app import serve_fastapi_dashboard

        serve_fastapi_dashboard(
            reports_dir=root_path / "reports" / "latest",
            host=host,
            port=port,
            open_browser=open_browser,
            repo_root=root_path,
        )
    except RuntimeError as exc:
        print(f"{exc}; falling back to the local single-user server.")
        from football_sim.dashboard import serve_dashboard

        serve_dashboard(
            reports_dir=root_path / "reports" / "latest",
            host=host,
            port=port,
            open_browser=open_browser,
        )


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if args and args[0] == "--cli":
            return run_cli(args[1:])
        host = os.environ.get("FOOTBALL_HOST", "127.0.0.1")
        port = int(os.environ.get("FOOTBALL_PORT", "8766"))
        open_browser = os.environ.get("FOOTBALL_OPEN_BROWSER", "1").lower() not in {"0", "false", "no"}
        run_dashboard(host=host, port=port, open_browser=open_browser)
        return 0
    except Exception:
        traceback.print_exc()
        if getattr(sys, "frozen", False):
            input("Press Enter to exit...")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
