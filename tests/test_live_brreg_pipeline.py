from opportunity_engine.ods import (
    BrregClient,
    BrregConnector,
    LifecycleState,
    run_live_brreg_analysis,
)


def _transport_with_entities(entities):
    def transport(url, timeout, headers):
        return {"_embedded": {"enheter": entities}}
    return transport


def test_live_brreg_pipeline_creates_signal_without_ranking_or_decision():
    entities = [
        {
            "organisasjonsnummer": "999888777",
            "navn": "Eksempel Klær AS",
            "konkurs": True,
            "underAvvikling": False,
            "organisasjonsform": {"beskrivelse": "Aksjeselskap"},
            "naeringskode1": {"kode": "47.710", "beskrivelse": "Butikkhandel med klær"},
            "forretningsadresse": {"kommune": "NAMSOS"},
        }
    ]
    connector = BrregConnector(
        client=BrregClient(transport=_transport_with_entities(entities)),
        page_size=10,
    )

    result = run_live_brreg_analysis("klær", connector=connector)

    assert result.scan.documents[0].source_name == "Brønnøysundregistrene"
    assert len(result.scan.opportunities) == 1
    signal = result.scan.opportunities[0]
    assert signal.opportunity_id == "brreg-status-999888777"
    assert signal.lifecycle_state is LifecycleState.SIGNAL
    assert signal.source_plugin == "brreg_status_extractor"
    assert result.ranked_opportunities == ()
    assert result.decision is None


def test_live_brreg_pipeline_returns_empty_without_explicit_status_signal():
    entities = [
        {
            "organisasjonsnummer": "111222333",
            "navn": "Aktiv Bedrift AS",
            "konkurs": False,
            "underAvvikling": False,
        }
    ]
    connector = BrregConnector(
        client=BrregClient(transport=_transport_with_entities(entities)),
        page_size=10,
    )

    result = run_live_brreg_analysis("bedrift", connector=connector)

    assert len(result.scan.documents) == 1
    assert result.scan.opportunities == ()
    assert result.ranked_opportunities == ()
    assert result.decision is None


def test_live_brreg_pipeline_does_not_claim_assets_or_opportunity_exist():
    entities = [
        {
            "organisasjonsnummer": "444555666",
            "navn": "Avvikling Eksempel AS",
            "konkurs": False,
            "underAvvikling": True,
        }
    ]
    connector = BrregConnector(
        client=BrregClient(transport=_transport_with_entities(entities)),
        page_size=10,
    )

    result = run_live_brreg_analysis("eksempel", connector=connector)
    description = result.scan.opportunities[0].description.lower()

    assert "does not prove that assets are available" in description
    assert "commercial opportunity exists" in description


def test_brreg_signal_cannot_skip_directly_to_hypothesis_or_decision_candidate():
    entities = [
        {
            "organisasjonsnummer": "777888999",
            "navn": "Konkurs Eksempel AS",
            "konkurs": True,
            "underAvvikling": False,
        }
    ]
    connector = BrregConnector(
        client=BrregClient(transport=_transport_with_entities(entities)),
        page_size=10,
    )
    signal = run_live_brreg_analysis("eksempel", connector=connector).scan.opportunities[0]

    for forbidden_target in (
        LifecycleState.HYPOTHESIS,
        LifecycleState.DECISION_CANDIDATE,
    ):
        try:
            signal.transition_to(forbidden_target)
        except ValueError:
            pass
        else:
            raise AssertionError(f"signal unexpectedly transitioned to {forbidden_target.value}")
