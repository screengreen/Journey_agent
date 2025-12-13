from pathlib import Path

def project_root() -> Path:
    start = Path(__file__).resolve()
    for p in [start, *start.parents]:
        # выбери маркер, который точно есть в корне проекта
        if (p / "pyproject.toml").exists() or (p / ".git").exists():
            return p
    # fallback: если маркера нет, пусть будет папка выше src
    return start.parents[2]

ROOT = project_root()
DATA = ROOT / "data"
