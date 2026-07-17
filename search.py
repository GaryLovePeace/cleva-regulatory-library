from __future__ import annotations

import hashlib
import io
import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable
from urllib.parse import urlparse

import requests
import trafilatura
from bs4 import BeautifulSoup
from pypdf import PdfReader

from config import SETTINGS
from source_registry import all_domains, source_metadata

USER_AGENT = "Cleva-Regulatory-Library/0.3 (+human-review-required)"

TOPIC_KEYWORDS: dict[str, list[str]] = {
    "Product Safety": ["product safety", "consumer product safety", "recall", "market surveillance"],
    "Electrical Safety": ["electrical safety", "low voltage", "electric appliance safety"],
    "Machinery": ["machinery safety", "machine regulation", "moving parts", "guarding"],
    "EMC": ["electromagnetic compatibility", "EMC"],
    "Radio / Wireless": ["radio equipment", "wireless", "Wi-Fi", "Bluetooth"],
    "Packaging / PPWR / EPR": ["packaging", "recyclable", "recycling label", "PPWR", "extended producer responsibility", "packaging EPR"],
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
    "加州": "California",
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
    "可回收": "recyclable recycling",
    "化学品": "chemicals",
    "有害物质": "restricted substances hazardous substances",
    "能效": "energy efficiency ecodesign",
    "网络安全": "cybersecurity connected product",
    "标签": "labelling marking",
    "运输": "transport dangerous goods",
}

STATE_ALIASES: dict[str, tuple[str, ...]] = {
    "California": ("california", "calif", "ca", "加州"),
    "Washington": ("washington", "wa", "华盛顿州"),
    "Oregon": ("oregon", "or", "俄勒冈州"),
    "Colorado": ("colorado", "co", "科罗拉多州"),
    "Minnesota": ("minnesota", "mn", "明尼苏达州"),
}

STATE_PRIORITY_DOMAINS: dict[str, list[str]] = {
    "California": [
        "leginfo.legislature.ca.gov",
        "calrecycle.ca.gov",
        "gov.ca.gov",
        "oehha.ca.gov",
        "dtsc.ca.gov",
        "intertek.com",
    ],
    "Washington": ["apps.leg.wa.gov"],
    "Oregon": ["oregonlegislature.gov"],
    "Colorado": ["leg.colorado.gov"],
    "Minnesota": ["revisor.mn.gov"],
}

FEDERAL_DOMAINS = {"federalregister.gov", "ecfr.gov", "regulations.gov"}


@dataclass(frozen=True)
class QueryIntent:
    kind: str = "general"
    citation: str | None = None
    compact_citation: str | None = None
    full_citation: str | None = None
    state: str | None = None
    inferred_jurisdictions: tuple[str, ...] = ()
    priority_domains: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def is_exact_legal_citation(self) -> bool:
        return self.kind in {"us_state_bill", "eu_legal_act"}


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    published_date: str | None = None
    matched_query: str | None = None
    relevance_score: int = 0
    relevance_reasons: list[str] | None = None
    intent_kind: str = "general"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _contains_alias(text: str, alias: str) -> bool:
    if len(alias) <= 2 and alias.isascii():
        return bool(re.search(rf"\b{re.escape(alias)}\b", text, flags=re.IGNORECASE))
    return alias.lower() in text.lower()


def detect_query_intent(query: str) -> QueryIntent:
    raw = " ".join(query.split())
    lower = raw.lower()
    state: str | None = None
    for state_name, aliases in STATE_ALIASES.items():
        if any(_contains_alias(raw, alias) for alias in aliases):
            state = state_name
            break

    bill_match = re.search(r"\b(SB|AB)\s*[- ]?\s*(\d{1,4})\b", raw, flags=re.IGNORECASE)
    if bill_match and state:
        bill_type = bill_match.group(1).upper()
        number = bill_match.group(2)
        full_type = "Senate Bill" if bill_type == "SB" else "Assembly Bill"
        citation = f"{bill_type} {number}"
        notes = (
            f"识别为{state}州级法案编号检索",
            "自动排除美国联邦来源并优先州立法机构及主管部门",
            "结果必须包含准确法案编号才会保留",
        )
        return QueryIntent(
            kind="us_state_bill",
            citation=citation,
            compact_citation=f"{bill_type}{number}",
            full_citation=f"{full_type} {number}",
            state=state,
            inferred_jurisdictions=("US States",),
            priority_domains=tuple(STATE_PRIORITY_DOMAINS.get(state, [])),
            notes=notes,
        )

    eu_match = re.search(
        r"(?:regulation|directive)?\s*\(?EU\)?\s*(\d{4})\s*/\s*(\d+)",
        raw,
        flags=re.IGNORECASE,
    )
    if eu_match:
        citation = f"EU {eu_match.group(1)}/{eu_match.group(2)}"
        return QueryIntent(
            kind="eu_legal_act",
            citation=citation,
            compact_citation=citation.replace(" ", ""),
            full_citation=citation,
            inferred_jurisdictions=("EU",),
            priority_domains=("eur-lex.europa.eu", "commission.europa.eu", "ec.europa.eu"),
            notes=("识别为欧盟法规编号检索", "优先EUR-Lex并要求结果包含法规编号"),
        )

    if state:
        return QueryIntent(
            kind="us_state_general",
            state=state,
            inferred_jurisdictions=("US States",),
            priority_domains=tuple(STATE_PRIORITY_DOMAINS.get(state, [])),
            notes=(f"识别到{state}，优先州级来源",),
        )

    return QueryIntent()


def resolve_jurisdictions(query: str, jurisdictions: list[str]) -> list[str]:
    intent = detect_query_intent(query)
    if intent.inferred_jurisdictions:
        return list(intent.inferred_jurisdictions)
    return jurisdictions


def add_english_terms(query: str) -> str:
    additions = [english for chinese, english in CHINESE_QUERY_TERMS.items() if chinese in query]
    return " ".join([query, *additions]).strip()


def build_query_variants(query: str, topic: str, search_mode: str) -> list[str]:
    intent = detect_query_intent(query)
    base = add_english_terms(query)

    if intent.kind == "us_state_bill" and intent.citation and intent.state:
        exact = f'"{intent.citation}" "{intent.state}"'
        if search_mode != "deep":
            return [exact]
        variants = [
            exact,
            f'"{intent.full_citation}" "{intent.state}"',
            f'"{intent.compact_citation}" "{intent.state}"',
        ]
        topic_terms = TOPIC_KEYWORDS.get(topic, []) if topic and topic != "All" else []
        if topic_terms:
            variants.append(f"{exact} {' '.join(topic_terms[:2])}")
        return _dedupe_queries(variants)[: max(1, SETTINGS.deep_search_queries)]

    if intent.kind == "eu_legal_act" and intent.citation:
        exact = f'"{intent.citation}"'
        if search_mode != "deep":
            return [exact]
        return _dedupe_queries(
            [exact, f"{exact} consolidated text amendment", f"{exact} implementation guidance"]
        )[: max(1, SETTINGS.deep_search_queries)]

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
    return _dedupe_queries(variants)[: max(1, SETTINGS.deep_search_queries)]


def _dedupe_queries(queries: Iterable[str]) -> list[str]:
    deduped: list[str] = []
    for item in queries:
        normalized = " ".join(item.split())
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    return deduped


def _rank_domains(domains: list[str], intent: QueryIntent, search_mode: str) -> list[str]:
    unique = list(dict.fromkeys(domains))
    priority = [domain for domain in intent.priority_domains if domain in unique]
    remainder = [domain for domain in unique if domain not in priority]

    # Exact legal citations should not be diluted across dozens of unrelated sources.
    if intent.is_exact_legal_citation:
        cap = 4 if search_mode in {"quick", "official"} else 8
    else:
        cap = 8 if search_mode == "quick" else (10 if search_mode == "official" else 14)
    return (priority + remainder)[:cap]


def _domain_batches(query: str, domains: list[str], *, exact_citation: bool) -> list[list[str]]:
    if not domains:
        return [[]]
    if exact_citation:
        return [[domain] for domain in domains]

    batches: list[list[str]] = []
    current: list[str] = []
    for domain in domains:
        candidate = current + [domain]
        candidate_query = _query_with_domains(query, candidate)
        if current and (len(candidate) > 3 or len(candidate_query) > 340 or len(candidate_query.split()) > 44):
            batches.append(current)
            current = [domain]
        else:
            current = candidate
    if current:
        batches.append(current)
    return batches


def _query_with_domains(query: str, domains: list[str]) -> str:
    if not domains:
        return query
    if len(domains) == 1:
        return f"{query} site:{domains[0]}"
    domain_clause = " OR ".join(f"site:{domain}" for domain in domains)
    return f"{query} ({domain_clause})"


def search_brave(query: str, domains: list[str], count: int, *, broad: bool = False) -> list[SearchResult]:
    if not SETTINGS.brave_search_api_key:
        raise RuntimeError("BRAVE_SEARCH_API_KEY is not configured")
    final_query = query if broad else _query_with_domains(query, domains)
    if len(final_query) > 400 or len(final_query.split()) > 50:
        raise ValueError("Brave query exceeds API limits after domain filtering")
    resp = requests.get(
        "https://api.search.brave.com/res/v1/web/search",
        params={
            "q": final_query,
            "count": min(count, 20),
            "safesearch": "moderate",
            "search_lang": "en",
            "extra_snippets": "true",
        },
        headers={"X-Subscription-Token": SETTINGS.brave_search_api_key, "Accept": "application/json"},
        timeout=SETTINGS.request_timeout,
    )
    resp.raise_for_status()
    items = resp.json().get("web", {}).get("results", [])
    results: list[SearchResult] = []
    for item in items:
        if not item.get("url"):
            continue
        extra = item.get("extra_snippets") or []
        snippet_parts = [item.get("description") or "", *[str(value) for value in extra[:3]]]
        results.append(
            SearchResult(
                title=item.get("title") or item.get("url", ""),
                url=item.get("url", ""),
                snippet="\n".join(part for part in snippet_parts if part),
                published_date=item.get("page_age"),
                matched_query=query,
            )
        )
    return results


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


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _score_result(
    item: SearchResult,
    query: str,
    jurisdictions: list[str],
    topic: str,
    intent: QueryIntent,
) -> tuple[int, list[str]]:
    title = item.title or ""
    snippet = item.snippet or ""
    combined = f"{title}\n{snippet}\n{item.url}"
    combined_lower = combined.lower()
    combined_normalized = _normalized(combined)
    meta = source_metadata(item.url)
    domain = str(meta.get("domain") or (urlparse(item.url).hostname or ""))
    score = 0
    reasons: list[str] = []

    level = str(meta.get("source_level") or "D")
    level_points = {"A": 30, "B": 20, "C": 8, "D": 0}.get(level, 0)
    score += level_points
    if level_points:
        reasons.append(f"{level}级来源 +{level_points}")

    if intent.citation:
        citation_forms = [intent.citation, intent.compact_citation or "", intent.full_citation or ""]
        citation_norms = {_normalized(value) for value in citation_forms if value}
        title_norm = _normalized(title)
        snippet_norm = _normalized(snippet)
        if any(value and value in title_norm for value in citation_norms):
            score += 100
            reasons.append("标题精确匹配法规/法案编号 +100")
        elif any(value and value in snippet_norm for value in citation_norms):
            score += 70
            reasons.append("摘要精确匹配法规/法案编号 +70")
        elif any(value and value in combined_normalized for value in citation_norms):
            score += 45
            reasons.append("页面地址或其他内容匹配编号 +45")
        else:
            score -= 140
            reasons.append("未出现目标法规/法案编号 -140")

    if intent.state:
        if intent.state.lower() in combined_lower:
            score += 25
            reasons.append(f"匹配{intent.state} +25")
        if domain in set(STATE_PRIORITY_DOMAINS.get(intent.state, [])):
            score += 35
            reasons.append("州级优先来源 +35")
        if domain in FEDERAL_DOMAINS:
            score -= 120
            reasons.append("州级问题命中联邦法规源 -120")

    if topic and topic != "All":
        topic_hits = sum(1 for term in TOPIC_KEYWORDS.get(topic, []) if term.lower() in combined_lower)
        if topic_hits:
            points = min(topic_hits * 8, 24)
            score += points
            reasons.append(f"主题关键词匹配 +{points}")

    significant_tokens = [
        token.lower()
        for token in re.findall(r"[A-Za-z0-9]{3,}", add_english_terms(query))
        if token.lower() not in {"regulation", "official", "united", "states", "european"}
    ]
    token_hits = sum(1 for token in set(significant_tokens) if token in combined_lower)
    if token_hits:
        points = min(token_hits * 4, 24)
        score += points
        reasons.append(f"查询词匹配 +{points}")

    if jurisdictions == ["US States"] and domain in FEDERAL_DOMAINS:
        score -= 80
        reasons.append("仅州级检索时排除联邦结果 -80")

    return score, reasons


def _minimum_score(intent: QueryIntent) -> int:
    if intent.is_exact_legal_citation:
        return 40
    if intent.kind == "us_state_general":
        return 5
    return -20


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
    intent = detect_query_intent(query)
    effective_jurisdictions = resolve_jurisdictions(query, jurisdictions)
    scope = "official" if search_mode == "official" else "curated"
    domains = all_domains(effective_jurisdictions, scope=scope, topic=topic, selected_domains=selected_domains)
    domains = _rank_domains(domains, intent, search_mode)
    variants = build_query_variants(query, topic, search_mode)
    results: list[SearchResult] = []
    errors: list[str] = []

    # Do not query Federal Register for an explicitly state-level bill.
    if "US Federal" in effective_jurisdictions and search_mode in {"official", "deep"} and not intent.state:
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
            batches = _domain_batches(variant, domains, exact_citation=intent.is_exact_legal_citation)
            for batch in batches:
                try:
                    per_call = 8 if intent.is_exact_legal_citation else SETTINGS.max_search_results
                    results.extend(search_fn(variant, batch, per_call))
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{provider}: {exc}")

        if search_mode == "deep":
            try:
                results.extend(search_fn(variants[0], [], SETTINGS.max_search_results, broad=True))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{provider} broad search: {exc}")

    seen: set[str] = set()
    ranked: list[SearchResult] = []
    for item in results:
        normalized_url = item.url.split("#", 1)[0].rstrip("/")
        if not normalized_url or normalized_url in seen:
            continue
        seen.add(normalized_url)
        item.url = normalized_url
        item.intent_kind = intent.kind
        item.relevance_score, item.relevance_reasons = _score_result(
            item, query, effective_jurisdictions, topic, intent
        )
        if item.relevance_score >= _minimum_score(intent):
            ranked.append(item)

    ranked.sort(
        key=lambda item: (
            item.relevance_score,
            1 if source_metadata(item.url).get("is_official") else 0,
            item.published_date or "",
        ),
        reverse=True,
    )

    if not ranked and not results and errors:
        raise RuntimeError("; ".join(errors))
    limit = SETTINGS.max_deep_search_results if search_mode == "deep" else SETTINGS.max_search_results
    return ranked[:limit]


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
        "is_official": meta["is_official"],
        "is_curated": meta["is_curated"],
        "verification_required": meta["verification_required"],
        "jurisdiction_group": meta["jurisdiction_group"],
        "full_text": text,
        "content_hash": content_hash,
    }
