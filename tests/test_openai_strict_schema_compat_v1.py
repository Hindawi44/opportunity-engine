from opportunity_engine.discovery import openai_hunt_case_enrichment as hunt


def test_hunt_case_schema_is_openai_strict_compatible() -> None:
    schema = hunt._schema(hunt.TriageOutput)

    assert schema["required"] == ["cases", "unassigned_signal_ids"]
    assert schema["additionalProperties"] is False
    assert "title" not in schema

    case_schema = schema["$defs"]["TriageCase"]
    assert set(case_schema["required"]) == set(case_schema["properties"])
    assert case_schema["additionalProperties"] is False
    assert "default" not in case_schema["properties"]["normalized_company_name"]
    assert "default" not in case_schema["properties"]["connection_basis"]


def test_deep_schema_requires_all_properties_too() -> None:
    schema = hunt._schema(hunt.DeepOutput)
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["additionalProperties"] is False
