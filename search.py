from __future__ import annotations

import hashlib
import io
import re
from datetime import datetime, timedelta, timezone
from dataclasses import asdict, dataclass
from typing import Any, Iterable
from urllib.parse import urlparse

import requests
try:
    import trafilatura
except ImportError:
    trafilatura = None
from bs4 import BeautifulSoup
from pypdf import PdfReader

from config import SETTINGS
from source_registry import all_domains, source_metadata
from us_state_sources import (
    bill_prefix_allowed,
    detect_state,
    domain_belongs_to_state,
    full_bill_name,
    normalize_bill_prefix,
    state_abbreviation,
    state_domains,
)

USER_AGENT = "Cleva-Regulatory-Library/0.5 (+human-review-required)"

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

FEDERAL_DOMAINS = {"federalregister.gov", "ecfr.gov", "regulations.gov"}

CURRENT_YEAR = datetime.now(timezone.utc).year
SEARCH_GOAL_LATEST = "latest"
SEARCH_GOAL_CURRENT = "current"
SEARCH_GOAL_ALL = "all"

LATEST_TITLE_TERMS = (
    "update", "updated", "changes", "change", "amendment", "amending",
    "consultation", "guidance", "new rule", "new regulation", "effective",
    "implementation", "transitional", "notice", "news",
)
CURRENT_LAW_TITLE_TERMS = (
    "regulation", "regulations", "act", "directive", "statutory instrument",
    "consolidated", "current version", "code", "law",
)
STOP_QUERY_TERMS = {
    "governor", "official", "regulation", "regulations", "law", "laws",
    "rule", "rules", "update", "latest", "state", "states", "united",
    "government", "website", "source", "article",
}


@dataclass(frozen=True)
class QueryIntent:
    kind: str = "general"
    citation: str | None = None
    compact_citation: str | None = None
    full_citation: str | None = None
    state: str | None = None
    inferred_jurisdictions: tuple[str, ...] = ()
    priority_domains: tuple[str, ...] = ()
    required_terms: tuple[str, ...] = ()
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
    result_category: str = "其他资料"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _bill_match(raw: str) -> tuple[str, str] | None:
    # Long prefixes are intentionally listed first. Dots and spaces are accepted,
    # e.g. H.B. 123, SB343, LD 1541, A-1234.
    prefix_pattern = r"HJR|SJR|HCR|SCR|ACA|SCA|AJR|ACR|HSB|SSB|HB|SB|AB|HF|SF|HR|SR|LD|LB|LR|HP|SP|PR|B|H|S|A|J|K"
    match = re.search(
        rf"(?<![A-Za-z])({prefix_pattern})(?:\.|\s)*[- ]?\s*(\d{{1,6}}(?:-\d{{1,6}})?)(?!\d)",
        raw,
        flags=re.IGNORECASE,
    )
    if match:
        return normalize_bill_prefix(match.group(1)), match.group(2)

    full_match = re.search(
        r"\b(House|Senate|Assembly)\s+(Bill|File)\s+(\d{1,6})\b",
        raw,
        flags=re.IGNORECASE,
    )
    if not full_match:
        return None
    chamber = full_match.group(1).lower()
    doc_type = full_match.group(2).lower()
    if doc_type == "file":
        prefix = "HF" if chamber == "house" else "SF"
    elif chamber == "assembly":
        prefix = "AB"
    else:
        prefix = "HB" if chamber == "house" else "SB"
    return prefix, full_match.group(3)


def detect_query_intent(query: str, state_hint: str | None = None) -> QueryIntent:
    raw = " ".join(query.split())
    state = detect_state(raw, state_hint)
    bill = _bill_match(raw)

    if bill and state and bill_prefix_allowed(state, bill[0]):
        bill_type, number = bill
        citation = f"{bill_type} {number}"
        abbr = state_abbreviation(state)
        notes = (
            f"识别为{state}州级法案编号检索",
            "自动排除美国联邦来源，并仅搜索该州立法机构和环境主管部门",
            "结果必须包含准确法案编号才会保留",
        )
        return QueryIntent(
            kind="us_state_bill",
            citation=citation,
            compact_citation=f"{bill_type}{number}",
            full_citation=f"{full_bill_name(bill_type)} {number}",
            state=state,
            inferred_jurisdictions=("US States",),
            priority_domains=tuple(state_domains(state)),
            notes=notes + ((f"州缩写：{abbr}",) if abbr else ()),
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

    if "governor" in raw.lower():
        topic_tokens = [
            token.lower()
            for token in re.findall(r"[A-Za-z0-9-]{3,}", add_english_terms(raw))
            if token.lower() not in STOP_QUERY_TERMS
            and (not state or token.lower() not in state.lower().split())
        ]
        required = tuple(dict.fromkeys(["governor", *topic_tokens[:4]]))
        inferred = ("US States",) if state else ()
        notes = [
            "识别为Governor与法规主题的组合检索",
            "Governor不会被单独运行；结果必须同时匹配Governor和至少一个主题词",
        ]
        if state:
            notes.append(f"已识别州：{state}")
        return QueryIntent(
            kind="governor_topic",
            state=state,
            inferred_jurisdictions=inferred,
            priority_domains=tuple(state_domains(state)) if state else (),
            required_terms=required,
            notes=tuple(notes),
        )

    if state:
        return QueryIntent(
            kind="us_state_general",
            state=state,
            inferred_jurisdictions=("US States",),
            priority_domains=tuple(state_domains(state)),
            notes=(f"识别到{state}，本次仅搜索该州官方来源及精选专业来源",),
        )

    if bill and not state:
        return QueryIntent(
            kind="us_state_bill_missing_state",
            citation=f"{bill[0]} {bill[1]}",
            compact_citation=f"{bill[0]}{bill[1]}",
            full_citation=f"{full_bill_name(bill[0])} {bill[1]}",
            notes=("识别到州级法案编号，但无法判断州；请选择美国州筛选或在搜索词中写明州名",),
        )

    return QueryIntent()


def resolve_jurisdictions(
    query: str, jurisdictions: list[str], state_hint: str | None = None
) -> list[str]:
    intent = detect_query_intent(query, state_hint)
    if intent.inferred_jurisdictions:
        return list(intent.inferred_jurisdictions)
    return jurisdictions


def add_english_terms(query: str) -> str:
    additions = [english for chinese, english in CHINESE_QUERY_TERMS.items() if chinese in query]
    return " ".join([query, *additions]).strip()


def build_query_variants(
    query: str,
    topic: str,
    search_mode: str,
    state_hint: str | None = None,
    search_goal: str = SEARCH_GOAL_ALL,
) -> list[str]:
    intent = detect_query_intent(query, state_hint)
    base = add_english_terms(query)

    if intent.kind == "us_state_bill" and intent.citation and intent.state:
        exact = f'"{intent.citation}" "{intent.state}"'
        abbr = state_abbreviation(intent.state)
        if search_mode != "deep":
            return [exact]
        variants = [
            exact,
            f'"{intent.full_citation}" "{intent.state}"',
            f'"{intent.compact_citation}" "{intent.state}"',
        ]
        if abbr:
            variants.append(f'"{intent.citation}" "{abbr}"')
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

    if intent.kind == "governor_topic":
        quoted = " ".join(f'"{term}"' for term in intent.required_terms if term)
        if intent.state and f'"{intent.state}"' not in quoted:
            quoted = f'{quoted} "{intent.state}"'
        variants = [quoted or base]
        if search_goal == SEARCH_GOAL_LATEST or search_mode == "deep":
            variants.extend([
                f"{quoted or base} signed veto executive order {CURRENT_YEAR}",
                f"{quoted or base} latest policy announcement {CURRENT_YEAR}",
            ])
        return _dedupe_queries(variants)[: max(1, SETTINGS.deep_search_queries)]

    special_variants: list[str] = []
    if re.search(r"\bGB\s*CLP\b", query, flags=re.IGNORECASE):
        special_variants = [
            f'"GB CLP" latest update {CURRENT_YEAR}',
            f'"GB CLP" amendment regulations {CURRENT_YEAR}',
            f'"GB CLP" HSE changes {CURRENT_YEAR}',
            f'"Chemicals (Health and Safety)" "GB CLP" {CURRENT_YEAR}',
        ]

    if search_goal == SEARCH_GOAL_LATEST:
        variants = [
            *special_variants,
            f"{base} latest update amendment changes guidance {CURRENT_YEAR}",
            f"{base} regulator official update {CURRENT_YEAR}",
            f"{base} new rules effective date {CURRENT_YEAR}",
        ]
        if search_mode == "deep":
            variants.extend([
                f"{base} consultation proposed rule implementation {CURRENT_YEAR}",
                f"{base} {CURRENT_YEAR - 1} {CURRENT_YEAR} official notice",
            ])
        cap = max(2, SETTINGS.deep_search_queries if search_mode == "deep" else min(3, SETTINGS.deep_search_queries))
        return _dedupe_queries(variants)[:cap]

    if search_goal == SEARCH_GOAL_CURRENT:
        variants = [
            base,
            f"{base} official legislation current consolidated text",
            f"{base} regulation statutory instrument legal text",
        ]
        cap = max(1, SETTINGS.deep_search_queries if search_mode == "deep" else 2)
        return _dedupe_queries(variants)[:cap]

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


def _rank_domains(
    domains: list[str],
    intent: QueryIntent,
    search_mode: str,
    search_goal: str = SEARCH_GOAL_ALL,
    topic: str = "All",
) -> list[str]:
    unique = list(dict.fromkeys(domains))
    intent_priority = list(dict.fromkeys(domain for domain in intent.priority_domains if domain in unique))

    def goal_key(domain: str) -> tuple[int, int]:
        meta = source_metadata(f"https://{domain}")
        source_type = str(meta.get("source_type") or "").lower()
        name = str(meta.get("source_name") or "").lower()
        score = 0
        if search_goal == SEARCH_GOAL_LATEST:
            if "regulator" in source_type or "government guidance" in source_type:
                score += 40
            if "official state environmental agency" in source_type:
                score += 35
            if domain in {"hse.gov.uk", "gov.uk", "commission.europa.eu", "ec.europa.eu"}:
                score += 30
            if "legislation" in source_type:
                score += 15
        elif search_goal == SEARCH_GOAL_CURRENT:
            if "legislation" in source_type:
                score += 45
            if str(meta.get("source_level")) == "A":
                score += 20
        else:
            if str(meta.get("source_level")) == "A":
                score += 15
            elif str(meta.get("source_level")) == "B":
                score += 10
        if topic == "Chemicals / REACH / RoHS / PFAS" and domain == "hse.gov.uk":
            score += 25
        if "governor" in name and intent.kind != "governor_topic":
            score -= 25
        return score, -unique.index(domain)

    remainder = [domain for domain in unique if domain not in intent_priority]
    remainder.sort(key=goal_key, reverse=True)

    if intent.is_exact_legal_citation:
        cap = 4 if search_mode in {"quick", "official"} else 8
    elif intent.kind == "governor_topic":
        cap = 6 if search_mode in {"quick", "official"} else 10
    else:
        cap = 8 if search_mode == "quick" else (10 if search_mode == "official" else 14)
    return (intent_priority + remainder)[:cap]

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


def search_brave(
    query: str,
    domains: list[str],
    count: int,
    *,
    broad: bool = False,
    freshness: str | None = None,
) -> list[SearchResult]:
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
            **({"freshness": freshness} if freshness else {}),
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


def search_serper(
    query: str,
    domains: list[str],
    count: int,
    *,
    broad: bool = False,
    freshness: str | None = None,
) -> list[SearchResult]:
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


def freshness_for_range(time_range: str) -> str | None:
    now = datetime.now(timezone.utc).date()
    if time_range == "30d":
        return "pm"
    if time_range == "90d":
        start = now - timedelta(days=90)
        return f"{start.isoformat()}to{now.isoformat()}"
    if time_range == "1y":
        return "py"
    if time_range == "3y":
        start = now - timedelta(days=365 * 3)
        return f"{start.isoformat()}to{now.isoformat()}"
    return None


def _parse_result_date(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    relative = re.search(r"(\d+)\s+(day|week|month|year)s?\s+ago", raw, flags=re.IGNORECASE)
    if relative:
        amount = int(relative.group(1))
        unit = relative.group(2).lower()
        days = amount * {"day": 1, "week": 7, "month": 30, "year": 365}[unit]
        return datetime.now(timezone.utc) - timedelta(days=days)
    iso_match = re.search(r"(20\d{2}|19\d{2})-(\d{2})-(\d{2})", raw)
    if iso_match:
        try:
            return datetime(
                int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)),
                tzinfo=timezone.utc,
            )
        except ValueError:
            return None
    year_match = re.search(r"\b(20\d{2}|19\d{2})\b", raw)
    if year_match:
        return datetime(int(year_match.group(1)), 1, 1, tzinfo=timezone.utc)
    return None


def _age_days(value: str | None) -> int | None:
    parsed = _parse_result_date(value)
    if not parsed:
        return None
    return max(0, (datetime.now(timezone.utc) - parsed).days)


def _result_category(item: SearchResult) -> str:
    meta = source_metadata(item.url)
    source_type = str(meta.get("source_type") or "").lower()
    title = (item.title or "").lower()
    level = str(meta.get("source_level") or "D")
    if not bool(meta.get("is_official")):
        return "专业解读 / 法规情报"
    if "legislation" in source_type:
        return "正式法规原文"
    if any(term in title for term in LATEST_TITLE_TERMS) or "guidance" in source_type or "regulator" in source_type or "environmental agency" in source_type:
        return "官方更新 / 实施指南"
    if level == "A" and any(term in title for term in ("regulation", "regulations", "act", "statutory instrument", "directive")):
        return "正式法规原文"
    return "其他官方资料"


def _significant_query_terms(query: str, state: str | None = None) -> list[str]:
    terms: list[str] = []
    for token in re.findall(r"[A-Za-z0-9-]{3,}", add_english_terms(query)):
        lowered = token.lower()
        if lowered in STOP_QUERY_TERMS:
            continue
        if state and lowered in state.lower().split():
            continue
        if lowered not in terms:
            terms.append(lowered)
    return terms


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _score_result(
    item: SearchResult,
    query: str,
    jurisdictions: list[str],
    topic: str,
    intent: QueryIntent,
    search_goal: str = SEARCH_GOAL_ALL,
) -> tuple[int, list[str]]:
    title = item.title or ""
    snippet = item.snippet or ""
    combined = f"{title}\n{snippet}\n{item.url}"
    combined_lower = combined.lower()
    combined_normalized = _normalized(combined)
    meta = source_metadata(item.url)
    domain = str(meta.get("domain") or (urlparse(item.url).hostname or ""))
    source_type = str(meta.get("source_type") or "").lower()
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
        abbr = state_abbreviation(intent.state)
        if abbr and re.search(rf"\b{re.escape(abbr)}\b", combined):
            score += 8
            reasons.append(f"匹配州缩写{abbr} +8")
        if domain_belongs_to_state(domain, intent.state):
            score += 35
            reasons.append("州级优先来源 +35")
        if domain in FEDERAL_DOMAINS:
            score -= 120
            reasons.append("州级问题命中联邦法规源 -120")

    if intent.kind == "governor_topic":
        required = list(intent.required_terms) or ["governor", *_significant_query_terms(query, intent.state)[:3]]
        governor_hit = "governor" in combined_lower
        topic_terms = [term for term in required if term != "governor"]
        topic_hit_count = sum(1 for term in topic_terms if term.lower() in combined_lower)
        if governor_hit:
            score += 45
            reasons.append("匹配Governor +45")
        else:
            score -= 120
            reasons.append("未匹配Governor -120")
        if topic_terms and topic_hit_count:
            points = min(20 + topic_hit_count * 12, 56)
            score += points
            reasons.append(f"同时匹配法规主题词 +{points}")
        elif topic_terms:
            score -= 100
            reasons.append("未匹配Governor之外的法规主题词 -100")

    if topic and topic != "All":
        topic_hits = sum(1 for term in TOPIC_KEYWORDS.get(topic, []) if term.lower() in combined_lower)
        if topic_hits:
            points = min(topic_hits * 8, 24)
            score += points
            reasons.append(f"主题关键词匹配 +{points}")

    significant_tokens = _significant_query_terms(query, intent.state)
    token_hits = sum(1 for token in set(significant_tokens) if token in combined_lower)
    if token_hits:
        points = min(token_hits * 4, 24)
        score += points
        reasons.append(f"查询词匹配 +{points}")

    age_days = _age_days(item.published_date)
    title_lower = title.lower()
    title_years = [int(value) for value in re.findall(r"\b(20\d{2}|19\d{2})\b", title)]
    title_year = max(title_years) if title_years else None
    latest_term_hits = sum(1 for term in LATEST_TITLE_TERMS if term in title_lower)
    current_term_hits = sum(1 for term in CURRENT_LAW_TITLE_TERMS if term in title_lower)

    if search_goal == SEARCH_GOAL_LATEST:
        if "regulator" in source_type or "government guidance" in source_type or "environmental agency" in source_type:
            score += 28
            reasons.append("主管机构/实施来源 +28")
        if domain == "hse.gov.uk" and ("clp" in combined_lower or topic == "Chemicals / REACH / RoHS / PFAS"):
            score += 35
            reasons.append("GB CLP主管机构HSE +35")
        if latest_term_hits:
            points = min(18 + latest_term_hits * 5, 38)
            score += points
            reasons.append(f"更新/修订类标题 +{points}")
        if title_year == CURRENT_YEAR:
            score += 35
            reasons.append(f"标题包含当前年份{CURRENT_YEAR} +35")
        elif title_year == CURRENT_YEAR - 1:
            score += 18
            reasons.append(f"标题包含上一年份{CURRENT_YEAR - 1} +18")
        elif title_year and title_year <= CURRENT_YEAR - 5:
            score -= 30
            reasons.append(f"标题年份较旧({title_year}) -30")
        if age_days is not None:
            if age_days <= 31:
                score += 60
                reasons.append("近31天 +60")
            elif age_days <= 90:
                score += 50
                reasons.append("近90天 +50")
            elif age_days <= 365:
                score += 35
                reasons.append("近一年 +35")
            elif age_days <= 365 * 3:
                score += 15
                reasons.append("近三年 +15")
            elif age_days > 365 * 5:
                score -= 25
                reasons.append("超过五年的旧资料 -25")
        else:
            reasons.append("未识别发布日期，不加新鲜度分")
    elif search_goal == SEARCH_GOAL_CURRENT:
        if "legislation" in source_type:
            score += 40
            reasons.append("正式立法来源 +40")
        if current_term_hits:
            points = min(15 + current_term_hits * 4, 35)
            score += points
            reasons.append(f"法规原文/现行文本标题 +{points}")
        if latest_term_hits and "legislation" not in source_type:
            score -= 5
            reasons.append("动态新闻非原文 -5")
    else:
        if age_days is not None and age_days <= 365:
            score += 10
            reasons.append("近一年资料 +10")

    if jurisdictions == ["US States"] and domain in FEDERAL_DOMAINS:
        score -= 80
        reasons.append("仅州级检索时排除联邦结果 -80")

    return score, reasons

def _minimum_score(intent: QueryIntent) -> int:
    if intent.is_exact_legal_citation:
        return 40
    if intent.kind == "governor_topic":
        return 20
    if intent.kind == "us_state_general":
        return 5
    if intent.kind == "us_state_bill_missing_state":
        return 10_000
    return -20


def search_all(
    query: str,
    jurisdictions: list[str],
    provider: str | None = None,
    *,
    search_mode: str = "quick",
    topic: str = "All",
    selected_domains: list[str] | None = None,
    selected_states: list[str] | None = None,
    search_goal: str = SEARCH_GOAL_ALL,
    time_range: str = "all",
) -> list[SearchResult]:
    provider = (provider or SETTINGS.search_provider).lower()
    state_hint = selected_states[0] if selected_states and len(selected_states) == 1 else None
    intent = detect_query_intent(query, state_hint)
    effective_jurisdictions = resolve_jurisdictions(query, jurisdictions, state_hint)
    scope = "official" if search_mode == "official" else "curated"
    effective_states = [intent.state] if intent.state else (selected_states or None)
    domains = all_domains(
        effective_jurisdictions,
        scope=scope,
        topic=topic,
        selected_domains=selected_domains,
        selected_states=effective_states,
    )
    domains = _rank_domains(domains, intent, search_mode, search_goal, topic)
    variants = build_query_variants(query, topic, search_mode, state_hint, search_goal)
    freshness = freshness_for_range(time_range)
    results: list[SearchResult] = []
    errors: list[str] = []

    if intent.kind == "us_state_bill_missing_state":
        return []

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
                    results.extend(search_fn(variant, batch, per_call, freshness=freshness))
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{provider}: {exc}")

        broad_needed = search_mode == "deep" or intent.kind == "governor_topic"
        if broad_needed:
            try:
                results.extend(
                    search_fn(
                        variants[0], [], SETTINGS.max_search_results, broad=True, freshness=freshness
                    )
                )
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
            item, query, effective_jurisdictions, topic, intent, search_goal
        )
        item.result_category = _result_category(item)
        if item.relevance_score >= _minimum_score(intent):
            ranked.append(item)

    def sort_key(item: SearchResult) -> tuple[int, int, int, str]:
        category_weight = {
            "官方更新 / 实施指南": 3 if search_goal == SEARCH_GOAL_LATEST else 1,
            "正式法规原文": 3 if search_goal == SEARCH_GOAL_CURRENT else 2,
            "其他官方资料": 1,
            "专业解读 / 法规情报": 0,
        }.get(item.result_category, 0)
        official = 1 if source_metadata(item.url).get("is_official") else 0
        parsed = _parse_result_date(item.published_date)
        timestamp = int(parsed.timestamp()) if parsed else 0
        return item.relevance_score, category_weight, official, timestamp

    ranked.sort(key=sort_key, reverse=True)

    if not ranked and not results and errors:
        raise RuntimeError("; ".join(errors))
    limit = SETTINGS.max_deep_search_results if search_mode == "deep" else SETTINGS.max_search_results
    return ranked[:limit]


def preview_search_plan(
    query: str,
    jurisdictions: list[str],
    *,
    search_mode: str = "quick",
    topic: str = "All",
    selected_domains: list[str] | None = None,
    selected_states: list[str] | None = None,
    search_goal: str = SEARCH_GOAL_ALL,
    time_range: str = "all",
) -> dict[str, Any]:
    state_hint = selected_states[0] if selected_states and len(selected_states) == 1 else None
    intent = detect_query_intent(query, state_hint)
    effective_jurisdictions = resolve_jurisdictions(query, jurisdictions, state_hint)
    scope = "official" if search_mode == "official" else "curated"
    effective_states = [intent.state] if intent.state else (selected_states or None)
    domains = all_domains(
        effective_jurisdictions,
        scope=scope,
        topic=topic,
        selected_domains=selected_domains,
        selected_states=effective_states,
    )
    domains = _rank_domains(domains, intent, search_mode, search_goal, topic)
    variants = build_query_variants(query, topic, search_mode, state_hint, search_goal)
    actual_queries: list[str] = []
    for variant in variants:
        for batch in _domain_batches(variant, domains, exact_citation=intent.is_exact_legal_citation):
            actual_queries.append(_query_with_domains(variant, batch))
    if search_mode == "deep" or intent.kind == "governor_topic":
        actual_queries.append(variants[0] + "  [全网补充检索]")
    return {
        "intent": intent,
        "effective_jurisdictions": effective_jurisdictions,
        "domains": domains,
        "variants": variants,
        "actual_queries": actual_queries,
        "freshness": freshness_for_range(time_range),
    }

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
        text = ""
        if trafilatura is not None:
            try:
                text = trafilatura.extract(html, include_links=False, include_tables=True) or ""
            except Exception:
                text = ""
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
