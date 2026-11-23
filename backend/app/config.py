from pathlib import Path

from dotenv import load_dotenv


def load_local_env() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    for dotenv_path in (backend_dir.parent / ".env", backend_dir / ".env"):
        load_dotenv(dotenv_path, override=False, encoding="utf-8-sig")
