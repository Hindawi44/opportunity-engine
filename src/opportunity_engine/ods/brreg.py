"""Official Brønnøysund Register Centre entity connector for ODS.

Uses the public Enhetsregisteret API and normalizes company/entity records into
``SourceDocument`` evidence. Network access is isolated behind an injectable
transport so unit tests remain deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .live_data import SourceDocument
from .models import ODSRequest

BRREG_API_BASE = "https://data.brreg.no/enhetsregisteret/api"
BRREG_ENTITY_MEDIA_TYPE = "application/vnd.brreg.enhetsregisteret.enhet.v2+json"
JsonTransport = Callable[[str, float, dict[str, str]], Any]


def _default_json_transport(url: str, timeout: float, headers: dict[str, str]) -> Any:
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed HTTPS API base
            charset = response.headers.get_content_charset() or "utf-8"
            return json.loads(response.read().decode(charset))
    except HTTPError as exc:
        raise RuntimeError(f"Brreg API returned HTTP {exc.code} for {url}") from exc
    except URLError as exc:
        raise RuntimeError(f"Brreg API request failed for {url}: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Brreg API returned invalid JSON for {url}") from exc


@dataclass(frozen=True)
class BrregClient:
    """Small client for public Enhetsregisteret entity endpoints."""

    timeout: float = 15.0
    base_url: str = BRREG_API_BASE
    transport: JsonTransport = _default_json_transport

    def __post_init__(self) -> None:
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")
        if not self.base_url.startswith("https://"):
            raise ValueError("Brreg base_url must use HTTPS")

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Accept": BRREG_ENTITY_MEDIA_TYPE,
            "User-Agent": "ODS-Opportunity-Engine/0.3",
        }

    def search_entities(
        self,
        *,
        name: str | None = None,
        municipality: str | None = None,
        industry_code: str | None = None,
        page_size: int = 20,
    ) -> tuple[dict[str, Any], ...]:
        if not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        params: dict[str, Any] = {"size": page_size}
        if name and name.strip():
            params["navn"] = name.strip()
        if municipality and municipality.strip():
            params["forretningsadresse.kommune"] = municipality.strip()
        if industry_code and industry_code.strip():
            params["naeringskode"] = industry_code.strip()
        payload = self.transport(
            f"{self.base_url}/enheter?{urlencode(params)}",
            self.timeout,
            self.headers,
        )
        if not isinstance(payload, dict):
            raise RuntimeError("Brreg entity search returned an unexpected payload")
        embedded = payload.get("_embedded", {})
        entities = embedded.get("enheter", ()) if isinstance(embedded, dict) else ()
        if not isinstance(entities, list):
            raise RuntimeError("Brreg entity search returned invalid entity data")
        return tuple(item for item in entities if isinstance(item, dict))

    def get_entity(self, organisation_number: str) -> dict[str, Any]:
        orgnr = self._validated_orgnr(organisation_number)
        payload = self.transport(
            f"{self.base_url}/enheter/{orgnr}", self.timeout, self.headers
        )
        if not isinstance(payload, dict):
            raise RuntimeError("Brreg entity lookup returned an unexpected payload")
        return payload

    @staticmethod
    def _validated_orgnr(value: str) -> str:
        normalized = value.replace(" ", "").strip()
        if len(normalized) != 9 or not normalized.isdigit():
            raise ValueError("organisation number must contain exactly nine digits")
        return normalized


@dataclass(frozen=True)
class BrregConnector:
    """Search and normalize public Norwegian entity records for one ODS request."""

    client: BrregClient = BrregClient()
    municipality: str | None = None
    industry_code: str | None = None
    page_size: int = 20
    name: str = "brreg_enhetsregisteret_v2"

    def fetch(self, request: ODSRequest) -> tuple[SourceDocument, ...]:
        entities = self.client.search_entities(
            name=request.subject,
            municipality=self.municipality,
            industry_code=self.industry_code,
            page_size=self.page_size,
        )
        return tuple(self._to_document(entity, request) for entity in entities)

    @staticmethod
    def _to_document(entity: dict[str, Any], request: ODSRequest) -> SourceDocument:
        orgnr = str(entity.get("organisasjonsnummer") or "").strip()
        title = str(entity.get("navn") or f"Brreg entity {orgnr or 'unknown'}").strip()
        if not orgnr:
            raise RuntimeError("Brreg entity is missing organisasjonsnummer")

        organisation_form = _nested_text(entity, "organisasjonsform", "beskrivelse")
        industry_code = _nested_text(entity, "naeringskode1", "kode")
        industry_label = _nested_text(entity, "naeringskode1", "beskrivelse")
        municipality = _nested_text(entity, "forretningsadresse", "kommune")
        registration_date = _optional_text(entity.get("registreringsdatoEnhetsregisteret"))
        bankrupt = bool(entity.get("konkurs"))
        liquidation = bool(entity.get("underAvvikling"))

        details = [f"Registered Norwegian entity: {title} ({orgnr})."]
        if organisation_form:
            details.append(f"Organisation form: {organisation_form}.")
        if industry_code or industry_label:
            details.append(f"Industry: {industry_code or '?'} {industry_label or ''}.".strip())
        if municipality:
            details.append(f"Municipality: {municipality}.")
        details.append(f"Bankruptcy flag: {bankrupt}; liquidation flag: {liquidation}.")

        return SourceDocument(
            document_id=f"brreg-entity-{orgnr}",
            source_name="Brønnøysundregistrene",
            source_type="official_business_register",
            title=title,
            text=" ".join(details),
            url=f"https://data.brreg.no/enhetsregisteret/oppslag/enheter/{orgnr}",
            country="Norway",
            metadata={
                "organisation_number": orgnr,
                "organisation_form": organisation_form,
                "industry_code": industry_code,
                "industry_label": industry_label,
                "municipality": municipality,
                "registration_date": registration_date,
                "bankrupt": bankrupt,
                "under_liquidation": liquidation,
                "request_subject": request.subject,
            },
        )


def _nested_text(payload: dict[str, Any], parent: str, child: str) -> str | None:
    value = payload.get(parent)
    if not isinstance(value, dict):
        return None
    return _optional_text(value.get(child))


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
