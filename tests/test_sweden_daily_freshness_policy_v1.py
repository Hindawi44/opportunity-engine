from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVED = ROOT / "docs/archive/legacy-six-market-checkpoint-20260919.yaml.txt"
ACTIVE = ROOT / ".github/workflows/multi-market-daily-operator-checkpoint.yaml"


def _source_step(text: str, start_name: str, end_name: str) -> str:
    start = text.index(f"- name: {start_name}")
    end = text.index(f"- name: {end_name}", start)
    return text[start:end]


def test_sweden_source_policy_is_preserved_in_archive_but_not_scheduled() -> None:
    old = ARCHIVED.read_text(encoding="utf-8")
    current = ACTIVE.read_text(encoding="utf-8")
    segments = (
        _source_step(old, "Run Sweden Blinto bounded pilot", "Run Sweden Klaravik bounded direct scan"),
        _source_step(old, "Run Sweden Klaravik bounded direct scan", "Run Sweden PS Auction bounded direct scan"),
        _source_step(old, "Run Sweden PS Auction bounded direct scan", "Run active Riegermann discovery"),
    )
    for segment in segments:
        assert "--freshness pm" in segment
        assert "--freshness none" not in segment
    assert "Run Sweden Blinto bounded pilot" not in current
    assert "Run Sweden Klaravik bounded direct scan" not in current
    assert "Run Sweden PS Auction bounded direct scan" not in current


def test_sweden_runner_keeps_monthly_freshness_as_its_historical_default() -> None:
    runner = (ROOT / "scripts/run_sweden_clothing_inventory_discovery_search.py").read_text(encoding="utf-8")
    assert 'choices=("none", "pd", "pw", "pm", "py")' in runner
    assert 'default="pm"' in runner
