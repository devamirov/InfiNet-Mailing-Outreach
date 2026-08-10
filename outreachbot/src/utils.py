"""Shared utilities: STOP file, delays, env."""
import os
import random
import time
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def stop_file_path() -> Path:
    return project_root() / "STOP"


def is_stop_requested() -> bool:
    return stop_file_path().exists()


def random_delay_seconds(min_sec: int, max_sec: int) -> float:
    return random.uniform(min_sec, max_sec)


def apply_delay(min_sec: int, max_sec: int) -> None:
    time.sleep(random_delay_seconds(min_sec, max_sec))


def get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()
