"""Assert that docker-compose*.yml declare the Phase B hardening keys."""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PROD_KEYS = {
    "mem_limit",
    "cpus",
    "pids_limit",
    "cap_drop",
    "cap_add",
    "security_opt",
    "logging",
    "healthcheck",
}
# Dev compose doesn't need a healthcheck (no Docker restart loop in dev).
REQUIRED_DEV_KEYS = REQUIRED_PROD_KEYS - {"healthcheck"}


def assert_hardening(path: Path, required: set[str]) -> list[str]:
    missing: list[str] = []
    if not path.exists():
        return [f"{path}: not found"]
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        return [f"{path}: YAML parse error: {e}"]
    services = data.get("services") or {}
    if not services:
        return [f"{path}: no services block"]
    for name, svc in services.items():
        keys = set(svc.keys())
        miss = required - keys
        if miss:
            missing.append(f"{path}::services.{name}: missing {sorted(miss)}")
    return missing


def main() -> int:
    errors: list[str] = []
    errors += assert_hardening(REPO_ROOT / "docker-compose.yml", REQUIRED_PROD_KEYS)
    errors += assert_hardening(REPO_ROOT / "docker-compose.dev.yml", REQUIRED_DEV_KEYS)
    if errors:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        return 1
    print("OK: compose files declare Phase B hardening keys.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
