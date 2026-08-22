from pathlib import Path


WORKFLOW = Path('.github/workflows/mind-forge-live-research-launcher.yaml')
RUNTIME = Path('mind-forge-live/phase1')


def _dispatch_block(text: str) -> str:
    return text.split('workflow_dispatch:', 1)[1].split('permissions:', 1)[0]


def test_existing_launcher_accepts_raw_seed_without_manual_execution_mode():
    text = WORKFLOW.read_text(encoding='utf-8')
    dispatch = _dispatch_block(text)

    assert 'seed:' in dispatch
    assert 'confirm_paid_live_research:' in dispatch
    assert 'mode:' not in dispatch
    assert 'LIVE_RESEARCH' not in dispatch
    assert 'CREATIVE_V2_OPEN' not in dispatch


def test_existing_launcher_preserves_explicit_paid_authorization():
    text = WORKFLOW.read_text(encoding='utf-8')

    assert 'default: "NO"' in text
    assert "inputs.confirm_paid_live_research == 'YES'" in text
    assert "inputs.confirm_paid_live_research != 'YES'" in text


def test_existing_launcher_routes_seed_directly_into_autonomous_v2_cycle():
    text = WORKFLOW.read_text(encoding='utf-8')

    assert 'MIND_FORGE_SEED: ${{ inputs.seed }}' in text
    assert 'Run one autonomous MIND FORGE V2 cycle from the raw seed' in text
    assert 'reasoning.json' in text
    assert 'top3.json' in text
    assert 'evidence.json' in text
    assert 'final_rank.json' in text
    assert 'live_evidence_usage.json' in text


def test_auto_routing_does_not_expand_workflow_inventory():
    workflows = [
        path for path in Path('.github/workflows').iterdir()
        if path.suffix in {'.yml', '.yaml'}
    ]
    assert len(workflows) == 6


def test_v2_runtime_is_local_to_main_line_and_not_checked_out_from_legacy_branch():
    text = WORKFLOW.read_text(encoding='utf-8')

    assert 'agent/mind-forge-generalization-tests' not in text
    assert 'ref:' not in text.split('Check out current main-line V2 implementation', 1)[1].split('Set up Python', 1)[0]

    required_runtime = {
        'contracts_v1.py',
        'question_generator_v1.py',
        'creative_engine_v1.py',
        'creative_engine_v2_open.py',
        'expert_minds_v1.py',
        'live_model_adapter_v1.py',
        'live_creative_v2_open.py',
    }
    assert required_runtime.issubset({path.name for path in RUNTIME.iterdir() if path.is_file()})


def test_isolated_runtime_copies_all_import_dependencies():
    text = WORKFLOW.read_text(encoding='utf-8')
    build_block = text.split('Build isolated Creative V2 runtime', 1)[1].split('Normalize API secret', 1)[0]

    # live_model_adapter_v1 imports expert_minds_v1 indirectly; it must be copied too.
    assert 'expert_minds_v1.py' in build_block
    assert 'live_model_adapter_v1.py' in build_block


def test_paid_live_job_sets_explicit_runtime_enable_guard():
    text = WORKFLOW.read_text(encoding='utf-8')
    paid_job = text.split('creative-v2-open-live:', 1)[1]

    assert text.count('MIND_FORGE_LIVE_ENABLED: "1"') == 1
    assert 'MIND_FORGE_LIVE_ENABLED: "1"' in paid_job
