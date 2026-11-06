from datetime import datetime, timedelta, timezone
import json
from pathlib import Path


CHECKPOINT_MAX_AGE = timedelta(days=7)


def checkpoint_path_for(output: Path) -> Path:
    return output.with_name(output.name + ".progress.json")


def _read_checkpoint_file(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read progress file {path}: {error}") from error
    if not isinstance(data, dict):
        raise ValueError(f"Progress file has an unexpected format: {path}")
    return data


def load_checkpoint(
    path: Path, variable_names: list[str], now: datetime | None = None
) -> dict[str, int]:
    data = _read_checkpoint_file(path)
    prices = data.get("prices")
    if not isinstance(prices, dict):
        raise ValueError(f"Progress file has an unexpected format: {path}")
    try:
        created_at = datetime.fromisoformat(data["created_at"])
        if created_at.tzinfo is None:
            raise ValueError("missing timezone")
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"Progress file has no valid creation time, so it was not used; "
            f"delete {path} to start over."
        ) from error
    now = now or datetime.now(timezone.utc)
    if now - created_at > CHECKPOINT_MAX_AGE:
        raise ValueError(
            f"Progress file was created {created_at:%Y-%m-%d %H:%M} "
            f"(more than {CHECKPOINT_MAX_AGE.days} days ago), so its prices were "
            f"not used; delete {path} to start over."
        )
    valid = set(variable_names)
    for name, price in prices.items():
        if name not in valid or isinstance(price, bool) or not isinstance(price, int):
            raise ValueError(
                f"Progress file contains an invalid entry {name!r}; "
                f"delete {path} to start over."
            )
    return prices


def save_checkpoint(path: Path, prices: dict[str, int]) -> None:
    created_at = None
    if path.exists():
        created_at = _read_checkpoint_file(path).get("created_at")
    if created_at is None:
        created_at = datetime.now(timezone.utc).isoformat()
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(
        json.dumps({"created_at": created_at, "prices": prices}, indent=2),
        encoding="utf-8",
    )
    temp.replace(path)
