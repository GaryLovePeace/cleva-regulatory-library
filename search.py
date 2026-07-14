from __future__ import annotations

import hashlib
import io
from dataclasses import asdict, dataclass
from typing import Any

import requests
import trafilatura
from bs4 import BeautifulSoup
from pypdf import PdfReader

from config import SETTINGS
from source_registry import all_domains, source_metadata

USER_AGENT = "Cleva-Regulatory-Library/0.2 (+human-review-required)"

TOPIC_KEYWORDS: dict[str, list[str]] = {
    "Product Safety": ["product safety", "consumer product safety", "recall", "market surveillance"],
    "Electrical Safety": ["electrical safety", "low voltage", "electric appliance safety"],
    "Machinery": ["machinery safety", "machine regulation", "moving parts", "guarding"],
    "EMC": ["electromagnetic compatibility", "EMC"],
    "Radio / Wireless": ["radio equipment", "wireless", "Wi-Fi", "Bluetooth"],
    "Packaging / PPWR / EPR": ["packaging", "PPWR", "extended producer responsibility", "packaging EPR"],
    "Batteries": ["battery", "waste batteries", "portable batteries", "battery labelling"],
    "WEEE / Waste": ["WEEE", "electronic waste", "waste electrical equipment"],
    "Chemicals / REACH / RoHS / PFAS": ["REACH", "RoHS", "PFAS", "restricted substances", "SVHC"],
    "Ecodesign / Energy Efficiency": ["ecodesign", "energy efficiency", "energy labelling", "standby power"],
    "Cybersecurity / IoT": ["connected products cybersecurity", "IoT security", "software update"],
    "Labelling / Instructions": ["product labelling", "marking", "instructions", "warning label"],
    "Transport / Dangerous Goods": ["dangerous goods", "lithium battery transport", "UN 38.3"],
    "Trade / Market Access": ["technical regulation", "TBT notification", "market access", "conformity assessment"],
    "Noise / Vibration / Outdoor Equipment": ["outdoor equipment noise", "vibration", "lawn mower noise"],
    "Industry News / Market Intelligence": ["regulatory update", "industry policy", "compliance news"],
}

CHINESE_QUERY_TERMS: dict[str, str] = {
    "欧盟": "EU European Union",
    "欧洲": "EU Europe",
    "英国": "UK United Kingdom",
    "美国": "US United States",
    "加拿大": "Canada",
    "电池": "battery batteries",
    "包装": "packaging",
    "环保": "environmental environment",
    "法规": "regulation law rule",
    "标准": "standard",
    "吸尘器": "vacuum cleaner floorcare appliance",
    "湿干吸尘器": "wet dry vacuum",
    "割草机": "lawn mower",
    "园林工具": "lawn garden equipment",
    "回收": "recycling waste EPR",
    "化学品": "chemicals",
    "有害物质": "restricted substances hazardous substances",
    "能效": "energy efficiency ecodesign",
    "网络安全": "cybersecurity connected product",
    "标签": "labelling marking",
    "运输": "transport dangerous goods",
}


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    published_date: str | None = None
    matched_query: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def add_english_terms(query: str) -> str:
    additions = [english for chinese, english in CHINESE_QUERY_TERMS.items() if chinese in query]
    return " ".join([query, *additions]).strip()


def build_query_variants(query: str, topic: str, search_mode: str) -> list[str]:
    base = add_english_terms(query)
    if search_mode != "deep":
        return [base]

    variants = [base]
    topic_terms = TOPIC_KEYWORDS.get(topic, []) if topic and topic != "All" else []
    if topic_terms:
        variants.append(f"{base} {' OR '.join(topic_terms[:3])}")
    variants.extend(
        [
            f"{base} regulation directive act rule official guidance",
            f"{base} amendment implementing delegated regulation consultation proposed rule",
            f"{base} compliance deadline effective date regulator",
        ]
    )
    deduped: list[str] = []
    for item in variants:
        normalized = " ".join(item.split())
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    return deduped[: max(1, SETTINGS.deep_search_queries)]


def _query_with_domains(query: str, domains: list[str]) -> str:
    domain_clause = " OR ".join(f"site:{domain}" for domain in domains)
    return f"({query}) ({domain_clause})" if domain_clause else query


def search_brave(query: str, domains: list[str], count: int, *, broad: bool = False) -> list[SearchResult]:
    if not SETTINGS.brave_search_api_key:
        raise RuntimeError("BRAVE_SEARCH_API_KEY is not configured")
    final_query = query if broad else _query_with_domains(query, domains)
    resp = requests.get(
        "https://api.search.brave.com/res/v1/web/search",
        params={
            "q": final_query,
            "count": min(count, 20),
            "safesearch": "moderate",
            "search_lang": "en",
        },
        headers={"X-Subscription-Token": SETTINGS.brave_search_api_key, "Accept": "application/json"},
        timeout=SETTINGS.request_timeout,
    )
    resp.raise_for_status()
    items = resp.json().get("web", {}).get("results", [])
    return [
        SearchResult(
            title=item.get("title") or item.get("url", ""),
            url=item.get("url", ""),
            snippet=item.get("description") or "",
            published_date=item.get("page_age"),
            matched_query=query,
        )
        for item in items
        if item.get("url")
    ]


def search_serper(query: str, domains: list[str], count: int, *, broad: bool = False) -> list[SearchResult]:
    if not SETTINGS.serper_api_key:
        raise RuntimeError("SERPER_API_KEY is not configured")
    final_query = query if broad else _query_with_domains(query, domains)
    resp = requests.post(
        "https://google.serper.dev/search",
        json={"q": final_query, "num": min(count, 20)},
        headers={"X-API-KEY": SETTINGS.serper_api_key, "Content-Type": "application/json"},
        timeout=SETTINGS.request_timeout,
    )
    resp.raise_for_status()
    return [
        SearchResult(
            title=item.get("title") or item.get("link", ""),
            url=item.get("link", ""),
            snippet=item.get("snippet") or "",
            published_date=item.get("date"),
            matched_query=query,
        )
        for item in resp.json().get("organic", [])
        if item.get("link")
    ]


def search_federal_register(query: str, count: int = 20) -> list[SearchResult]:
    resp = requests.get(
        "https://www.federalregister.gov/api/v1/documents.json",
        params={"per_page": min(count, 100), "order": "newest", "conditions[term]": query},
        headers={"User-Agent": USER_AGENT},
        timeout=SETTINGS.request_timeout,
    )
    resp.raise_for_status()
    return [
        SearchResult(
            title=item.get("title") or "Federal Register document",
            url=item.get("html_url") or item.get("pdf_url"),
            snippet=item.get("abstract") or "",
            published_date=item.get("publication_date"),
            matched_query=query,
        )
        for item in resp.json().get("results", [])
        if item.get("html_url") or item.get("pdf_url")
    ]


def search_all(
    query: str,
    jurisdictions: list[str],
    provider: str | None = None,
    *,
    search_mode: str = "quick",
    topic: str = "All",
    selected_domains: list[str] | None = None,
) -> list[SearchResult]:
    provider = (provider or SETTINGS.search_provider).lower()
    scope = "official" if search_mode == "official" else "curated"
    domains = all_domains(jurisdictions, scope=scope, topic=topic, selected_domains=selected_domains)
    variants = build_query_variants(query, topic, search_mode)
    results: list[SearchResult] = []
    errors: list[str] = []

    # Keyless official connector. It remains useful even when Brave is unavailable.
    if "US Federal" in jurisdictions and search_mode in {"official", "deep"}:
        try:
            results.extend(search_federal_register(variants[0], SETTINGS.max_search_results))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Federal Register: {exc}")

    if provider in {"official-only", "none"}:
        pass
    elif provider not in {"brave", "serper"}:
        raise RuntimeError(f"Unsupported search provider: {provider}")
    else:
        search_fn = search_brave if provider == "brave" else search_serper
        for variant in variants:
            try:
                results.extend(search_fn(variant, domains, SETTINGS.max_search_results))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{provider}: {exc}")

        # Deep mode adds one broad-web discovery query. Non-curated results remain clearly marked
        # and must be verified before they can become a formal regulation record.
        if search_mode == "deep":
            try:
                results.extend(search_fn(variants[0], [], SETTINGS.max_search_results, broad=True))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{provider} broad search: {exc}")

    seen: set[str] = set()
    deduped: list[SearchResult] = []
    for item in results:
        normalized = item.url.split("#", 1)[0].rstrip("/")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        item.url = normalized
        deduped.append(item)

    if not deduped and errors:
        raise RuntimeError("; ".join(errors))
    limit = SETTINGS.max_deep_search_results if search_mode == "deep" else SETTINGS.max_search_results
    return deduped[:limit]


def fetch_document(url: str) -> tuple[str, str]:
    resp = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.8"},
        timeout=SETTINGS.request_timeout,
        allow_redirects=True,
    )
    resp.raise_for_status()
    content_type = (resp.headers.get("Content-Type") or "").lower()
    final_url = resp.url

    if "pdf" in content_type or final_url.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(resp.content))
        text = "\n".join((page.extract_text() or "") for page in reader.pages[:80])
    else:
        html = resp.text
        text = trafilatura.extract(html, include_links=False, include_tables=True) or ""
        if not text:
            text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
    return text[: SETTINGS.max_fetch_chars], final_url


def enrich_result(result: SearchResult, fetch_full_text: bool = True) -> dict[str, Any]:
    meta = source_metadata(result.url)
    text = ""
    final_url = result.url
    if fetch_full_text:
        try:
            text, final_url = fetch_document(result.url)
            meta = source_metadata(final_url)
        except Exception as exc:  # noqa: BLE001
            text = f"[Fetch failed: {exc}]\n{result.snippet}"
    content_hash = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest() if text else None
    return {
        **result.to_dict(),
        "url": final_url,
        "source_name": meta["source_name"],
        "source_domain": meta["domain"],
        "source_level": meta["source_level"],
        "source_type": meta["source_type"],
        "jurisdiction_group": meta["jurisdiction_group"],
        "is_official": meta["is_official"],
        "is_curated": meta["is_curated"],
        "verification_required": meta["verification_required"],
        "content_hash": content_hash,
        "extracted_text": text,
    }
