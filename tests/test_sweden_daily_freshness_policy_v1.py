from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/multi-market-daily-operator-checkpoint.yaml"


def _source_step(text: str, start_name: str, end_name: str) -> str:
    start = text.index(f"- name: {start_name}")
    end = text.index(f"- name: {end_name}", start)
    return text[start:end]


def test_all_daily_sweden_direct_sources_use_bounded_monthly_freshness() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    blinto = _source_step(
        text,
        "Run Sweden Blinto bounded pilot",
        "Run Sweden Klaravik bounded direct scan",
    )
    klaravik = _source_step(
        text,
        "Run Sweden Klaravik bounded direct scan",
        "Run Sweden PS Auction bounded direct scan",
    )
    psauction = _source_step(
        text,
        "Run Sweden PS Auction bounded direct scan",
        "Run active Riegermann discovery",
    )

    for source_step in (blinto, klaravik, psauction):
        assert "--freshness pm" in source_step
        assert "--freshness none" not in source_step


def test_sweden_runner_keeps_monthly_freshness_as_its_default() -> None:
    runner = (
        ROOT / "scripts/run_sweden_clothing_inventory_discovery_search.py"
    ).read_text(encoding="utf-8")

    assert 'choices=("none", "pd", "pw", "pm", "py")' in runner
    assert 'default="pm"' in runner
