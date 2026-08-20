from __future__ import annotations

import inspect
import json
import sys
from enum import Enum
from pathlib import Path

from pydantic import BaseModel

app = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(app))

import mind_forge.schemas as legacy_schemas  # noqa: E402


models: dict[str, dict[str, object]] = {}
enums: dict[str, dict[str, object]] = {}

for name, value in vars(legacy_schemas).items():
    if not inspect.isclass(value):
        continue

    try:
        is_model = issubclass(value, BaseModel)
    except TypeError:
        is_model = False
    if is_model and value is not BaseModel and value.__module__ == legacy_schemas.__name__:
        models[name] = {
            "fields": {
                field_name: {
                    "required": field_info.is_required(),
                    "annotation": str(field_info.annotation),
                    "default": None if field_info.is_required() else repr(field_info.default),
                }
                for field_name, field_info in value.model_fields.items()
            }
        }
        continue

    try:
        is_enum = issubclass(value, Enum)
    except TypeError:
        is_enum = False
    if is_enum and value is not Enum and value.__module__ == legacy_schemas.__name__:
        enums[name] = {
            "members": {member.name: member.value for member in value},
        }

payload = {
    "legacy_module": legacy_schemas.__name__,
    "model_count": len(models),
    "models": dict(sorted(models.items())),
    "enum_count": len(enums),
    "enums": dict(sorted(enums.items())),
}
print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
