import json
from pathlib import Path


def scan(state_file: str) -> dict:
    """Read deployed state from a JSON file and return parsed resources."""
    path = Path(state_file)
    if not path.exists():
        raise FileNotFoundError(f"State file not found: {state_file}")
    with open(path) as f:
        return json.load(f)
