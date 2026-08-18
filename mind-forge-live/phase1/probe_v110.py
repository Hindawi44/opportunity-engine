from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

from pydantic import BaseModel

app = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(app))

import mind_forge.schemas as legacy_schemas  # noqa: E402


models: dict[str, dict[str, object]] = {}
for name, value in vars(legacy_schemas).items():
    if not inspect.isclass(value):
        continue
    try:
        is_model = issubclass(value, BaseModel)
    except TypeError:
        is_model = False
    if not is_model or value is BaseModel:
        continue
    if value.__module__ != legacy_schemas.__name__:
        continue
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

payload = {
    "legacy_module": legacy_schemas.__name__,
    "model_count": len(models),
    "models": dict(sorted(models.items())),
}
print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
