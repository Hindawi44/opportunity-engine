"""Guarded external research loop for Opportunity Engine.

Market-price evidence is governed by the V2.8.2B comparable evidence contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Callable, Iterable, Protocol

from .external_research.comparable_evidence import candidate_to_market_price_evidence


class SearchProvider(Protocol):
    def search(self, query: str, **kwargs: Any) -> Any: ...


class EvidenceSink(Protocol):
    def upsert(self, evidence: Any) -> Any: ...


@dataclass(frozen=True, slots=True)
class ResearchNeed:
    kind: str
    query: str
    reason: str
    priority: str = "medium"

    @property
    def need_id(self) -> str:
        key = f"{self.kind}|{self.query.casefold().strip()}"
        return "need_" + sha256(key.encode("utf-8")).hexdigest()[:20]


@dataclass(frozen=True, slots=True)
class ExternalEvidenceLoopResult:
    opportunity_id: str
    needs_detected: int
    searches_executed: int
    searches_skipped: int
    evidence_created: int
    evidence_updated: int
    buyers_found: int
    comparables_found: int
    scenarios_regenerated: bool
    errors: tuple[str, ...] = ()
    events: tuple[str, ...] = ()


@dataclass(slots=True)
class ExternalEvidenceLoop:
    search_provider: SearchProvider
    evidence_repository: EvidenceSink
    evidence_factory: Callable[..., Any]
    evidence_scorer: Any
    scenario_generator: Any
    market_comparables_engine: Any | None = None
    buyer_discovery_engine: Any | None = None
    comparable_adapter: Callable[[Any], Iterable[Any]] | None = None
    buyer_adapter: Callable[[Any], Iterable[Any]] | None = None
    max_searches_per_opportunity: int = 4
    search_history: set[str] = field(default_factory=set)

    def run(self, investment_file: Any) -> ExternalEvidenceLoopResult:
        opportunity_id = str(investment_file.opportunity_id)
        needs = self.detect_needs(investment_file)
        executed = skipped = created = updated = buyers_found = comparables_found = 0
        errors: list[str] = []
        events: list[str] = []
        evidence_changed = False
        linked_evidence_ids: list[str] = []

        for need in needs[: self.max_searches_per_opportunity]:
            key = self._search_key(opportunity_id, need.query)
            if key in self.search_history:
                skipped += 1
                events.append(f"search_skipped:{need.need_id}")
                continue
            self.search_history.add(key)
            try:
                response = self.search_provider.search(need.query)
                executed += 1
                events.append(f"search_executed:{need.need_id}")
            except Exception as exc:
                errors.append(f"search:{need.need_id}:{exc}")
                continue

            if need.kind == "market" and self.market_comparables_engine is not None:
                try:
                    candidates = tuple(self.comparable_adapter(response) if self.comparable_adapter else ())
                    result = self.market_comparables_engine.evaluate(candidates)
                    accepted = tuple(getattr(result, "accepted", ()))
                    comparables_found += len(accepted)
                    for candidate in accepted:
                        evidence = candidate_to_market_price_evidence(candidate, opportunity_id)
                        evidence.metadata["research_need"] = need.need_id
                        changed, evidence_id = self._persist_evidence(investment_file, evidence)
                        evidence_changed = evidence_changed or bool(changed)
                        if evidence_id:
                            linked_evidence_ids.append(evidence_id)
                        created += int(changed == "created")
                        updated += int(changed == "updated")
                except Exception as exc:
                    errors.append(f"comparables:{need.need_id}:{exc}")

            if need.kind == "buyer" and self.buyer_discovery_engine is not None:
                try:
                    candidates = tuple(self.buyer_adapter(response) if self.buyer_adapter else ())
                    result = self.buyer_discovery_engine.discover(
                        candidates,
                        opportunity_terms=self._opportunity_terms(investment_file),
                        opportunity_location=getattr(investment_file, "location", None),
                    )
                    accepted = tuple(getattr(result, "accepted", ()))
                    buyers_found += len(accepted)
                    for ranked in accepted:
                        candidate = getattr(ranked, "candidate", ranked)
                        name = str(getattr(candidate, "name", "Potential buyer"))
                        changed, evidence_id = self._store_external_evidence(
                            investment_file,
                            kind="buyer",
                            statement=f"{name} is an externally discovered potential buyer candidate; buying intent is unconfirmed.",
                            source_url=getattr(candidate, "website_url", None),
                            source_name="buyer_discovery_engine",
                            metadata={
                                "research_need": need.need_id,
                                "external": True,
                                "fit_score": getattr(ranked, "fit_score", None),
                                "confirmed_buying_intent": False,
                            },
                        )
                        evidence_changed = evidence_changed or bool(changed)
                        if evidence_id:
                            linked_evidence_ids.append(evidence_id)
                        created += int(changed == "created")
                        updated += int(changed == "updated")
                except Exception as exc:
                    errors.append(f"buyers:{need.need_id}:{exc}")

        regenerated = False
        if evidence_changed:
            try:
                self.scenario_generator.generate(
                    investment_file,
                    evidence_ids=tuple(dict.fromkeys(linked_evidence_ids)),
                )
                regenerated = True
                events.append("scenarios_regenerated")
            except Exception as exc:
                errors.append(f"scenarios:{exc}")
        else:
            events.append("scenarios_unchanged")

        return ExternalEvidenceLoopResult(
            opportunity_id=opportunity_id,
            needs_detected=len(needs),
            searches_executed=executed,
            searches_skipped=skipped,
            evidence_created=created,
            evidence_updated=updated,
            buyers_found=buyers_found,
            comparables_found=comparables_found,
            scenarios_regenerated=regenerated,
            errors=tuple(errors),
            events=tuple(events),
        )

    def detect_needs(self, investment_file: Any) -> tuple[ResearchNeed, ...]:
        needs: list[ResearchNeed] = []
        title = " ".join(str(getattr(investment_file, "title", "")).split())
        location = " ".join(str(getattr(investment_file, "location", "") or "").split())
        unresolved = " ".join(
            str(getattr(item, "question", ""))
            for item in tuple(getattr(investment_file, "missing_information", ()))
            if not bool(getattr(item, "resolved", False))
        ).casefold()
        has_market_value = any(
            getattr(path, "estimated_revenue_nok", None) is not None
            for path in getattr(investment_file, "revenue_paths", ())
        )
        if not has_market_value or any(word in unresolved for word in ("resale", "market", "price", "value")):
            needs.append(ResearchNeed("market", f'"{title}" brukt pris Norge'.strip(), "Verified external resale comparables are missing", "high"))
        potential_buyers = tuple(getattr(investment_file, "potential_buyers", ()))
        if not potential_buyers or any(word in unresolved for word in ("buyer", "customer", "purchaser")):
            suffix = f" {location}" if location else " Norge"
            needs.append(ResearchNeed("buyer", f'"{title}" forhandler grossist kjøper{suffix}'.strip(), "Potential buyers are missing", "high"))
        return tuple(needs)

    def _store_external_evidence(
        self,
        investment_file: Any,
        *,
        kind: str,
        statement: str,
        source_url: str | None,
        source_name: str,
        numeric_value: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[str | bool, str | None]:
        if kind == "market_price":
            raise ValueError("market_price evidence must use candidate_to_market_price_evidence")
        evidence = self.evidence_factory(
            opportunity_id=investment_file.opportunity_id,
            evidence_type=kind,
            statement=statement,
            source_name=source_name,
            source_url=source_url,
            numeric_value=numeric_value,
            currency="NOK" if numeric_value is not None else None,
            metadata=metadata or {},
        )
        return self._persist_evidence(investment_file, evidence)

    def _persist_evidence(self, investment_file: Any, evidence: Any) -> tuple[str | bool, str | None]:
        result = self.evidence_repository.upsert(evidence)
        stored = getattr(result, "evidence", evidence)
        peers = tuple(getattr(self.evidence_repository, "list_for_opportunity", lambda _id: ())(
            investment_file.opportunity_id
        ))
        score = self.evidence_scorer.score(stored, peers=peers)
        stored.metadata["external_evidence_score"] = getattr(score, "score", None)
        stored.metadata["external_evidence_grade"] = getattr(getattr(score, "grade", None), "value", None)
        self.evidence_repository.upsert(stored)

        evidence_id = getattr(stored, "evidence_id", None)
        if evidence_id and not any(
            str(getattr(item, "notes", "")) == f"research:{evidence_id}"
            for item in getattr(investment_file, "evidence", ())
        ):
            add = getattr(investment_file, "add_evidence", None)
            if callable(add):
                mirror = self._make_living_evidence(
                    str(getattr(stored, "statement", "")),
                    getattr(stored, "source_url", None),
                    str(getattr(stored, "source_name", "")),
                    str(evidence_id),
                )
                if mirror is not None:
                    add(mirror)
        if bool(getattr(result, "created", False)):
            return "created", evidence_id
        if bool(getattr(result, "observation_added", False)):
            return "updated", evidence_id
        return False, evidence_id

    @staticmethod
    def _make_living_evidence(statement: str, source_url: str | None, source_name: str, evidence_id: str) -> Any | None:
        try:
            from .living_investment_file import Confidence, Evidence
            return Evidence.create(
                statement,
                source_url=source_url,
                source_name=source_name,
                confidence=Confidence.MEDIUM,
                notes=f"research:{evidence_id}",
            )
        except Exception:
            return None

    @staticmethod
    def _opportunity_terms(investment_file: Any) -> tuple[str, ...]:
        text = f"{getattr(investment_file, 'title', '')} {getattr(investment_file, 'summary', '')}"
        stop = {"og", "med", "for", "til", "the", "and", "with"}
        return tuple(dict.fromkeys(
            token.casefold().strip(".,;:()[]{}")
            for token in text.split()
            if len(token.strip(".,;:()[]{}")) >= 4 and token.casefold() not in stop
        ))[:12]

    @staticmethod
    def _search_key(opportunity_id: str, query: str) -> str:
        raw = f"{opportunity_id}|{' '.join(query.casefold().split())}"
        return sha256(raw.encode("utf-8")).hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
