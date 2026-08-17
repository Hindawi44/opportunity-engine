from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISCOVERY_INIT = ROOT / "src/opportunity_engine/discovery/__init__.py"
HOOK = ROOT / "src/opportunity_engine/discovery/mathematical_logic_shadow_cli_hook.py"


def test_math_shadow_is_registered_before_river_for_lifo_execution() -> None:
    text = DISCOVERY_INIT.read_text(encoding="utf-8")
    math_install = text.index("install_mathematical_logic_shadow_cli_hook()")
    river_install = text.index("install_unified_market_intelligence_river_cli_hook()")
    assert math_install < river_install


def test_math_shadow_hook_is_read_only_and_requires_unified_cases() -> None:
    text = HOOK.read_text(encoding="utf-8")
    assert '"unified-market-cases.json"' in text
    assert "write_mathematical_logic_shadow" in text
    assert "automatic_purchase" not in text
    assert "requests." not in text
    assert "openai" not in text.lower()
