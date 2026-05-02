from collections.abc import Iterable
from pathlib import Path
import os

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
DB_ENV_PREFIX = "DB_"


def load_env_file(env_path: Path = ENV_PATH) -> None:
    if load_dotenv:
        load_dotenv(env_path)
        return

    if not env_path.exists():
        return

    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def resolve_project_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path

    return PROJECT_ROOT / path


def get_instances() -> dict[str, Path]:
    load_env_file()

    instances = {}
    for key, value in os.environ.items():
        if not key.startswith(DB_ENV_PREFIX) or not value:
            continue

        instance_id = key.removeprefix(DB_ENV_PREFIX)
        instances[instance_id] = resolve_project_path(value)

    return dict(sorted(instances.items()))


def get_instance_path(instance_id: str) -> Path:
    instances = get_instances()
    if instance_id not in instances:
        available = ", ".join(instances) or "none"
        raise ValueError(f"Unknown instance_id: {instance_id}. Available instances: {available}")

    return instances[instance_id]


def get_required_instance_paths(instance_ids: Iterable[str]) -> list[Path]:
    instances = get_instances()
    missing = [instance_id for instance_id in instance_ids if instance_id not in instances]
    if missing:
        env_vars = ", ".join(f"{DB_ENV_PREFIX}{instance_id}" for instance_id in missing)
        raise RuntimeError(f"Missing required database path(s) in .env: {env_vars}")

    return [instances[instance_id] for instance_id in instance_ids]
