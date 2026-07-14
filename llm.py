from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from config import SETTINGS

SYSTEM_PROMPT = """You are a regulatory-document extraction assistant for Cleva, a manufacturer and exporter of vacuum cleaners, wet/dry vacuums, floor-care appliances, lawn and garden equipment, batteries, chargers, packaging and connected products.

Return only valid JSON. Never invent a regulation number, legal status or date. Use null when the source does not prove a field. Distinguish binding law, proposed rule, consultation, official guidance, technical standard and news release. The output is preliminary and must be reviewed by a human.

Required JSON keys:
record_type, original_title, chinese_title, regulation_number, jurisdiction, country, state_province, authority, document_type, legal_status, publication_date, entry_into_force_date, application_date, compliance_deadline, topics, business_lines, relevance_level, summary_cn, cleva_impact, pdf_url, related_official_url, evidence_quotes, uncertainty_notes.

Allowed record_type: Regulation, Regulatory Intelligence, Unclear. Use Regulation only when the source itself is binding law, an official proposed rule, consultation, official guidance or an official legal database record. Use Regulatory Intelligence for professional articles, media reports, testing-body updates, consulting commentary, PRO operational notices or industry news.

Allowed relevance_level: High, Medium, Low, Unclear.
Allowed business_lines: Wet/Dry Vacuum, Household Floorcare, Lawn & Garden, Batteries & Chargers, Packaging, All Products.
Dates must be YYYY-MM-DD when clearly stated, otherwise null.
evidence_quotes must contain short source excerpts or section references supporting the extracted fields."""


def _client_and_model() -> tuple[OpenAI, str]:
    if SETTINGS.llm_provider == "deepseek":
        if not SETTINGS.deepseek_api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is not configured")
        return (
            OpenAI(api_key=SETTINGS.deepseek_api_key, base_url="https://api.deepseek.com"),
            SETTINGS.deepseek_model,
        )
    if SETTINGS.llm_provider == "openai":
        if not SETTINGS.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        return OpenAI(api_key=SETTINGS.openai_api_key), SETTINGS.openai_model
    raise RuntimeError("LLM provider is disabled")


def analyze_document(item: dict[str, Any], query: str, topic: str) -> dict[str, Any]:
    if SETTINGS.llm_provider == "none":
        return {
            "record_type": "Unclear",
            "original_title": item.get("title"),
            "chinese_title": None,
            "jurisdiction": item.get("jurisdiction_group"),
            "topics": [topic] if topic else [],
            "relevance_level": "Unclear",
            "summary_cn": item.get("snippet"),
            "uncertainty_notes": ["LLM analysis disabled"],
        }

    client, model = _client_and_model()
    user_content = {
        "search_query": query,
        "selected_topic": topic,
        "source_url": item.get("url"),
        "source_title": item.get("title"),
        "search_snippet": item.get("snippet"),
        "official_source": item.get("is_official"),
        "source_level": item.get("source_level"),
        "document_text": (item.get("extracted_text") or "")[:50000],
    }
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_content, ensure_ascii=False)},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    raw = response.choices[0].message.content or "{}"
    return json.loads(raw)
