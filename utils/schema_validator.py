"""
JSON Schema validation helper.
Loads schemas once from the schemas/ directory and exposes a simple validate() call.
"""

import json
import os
from pathlib import Path

import jsonschema

SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"

# Cache loaded schemas so we don't re-read from disk on every call.
_schema_cache: dict[str, dict] = {}


def _load_schema(name: str) -> dict:
    """Load and cache a JSON schema file by name (without extension)."""
    if name not in _schema_cache:
        schema_path = SCHEMAS_DIR / f"{name}.json"
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
        with open(schema_path) as f:
            _schema_cache[name] = json.load(f)
    return _schema_cache[name]


def validate(instance: dict, schema_name: str) -> None:
    """
    Validate a response payload against a named schema.

    Args:
        instance:    The JSON object to validate.
        schema_name: One of 'repository', 'issue', 'user'.

    Raises:
        jsonschema.ValidationError on mismatch.
    """
    schema = _load_schema(schema_name)
    jsonschema.validate(instance=instance, schema=schema)
