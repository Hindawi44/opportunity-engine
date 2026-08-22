from copy import deepcopy
import json
from pathlib import Path

from scripts.mind_forge_v2_reasoning import evaluate_payload


def _payload():
    ideas = [
        {
            "idea_id": "a",
            "title": "Small Batch Import Lab",
            "mechanism_family": "Inventory-light validation",
            "core_mechanism": "Test imported products with small preorder batches before larger purchasing.",
            "customer_value": "Access to useful products with lower stockout risk.",
            "business_value": "Limits working capital and validates demand.",
            "required_capabilities": ["supplier coordination", "preorder operations"],
            "assumptions": ["Suppliers accept small batches."],
            "risks": ["Lead times may reduce conversion."],
            "novelty_reason": "Turns purchasing into a reversible test.",
        },
        {
            "idea_id": "b",
            "title": "Merchant Margin Simulator",
            "mechanism_family": "Decision analytics",
            "core_mechanism": "Model landed cost, tax, returns, storage and break-even volume before buying.",
            "customer_value": "More sustainable product availability.",
            "business_value": "Prevents weak economics from hiding behind low purchase prices.",
            "required_capabilities": ["cost modeling", "scenario analysis"],
            "assumptions": ["Input costs can be estimated."],
            "risks": ["False precision may mislead decisions."],
            "novelty_reason": "Makes full economics visible before purchase.",
        },
        {
            "idea_id": "c",
            "title": "Seasonal Stock Exchange",
            "mechanism_family": "Inventory liquidity",
            "core_mechanism": "Transfer slow stock between merchants with different local demand.",
            "customer_value": "Better local availability and discounts.",
            "business_value": "Reduces markdown losses and trapped inventory.",
            "required_capabilities": ["stock visibility", "transport", "settlement"],
            "assumptions": ["Demand differs across locations."],
            "risks": ["Transport can erase value."],
            "novelty_reason": "Uses geographic demand differences as inventory liquidity.",
        },
        {
            "idea_id": "d",
            "title": "Proof of Origin Commerce",
            "mechanism_family": "Traceability",
            "core_mechanism": "Attach supplier, origin, batch and claim evidence to product listings.",
            "customer_value": "Improves trust and authenticity checks.",
            "business_value": "Supports premium trust and dispute resolution.",
            "required_capabilities": ["supplier verification", "batch records"],
            "assumptions": ["Suppliers provide credible evidence."],
            "risks": ["Verification may cost too much."],
            "novelty_reason": "Makes provenance visible at the buying decision.",
        },
    ]
    return {"seed": "trade in Norway", "ideas": ideas}


def test_reasoning_uses_ten_lenses_and_selects_top_three():
    result = evaluate_payload(_payload())
    assert result["status"] == "MIND_FORGE_V2_REASONING_COMPLETE"
    assert result["expert_mind_count"] == 10
    assert len(result["selected_idea_ids"]) == 3
    assert result["uses_mechanism_family_for_scoring"] is False
    assert {row["idea_id"] for row in result["assessments"]} == {"a", "b", "c", "d"}


def test_family_labels_do_not_change_scores_or_selection():
    original = _payload()
    renamed = deepcopy(original)
    for idx, idea in enumerate(renamed["ideas"]):
        idea["mechanism_family"] = f"totally-new-family-{idx}"

    first = evaluate_payload(original)
    second = evaluate_payload(renamed)

    assert first["selected_idea_ids"] == second["selected_idea_ids"]
    first_scores = {row["idea_id"]: row["composite_score"] for row in first["assessments"]}
    second_scores = {row["idea_id"]: row["composite_score"] for row in second["assessments"]}
    assert first_scores == second_scores


def test_all_ideas_receive_logic_and_devils_advocate():
    result = evaluate_payload(_payload())
    for row in result["assessments"]:
        assert 0 <= row["logic_score"] <= 1
        assert 0 <= row["expert_support_mean"] <= 1
        assert row["critique"]["disposition"] in {"SURVIVES", "NEEDS_EVIDENCE", "REWORK"}
        assert row["critique"]["falsification_test"]


def test_live_creative_v2_run_32555691182_selects_stable_top_three():
    fixture_path = Path("tests/fixtures/mind_forge_v2_live_run_32555691182.json")
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    result = evaluate_payload(payload)

    assert payload["fixture_source"]["run_id"] == 32555691182
    assert payload["fixture_source"]["artifact_id"] == 9471344273
    assert result["idea_count"] == 14
    assert result["expert_mind_count"] == 10
    assert result["uses_mechanism_family_for_scoring"] is False
    assert result["selected_idea_ids"] == [
        "idea-open-c99ef11df42f259b",
        "idea-open-adc0e939beba1e85",
        "idea-open-b7e3e27666346cfe",
    ]

    top_titles = [row["title"] for row in result["assessments"][:3]]
    assert top_titles == [
        "Merchant-in-a-Box Operating Standard",
        "Rural Merchant Shared Fulfillment",
        "B2B Replenishment Route",
    ]
