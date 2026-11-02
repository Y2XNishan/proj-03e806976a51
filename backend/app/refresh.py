"""Explicit one-shot cache refresh: python -m app.refresh (from backend)."""

import json

from .cache import refresh


if __name__ == "__main__":
    print(json.dumps(refresh(), indent=2))
