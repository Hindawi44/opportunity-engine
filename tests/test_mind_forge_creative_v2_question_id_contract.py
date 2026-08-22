from pathlib import Path
import runpy


def test_creative_v2_question_id_contract():
    contract = Path("mind-forge-live/phase1/creative_v2_open_contract.py")
    namespace = runpy.run_path(str(contract), run_name="creative_v2_open_contract_test")
    result = namespace["run_contract"]()

    assert result["status"] == "CREATIVE_V2_OPEN_CONTRACT_PASS"
    assert result["paid_api_calls"] == 0
    assert result["unknown_question_ids_are_canonicalized"] is True
    assert result["final_question_id_subset_validation_is_strict"] is True
