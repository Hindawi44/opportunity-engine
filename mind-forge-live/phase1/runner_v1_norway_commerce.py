from __future__ import annotations

import re

from . import norway_commerce_v1 as commerce
from . import runner_v1_geographic as geographic
from . import runner_v1_resilient as resilient
from .research_evidence_v1 import EvidenceObservation, EvidenceObservationOrigin


_ORIGINAL_PROFILE = resilient.research_profile_for_seed
_ORIGINAL_TEMPLATES = resilient.research_templates_for_seed
_ORIGINAL_GEOGRAPHIC_RELEVANCE = geographic._is_geographically_relevant
_ORIGINAL_SEMANTIC_RELEVANCE = geographic._is_semantically_relevant


def norway_commerce_profile_for_seed(seed: str) -> str:
    base_profile = _ORIGINAL_PROFILE(seed)
    if base_profile == "LOCAL_MARKET":
        return base_profile
    if commerce.is_norway_commerce_seed(seed):
        return "NORWAY_COMMERCE"
    return base_profile


def norway_commerce_templates_for_seed(seed: str):
    if norway_commerce_profile_for_seed(seed) == "NORWAY_COMMERCE":
        return commerce.norway_commerce_templates()
    return _ORIGINAL_TEMPLATES(seed)


def _source_text(observation: EvidenceObservation) -> str:
    return " ".join(
        value
        for value in (
            observation.source or "",
            observation.source_type or "",
            observation.source_ref or "",
            observation.observation_text or "",
        )
        if value
    ).casefold()


def _contains_marker(text: str, marker: str) -> bool:
    marker = marker.casefold()
    if " " in marker or "-" in marker:
        return marker in text
    return re.search(rf"(?<!\w){re.escape(marker)}(?!\w)", text) is not None


def norway_commerce_geographically_relevant(
    observation: EvidenceObservation,
    *,
    seed: str,
    question_label: str | None,
) -> bool:
    profile = norway_commerce_profile_for_seed(seed)
    if profile != "NORWAY_COMMERCE":
        return _ORIGINAL_GEOGRAPHIC_RELEVANCE(
            observation,
            seed=seed,
            question_label=question_label,
        )

    if observation.origin is not EvidenceObservationOrigin.LIVE_RESEARCH:
        return True
    if question_label not in commerce.NORWAY_EVIDENCE_REQUIRED_LABELS:
        return True

    host = geographic._hostname(observation.source_ref)
    if host.endswith(".test"):
        return True
    if host == "no" or host.endswith(".no"):
        return True

    text = _source_text(observation)
    return any(marker.casefold() in text for marker in commerce.NORWAY_MARKERS)


def norway_commerce_semantically_relevant(
    observation: EvidenceObservation,
    *,
    question_label: str | None,
) -> bool:
    if question_label not in commerce.COMMERCE_SEMANTIC_MARKERS:
        return _ORIGINAL_SEMANTIC_RELEVANCE(
            observation,
            question_label=question_label,
        )

    if observation.origin is not EvidenceObservationOrigin.LIVE_RESEARCH:
        return True
    host = geographic._hostname(observation.source_ref)
    if host.endswith(".test"):
        return True

    text = _source_text(observation)
    markers = commerce.COMMERCE_SEMANTIC_MARKERS[question_label]
    if not any(_contains_marker(text, marker) for marker in markers):
        return False

    if question_label == "norway resale pricing and margin":
        return bool(re.search(r"\d", text))
    return True


def install_norway_commerce_runner() -> None:
    resilient.research_profile_for_seed = norway_commerce_profile_for_seed
    resilient.research_templates_for_seed = norway_commerce_templates_for_seed
    geographic._is_geographically_relevant = norway_commerce_geographically_relevant
    geographic._is_semantically_relevant = norway_commerce_semantically_relevant
    geographic.install_geographic_runner()


def norway_commerce_main() -> int:
    install_norway_commerce_runner()
    return geographic.base.main()


if __name__ == "__main__":
    raise SystemExit(norway_commerce_main())
