import json
import time

from pathlib import Path


CACHE_FILE = Path(__file__).resolve().parent / "phab_cache.json"


def _is_fresh(path: Path) -> bool:
    try:
        return (time.time() - path.stat().st_mtime) <= (6 * 60 * 60)
    except FileNotFoundError:
        return False


def _load() -> dict:
    if not _is_fresh(CACHE_FILE):
        try:
            print("Cache is stale, removing...")
            CACHE_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        return {}
    try:
        with CACHE_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(cache: dict) -> None:
    tmp = CACHE_FILE.with_suffix(CACHE_FILE.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    tmp.replace(CACHE_FILE)


def get_transactions(diff_identifier: str):
    """Return cached transactions for a given diff/revision id, or None."""
    cache = _load()
    return cache.get(f"txn:{diff_identifier}")


def set_transactions(diff_identifier: str, transactions) -> None:
    """Save transactions for a given diff/revision id."""
    cache = _load()
    cache[f"txn:{diff_identifier}"] = transactions
    _save(cache)


def get_group(group_name: str):
    """Return cached group info (phid + filtered members) or None."""
    cache = _load()
    return cache.get(f"group:{group_name}")


def set_group(group_name: str, group_data: dict) -> None:
    """Save group info (phid + filtered members)."""
    cache = _load()
    cache[f"group:{group_name}"] = group_data
    _save(cache)


def get_user_phids():
    """Return cached list of user phid dicts, or None."""
    cache = _load()
    return cache.get("user_phids")


def set_user_phids(users: list) -> None:
    """Save list of user phid dicts."""
    cache = _load()
    cache["user_phids"] = users
    _save(cache)
