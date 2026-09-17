import json
from datetime import datetime
from pathlib import Path
from config import DATA_PROCESSED


def create_run_folder():
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = DATA_PROCESSED / "run" / ts
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def save_json(run_dir: Path, name: str, data: dict):
    with open(run_dir / f"{name}.json", "w") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
