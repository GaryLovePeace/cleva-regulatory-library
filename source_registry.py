from __future__ import annotations

from typing import Iterable
from urllib.parse import urlparse

# Levels used by the MVP:
# A = official legislation / official legal database
# B = regulator, government guidance, official notification or authorised operator
# C = professional testing, certification or regulatory consulting source
# D = industry media, company commentary or general intelligence source

SOURCES: list[dict[str, object]] = [
    # ---------------- EU ----------------
    {
        "domain": "eur-lex.europa.eu", "name": "EUR-Lex", "level": "A",
        "source_type": "Official legislation", "is_official": True,
        "markets": ["EU"], "topics": ["All"],
        "monitoring_urls": ["https://eur-lex.europa.eu/"],
        "notes": "欧盟法律、官方公报、合并文本及修订关系。",
    },
    {
        "domain": "commission.europa.eu", "name": "European Commission", "level": "B",
        "source_type": "Regulator / government guidance", "is_official": True,
        "markets": ["EU"], "topics": ["All"],
        "monitoring_urls": ["https://commission.europa.eu/law/law-topic_en"],
        "notes": "政策、实施信息、指南、咨询和FAQ。",
    },
    {
        "domain": "ec.europa.eu", "name": "European Commission legacy pages", "level": "B",
        "source_type": "Regulator / government guidance", "is_official": True,
        "markets": ["EU"], "topics": ["All"],
        "monitoring_urls": ["https://ec.europa.eu/"],
        "notes": "欧委会旧域名中的监管资料。",
    },
    {
        "domain": "echa.europa.eu", "name": "ECHA", "level": "B",
        "source_type": "Regulator / government guidance", "is_official": True,
        "markets": ["EU"],
        "topics": ["Chemicals / REACH / RoHS / PFAS", "Batteries", "Packaging / PPWR / EPR"],
        "monitoring_urls": ["https://echa.europa.eu/"],
        "notes": "REACH、CLP、限制物质、候选清单和化学品指南。",
    },
    {
        "domain": "single-market-economy.ec.europa.eu", "name": "EU Single Market", "level": "B",
        "source_type": "Regulator / government guidance", "is_official": True,
        "markets": ["EU"], "topics": ["All"],
        "monitoring_urls": ["https://single-market-economy.ec.europa.eu/"],
        "notes": "产品法规、协调标准、市场准入和工业政策。",
    },
    # ---------------- UK ----------------
    {
        "domain": "legislation.gov.uk", "name": "UK Legislation", "level": "A",
        "source_type": "Official legislation", "is_official": True,
        "markets": ["UK"], "topics": ["All"],
        "monitoring_urls": ["https://www.legislation.gov.uk/"],
        "notes": "英国法案和法定文书。",
    },
    {
        "domain": "gov.uk", "name": "GOV.UK", "level": "B",
        "source_type": "Regulator / government guidance", "is_official": True,
        "markets": ["UK"], "topics": ["All"],
        "monitoring_urls": ["https://www.gov.uk/search/policy-papers-and-consultations"],
        "notes": "监管指南、咨询、EPR、产品安全和市场监督。",
    },
    {
        "domain": "hse.gov.uk", "name": "UK HSE", "level": "B",
        "source_type": "Regulator / government guidance", "is_official": True,
        "markets": ["UK"],
        "topics": ["Product Safety", "Machinery", "Chemicals / REACH / RoHS / PFAS", "Noise / Vibration / Outdoor Equipment"],
        "monitoring_urls": ["https://www.hse.gov.uk/"],
        "notes": "机械、工作场所安全、化学品和噪声等。",
    },
    # ---------------- US federal ----------------
    {
        "domain": "federalregister.gov", "name": "Federal Register", "level": "A",
        "source_type": "Official legislation", "is_official": True,
        "markets": ["US Federal"], "topics": ["All"],
        "monitoring_urls": ["https://www.federalregister.gov/"],
        "notes": "联邦拟议规则、最终规则、通知和咨询。",
    },
    {
        "domain": "ecfr.gov", "name": "eCFR", "level": "A",
        "source_type": "Official legislation", "is_official": True,
        "markets": ["US Federal"], "topics": ["All"],
        "monitoring_urls": ["https://www.ecfr.gov/"],
        "notes": "当前联邦法规汇编文本。",
    },
    {
        "domain": "regulations.gov", "name": "Regulations.gov", "level": "A",
        "source_type": "Official legislation", "is_official": True,
        "markets": ["US Federal"], "topics": ["All"],
        "monitoring_urls": ["https://www.regulations.gov/"],
        "notes": "Docket、拟议规则和公众意见。",
    },
    {
        "domain": "cpsc.gov", "name": "US CPSC", "level": "B",
        "source_type": "Regulator / government guidance", "is_official": True,
        "markets": ["US Federal"], "topics": ["Product Safety", "Batteries", "Labelling / Instructions"],
        "monitoring_urls": ["https://www.cpsc.gov/Newsroom"],
        "notes": "消费品安全、召回、事故报告和指南。",
    },
    {
        "domain": "epa.gov", "name": "US EPA", "level": "B",
        "source_type": "Regulator / government guidance", "is_official": True,
        "markets": ["US Federal"],
        "topics": ["Chemicals / REACH / RoHS / PFAS", "Packaging / PPWR / EPR", "WEEE / Waste", "Batteries"],
        "monitoring_urls": ["https://www.epa.gov/laws-regulations"],
        "notes": "环境、化学品、废弃物和EPR。",
    },
    {
        "domain": "energy.gov", "name": "US DOE", "level": "B",
        "source_type": "Regulator / government guidance", "is_official": True,
        "markets": ["US Federal"], "topics": ["Ecodesign / Energy Efficiency"],
        "monitoring_urls": ["https://www.energy.gov/eere/buildings/appliance-and-equipment-standards-program"],
        "notes": "家电和设备能效规则。",
    },
    {
        "domain": "fcc.gov", "name": "US FCC", "level": "B",
        "source_type": "Regulator / government guidance", "is_official": True,
        "markets": ["US Federal"], "topics": ["EMC", "Radio / Wireless", "Cybersecurity / IoT"],
        "monitoring_urls": ["https://www.fcc.gov/"],
        "notes": "无线通信和电磁干扰要求。",
    },
    {
        "domain": "phmsa.dot.gov", "name": "US PHMSA", "level": "B",
        "source_type": "Regulator / government guidance", "is_official": True,
        "markets": ["US Federal"], "topics": ["Transport / Dangerous Goods", "Batteries"],
        "monitoring_urls": ["https://www.phmsa.dot.gov/"],
        "notes": "危险品及锂电池运输。",
    },
    # ---------------- US states ----------------
    {
        "domain": "calrecycle.ca.gov", "name": "CalRecycle", "level": "B",
        "source_type": "Regulator / government guidance", "is_official": True,
        "markets": ["US States"], "topics": ["Packaging / PPWR / EPR", "WEEE / Waste", "Batteries"],
        "monitoring_urls": ["https://calrecycle.ca.gov/"],
        "notes": "加州包装、回收和生产者责任。",
    },
    {
        "domain": "oehha.ca.gov", "name": "California OEHHA", "level": "B",
        "source_type": "Regulator / government guidance", "is_official": True,
        "markets": ["US States"], "topics": ["Chemicals / REACH / RoHS / PFAS", "Labelling / Instructions"],
        "monitoring_urls": ["https://oehha.ca.gov/proposition-65"],
        "notes": "California Proposition 65。",
    },
    {
        "domain": "dtsc.ca.gov", "name": "California DTSC", "level": "B",
        "source_type": "Regulator / government guidance", "is_official": True,
        "markets": ["US States"], "topics": ["Chemicals / REACH / RoHS / PFAS", "WEEE / Waste"],
        "monitoring_urls": ["https://dtsc.ca.gov/"],
        "notes": "加州有害物质和Safer Consumer Products。",
    },
    {
        "domain": "leginfo.legislature.ca.gov", "name": "California Legislature", "level": "A",
        "source_type": "Official legislation", "is_official": True,
        "markets": ["US States"], "topics": ["All"],
        "monitoring_urls": ["https://leginfo.legislature.ca.gov/"],
        "notes": "加州法案和法典。",
    },
    {
        "domain": "apps.leg.wa.gov", "name": "Washington Legislature", "level": "A",
        "source_type": "Official legislation", "is_official": True,
        "markets": ["US States"], "topics": ["All"],
        "monitoring_urls": ["https://apps.leg.wa.gov/"],
        "notes": "华盛顿州法规和法案。",
    },
    {
        "domain": "oregonlegislature.gov", "name": "Oregon Legislature", "level": "A",
        "source_type": "Official legislation", "is_official": True,
        "markets": ["US States"], "topics": ["All"],
        "monitoring_urls": ["https://www.oregonlegislature.gov/"],
        "notes": "俄勒冈州法规和法案。",
    },
    {
        "domain": "leg.colorado.gov", "name": "Colorado Legislature", "level": "A",
        "source_type": "Official legislation", "is_official": True,
        "markets": ["US States"], "topics": ["All"],
        "monitoring_urls": ["https://leg.colorado.gov/"],
        "notes": "科罗拉多州法规和法案。",
    },
    {
        "domain": "revisor.mn.gov", "name": "Minnesota Revisor", "level": "A",
        "source_type": "Official legislation", "is_official": True,
        "markets": ["US States"], "topics": ["All"],
        "monitoring_urls": ["https://www.revisor.mn.gov/"],
        "notes": "明尼苏达州法规和法案。",
    },
    # ---------------- Canada ----------------
    {
        "domain": "laws-lois.justice.gc.ca", "name": "Justice Laws", "level": "A",
        "source_type": "Official legislation", "is_official": True,
        "markets": ["Canada Federal"], "topics": ["All"],
        "monitoring_urls": ["https://laws-lois.justice.gc.ca/eng/"],
        "notes": "加拿大联邦法律和合并法规。",
    },
    {
        "domain": "gazette.gc.ca", "name": "Canada Gazette", "level": "A",
        "source_type": "Official legislation", "is_official": True,
        "markets": ["Canada Federal"], "topics": ["All"],
        "monitoring_urls": ["https://gazette.gc.ca/"],
        "notes": "拟议法规、正式法规和政府公告。",
    },
    {
        "domain": "canada.ca", "name": "Government of Canada", "level": "B",
        "source_type": "Regulator / government guidance", "is_official": True,
        "markets": ["Canada Federal"], "topics": ["All"],
        "monitoring_urls": ["https://www.canada.ca/en/government/system/consultations/consultingcanadians.html"],
        "notes": "各联邦部门法规、指南和咨询。",
    },
    {
        "domain": "tc.canada.ca", "name": "Transport Canada", "level": "B",
        "source_type": "Regulator / government guidance", "is_official": True,
        "markets": ["Canada Federal"], "topics": ["Transport / Dangerous Goods", "Batteries"],
        "monitoring_urls": ["https://tc.canada.ca/en/dangerous-goods"],
        "notes": "危险品和锂电池运输。",
    },
    {
        "domain": "ised-isde.canada.ca", "name": "ISED Canada", "level": "B",
        "source_type": "Regulator / government guidance", "is_official": True,
        "markets": ["Canada Federal"], "topics": ["EMC", "Radio / Wireless", "Cybersecurity / IoT"],
        "monitoring_urls": ["https://ised-isde.canada.ca/"],
        "notes": "无线、EMC和市场准入。",
    },
    {
        "domain": "ontario.ca", "name": "Ontario", "level": "B",
        "source_type": "Regulator / government guidance", "is_official": True,
        "markets": ["Canada Provinces"], "topics": ["All"],
        "monitoring_urls": ["https://www.ontario.ca/laws"],
        "notes": "安大略省法规和指南。",
    },
    {
        "domain": "bclaws.gov.bc.ca", "name": "BC Laws", "level": "A",
        "source_type": "Official legislation", "is_official": True,
        "markets": ["Canada Provinces"], "topics": ["All"],
        "monitoring_urls": ["https://www.bclaws.gov.bc.ca/"],
        "notes": "不列颠哥伦比亚省法规。",
    },
    {
        "domain": "legisquebec.gouv.qc.ca", "name": "LégisQuébec", "level": "A",
        "source_type": "Official legislation", "is_official": True,
        "markets": ["Canada Provinces"], "topics": ["All"],
        "monitoring_urls": ["https://www.legisquebec.gouv.qc.ca/"],
        "notes": "魁北克省法规。",
    },
    {
        "domain": "alberta.ca", "name": "Alberta", "level": "B",
        "source_type": "Regulator / government guidance", "is_official": True,
        "markets": ["Canada Provinces"], "topics": ["All"],
        "monitoring_urls": ["https://www.alberta.ca/alberta-kings-printer"],
        "notes": "阿尔伯塔省法规和指南。",
    },
    # ---------------- Curated professional / intelligence sources ----------------
    {
        "domain": "intertek.com.cn", "name": "Intertek China Regulatory & Standards", "level": "C",
        "source_type": "Testing / certification body", "is_official": False,
        "markets": ["Global"], "topics": ["All"],
        "monitoring_urls": ["https://www.intertek.com.cn/Regulatorystandard"],
        "notes": "产品法规、标准、认证和召回信息。仅作线索和解读，需回到官方原文。",
    },
    {
        "domain": "tbt.org.cn", "name": "技术性贸易措施资讯网", "level": "B",
        "source_type": "Authoritative notification platform", "is_official": False,
        "markets": ["Global"], "topics": ["Trade / Market Access", "Product Safety", "All"],
        "monitoring_urls": [
            "http://www.tbt.org.cn/index.html",
            "http://www.tbt.org.cn/newsReading.html?type=news",
            "http://www.tbt.org.cn/warningInfo.html",
        ],
        "notes": "TBT/SPS通报、新闻速递和预警信息。应继续核验原始通报及外国官方法规。",
    },
    {
        "domain": "reach24h.com", "name": "REACH24H", "level": "C",
        "source_type": "Regulatory consulting", "is_official": False,
        "markets": ["Global"],
        "topics": ["Chemicals / REACH / RoHS / PFAS", "Batteries", "Packaging / PPWR / EPR", "Trade / Market Access"],
        "monitoring_urls": ["https://www.reach24h.com/"],
        "notes": "化学品、材料、电池和全球市场准入法规解读。",
    },
    {
        "domain": "incompliancemag.com", "name": "In Compliance Magazine", "level": "D",
        "source_type": "Industry media", "is_official": False,
        "markets": ["Global"],
        "topics": ["EMC", "Radio / Wireless", "Electrical Safety", "Product Safety", "Cybersecurity / IoT"],
        "monitoring_urls": ["https://incompliancemag.com/"],
        "notes": "EMC、电气安全、无线和产品合规行业文章。",
    },
    {
        "domain": "deutsche-recycling.com", "name": "Deutsche Recycling", "level": "C",
        "source_type": "EPR compliance service", "is_official": False,
        "markets": ["EU"],
        "topics": ["Packaging / PPWR / EPR", "WEEE / Waste", "Batteries"],
        "monitoring_urls": ["https://deutsche-recycling.com"],
        "notes": "德国及欧盟包装、WEEE和电池EPR实务信息。",
    },
    {
        "domain": "gwp.co.uk", "name": "GWP Packaging", "level": "D",
        "source_type": "Packaging specialist", "is_official": False,
        "markets": ["UK", "EU"], "topics": ["Packaging / PPWR / EPR"],
        "monitoring_urls": ["https://www.gwp.co.uk"],
        "notes": "英国和欧盟包装设计、包装材料及EPR文章。",
    },
    {
        "domain": "productcomplianceinstitute.com", "name": "Product Compliance Institute", "level": "C",
        "source_type": "Regulatory training / consulting", "is_official": False,
        "markets": ["Global"], "topics": ["All"],
        "monitoring_urls": ["https://www.productcomplianceinstitute.com"],
        "notes": "综合产品安全、EMC、无线、环保、生态设计和标签信息。",
    },
    {
        "domain": "circularactionalliance.org", "name": "Circular Action Alliance", "level": "B",
        "source_type": "EPR operational organization", "is_official": False,
        "markets": ["US States"], "topics": ["Packaging / PPWR / EPR"],
        "monitoring_urls": ["https://circularactionalliance.org/producer-resource-center#Events"],
        "notes": "美国州级包装EPR的生产者注册、申报、时间节点和PRO运营信息。法律结论仍需州政府原文。",
    },
    {
        "domain": "dianqizazhi.com", "name": "《电器》杂志", "level": "D",
        "source_type": "Industry publication", "is_official": False,
        "markets": ["Global"], "topics": ["Industry News / Market Intelligence", "All"],
        "monitoring_urls": ["https://www.dianqizazhi.com/"],
        "notes": "国内家电行业政策、市场和行业新闻线索。",
    },
]

TOPICS = [
    "Product Safety",
    "Electrical Safety",
    "Machinery",
    "EMC",
    "Radio / Wireless",
    "Packaging / PPWR / EPR",
    "Batteries",
    "WEEE / Waste",
    "Chemicals / REACH / RoHS / PFAS",
    "Ecodesign / Energy Efficiency",
    "Cybersecurity / IoT",
    "Labelling / Instructions",
    "Transport / Dangerous Goods",
    "Trade / Market Access",
    "Noise / Vibration / Outdoor Equipment",
    "Industry News / Market Intelligence",
]

JURISDICTIONS = ["EU", "UK", "US Federal", "US States", "Canada Federal", "Canada Provinces"]

# Backwards-compatible view used by older code and jurisdiction selectors.
OFFICIAL_SOURCES: dict[str, list[dict[str, str]]] = {
    market: [
        {"domain": str(source["domain"]), "name": str(source["name"]), "level": str(source["level"])}
        for source in SOURCES
        if source["is_official"] and market in source["markets"]
    ]
    for market in JURISDICTIONS
}


def _topic_matches(source: dict[str, object], topic: str | None) -> bool:
    if not topic or topic == "All":
        return True
    topics = source.get("topics") or []
    return "All" in topics or topic in topics


def _market_matches(source: dict[str, object], jurisdictions: Iterable[str] | None) -> bool:
    selected = set(jurisdictions or JURISDICTIONS)
    markets = set(source.get("markets") or [])
    return "Global" in markets or bool(selected & markets)


def filtered_sources(
    jurisdictions: list[str] | None = None,
    scope: str = "curated",
    topic: str | None = None,
    selected_domains: list[str] | None = None,
) -> list[dict[str, object]]:
    selected_domain_set = set(selected_domains or [])
    results: list[dict[str, object]] = []
    for source in SOURCES:
        if selected_domain_set and source["domain"] not in selected_domain_set:
            continue
        if not _market_matches(source, jurisdictions) or not _topic_matches(source, topic):
            continue
        if scope == "official" and not source["is_official"]:
            continue
        if scope == "professional" and source["is_official"]:
            continue
        results.append(source)
    return results


def all_domains(
    jurisdictions: list[str] | None = None,
    scope: str = "curated",
    topic: str | None = None,
    selected_domains: list[str] | None = None,
) -> list[str]:
    return sorted(
        {
            str(item["domain"])
            for item in filtered_sources(jurisdictions, scope, topic, selected_domains)
        }
    )


def source_metadata(url: str) -> dict[str, str | bool]:
    host = (urlparse(url).hostname or "").lower()
    for source in SOURCES:
        domain = str(source["domain"])
        if host == domain or host.endswith("." + domain):
            markets = list(source.get("markets") or [])
            jurisdiction = markets[0] if len(markets) == 1 else ("Global" if "Global" in markets else ", ".join(markets))
            return {
                "is_official": bool(source["is_official"]),
                "is_curated": True,
                "verification_required": not bool(source["is_official"]),
                "jurisdiction_group": jurisdiction,
                "source_name": str(source["name"]),
                "source_level": str(source["level"]),
                "source_type": str(source["source_type"]),
                "domain": domain,
            }
    return {
        "is_official": False,
        "is_curated": False,
        "verification_required": True,
        "jurisdiction_group": "Unknown",
        "source_name": host or "Unknown",
        "source_level": "D",
        "source_type": "Unregistered web source",
        "domain": host,
    }


def source_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for source in SOURCES:
        rows.append(
            {
                "来源名称": source["name"],
                "域名": source["domain"],
                "等级": source["level"],
                "来源类型": source["source_type"],
                "官方原文源": "是" if source["is_official"] else "否",
                "适用市场": ", ".join(source.get("markets") or []),
                "关注主题": ", ".join(source.get("topics") or []),
                "监控入口": "\n".join(source.get("monitoring_urls") or []),
                "说明": source.get("notes") or "",
            }
        )
    return rows
