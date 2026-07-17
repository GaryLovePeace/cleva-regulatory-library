from __future__ import annotations

import re
from typing import Iterable

# U.S. state source registry used by v0.4.
# Legislature links are curated from state legislative websites/NCSL directories.
# Environmental-agency links are curated from the U.S. EPA state-agency directory.

ENVIRONMENT_TOPICS = [
    "Packaging / PPWR / EPR",
    "Batteries",
    "WEEE / Waste",
    "Chemicals / REACH / RoHS / PFAS",
    "Labelling / Instructions",
    "Industry News / Market Intelligence",
]

COMMON_BILL_PREFIXES = (
    "HB", "SB", "AB", "HF", "SF", "HJR", "SJR", "HCR", "SCR",
    "HR", "SR", "LD", "LB", "H", "S", "A", "B",
)

BILL_PREFIX_FULL_NAMES = {
    "HB": "House Bill",
    "SB": "Senate Bill",
    "AB": "Assembly Bill",
    "HF": "House File",
    "SF": "Senate File",
    "HJR": "House Joint Resolution",
    "SJR": "Senate Joint Resolution",
    "HCR": "House Concurrent Resolution",
    "SCR": "Senate Concurrent Resolution",
    "HR": "House Resolution",
    "SR": "Senate Resolution",
    "LD": "Legislative Document",
    "LB": "Legislative Bill",
    "H": "House Bill",
    "S": "Senate Bill",
    "A": "Assembly Bill",
    "B": "Bill",
}

# Each profile contains one or more official legislative domains and at least one
# official environmental agency domain. A few states have additional topic-specific
# agencies because they are particularly relevant to Cleva (packaging, chemicals,
# batteries, e-waste or environmental claims).
US_STATE_PROFILES: dict[str, dict[str, object]] = {
    "District of Columbia": {
        "abbr": "DC", "aliases": ["district of columbia", "washington dc", "washington, d.c.", "华盛顿特区", "哥伦比亚特区"],
        "bill_prefixes": ["B", "PR"],
        "legislature": [
            ("lims.dccouncil.gov", "DC Council LIMS", "https://lims.dccouncil.gov/"),
            ("code.dccouncil.gov", "District of Columbia Code", "https://code.dccouncil.gov/"),
        ],
        "agencies": [
            ("doee.dc.gov", "DC Department of Energy and Environment", "https://doee.dc.gov/", ENVIRONMENT_TOPICS),
        ],
    },
    "Alabama": {
        "abbr": "AL", "aliases": ["alabama", "阿拉巴马州"],
        "legislature": [("legislature.state.al.us", "Alabama Legislature", "https://legislature.state.al.us/")],
        "agencies": [("adem.alabama.gov", "Alabama Department of Environmental Management", "https://adem.alabama.gov/", ENVIRONMENT_TOPICS)],
    },
    "Alaska": {
        "abbr": "AK", "aliases": ["alaska", "阿拉斯加州"],
        "legislature": [("akleg.gov", "Alaska Legislature", "https://www.akleg.gov/")],
        "agencies": [("dec.alaska.gov", "Alaska Department of Environmental Conservation", "https://dec.alaska.gov/", ENVIRONMENT_TOPICS)],
    },
    "Arizona": {
        "abbr": "AZ", "aliases": ["arizona", "亚利桑那州"],
        "legislature": [("azleg.gov", "Arizona Legislature", "https://www.azleg.gov/"), ("apps.azleg.gov", "Arizona Legislature Applications", "https://apps.azleg.gov/")],
        "agencies": [("azdeq.gov", "Arizona Department of Environmental Quality", "https://azdeq.gov/", ENVIRONMENT_TOPICS)],
    },
    "Arkansas": {
        "abbr": "AR", "aliases": ["arkansas", "阿肯色州"],
        "legislature": [("arkleg.state.ar.us", "Arkansas Legislature", "https://www.arkleg.state.ar.us/")],
        "agencies": [("adeq.state.ar.us", "Arkansas Division of Environmental Quality", "https://www.adeq.state.ar.us/", ENVIRONMENT_TOPICS)],
    },
    "California": {
        "abbr": "CA", "aliases": ["california", "calif", "加州", "加利福尼亚州"],
        "bill_prefixes": ["AB", "SB", "ACA", "SCA", "AJR", "SJR", "ACR", "SCR", "HR", "SR"],
        "legislature": [("leginfo.legislature.ca.gov", "California Legislature", "https://leginfo.legislature.ca.gov/")],
        "agencies": [
            ("calepa.ca.gov", "California Environmental Protection Agency", "https://calepa.ca.gov/", ENVIRONMENT_TOPICS),
            ("calrecycle.ca.gov", "CalRecycle", "https://calrecycle.ca.gov/", ["Packaging / PPWR / EPR", "Batteries", "WEEE / Waste", "Labelling / Instructions"]),
            ("dtsc.ca.gov", "California DTSC", "https://dtsc.ca.gov/", ["Chemicals / REACH / RoHS / PFAS", "WEEE / Waste"]),
            ("oehha.ca.gov", "California OEHHA", "https://oehha.ca.gov/proposition-65", ["Chemicals / REACH / RoHS / PFAS", "Labelling / Instructions"]),
            ("ww2.arb.ca.gov", "California Air Resources Board", "https://ww2.arb.ca.gov/", ENVIRONMENT_TOPICS),
        ],
    },
    "Colorado": {
        "abbr": "CO", "aliases": ["colorado", "科罗拉多州"],
        "legislature": [("leg.colorado.gov", "Colorado General Assembly", "https://leg.colorado.gov/")],
        "agencies": [("cdphe.colorado.gov", "Colorado Department of Public Health and Environment", "https://cdphe.colorado.gov/", ENVIRONMENT_TOPICS)],
    },
    "Connecticut": {
        "abbr": "CT", "aliases": ["connecticut", "康涅狄格州"],
        "legislature": [("cga.ct.gov", "Connecticut General Assembly", "https://www.cga.ct.gov/")],
        "agencies": [("portal.ct.gov", "Connecticut DEEP", "https://portal.ct.gov/deep", ENVIRONMENT_TOPICS)],
    },
    "Delaware": {
        "abbr": "DE", "aliases": ["delaware", "特拉华州"],
        "legislature": [("legis.delaware.gov", "Delaware General Assembly", "https://legis.delaware.gov/")],
        "agencies": [("dnrec.delaware.gov", "Delaware DNREC", "https://dnrec.delaware.gov/", ENVIRONMENT_TOPICS)],
    },
    "Florida": {
        "abbr": "FL", "aliases": ["florida", "佛罗里达州"],
        "legislature": [("flsenate.gov", "Florida Senate", "https://www.flsenate.gov/"), ("myfloridahouse.gov", "Florida House", "https://www.myfloridahouse.gov/")],
        "agencies": [("floridadep.gov", "Florida Department of Environmental Protection", "https://floridadep.gov/", ENVIRONMENT_TOPICS)],
    },
    "Georgia": {
        "abbr": "GA", "aliases": ["georgia", "佐治亚州", "乔治亚州"],
        "legislature": [("legis.ga.gov", "Georgia General Assembly", "https://www.legis.ga.gov/")],
        "agencies": [("epd.georgia.gov", "Georgia Environmental Protection Division", "https://epd.georgia.gov/", ENVIRONMENT_TOPICS)],
    },
    "Hawaii": {
        "abbr": "HI", "aliases": ["hawaii", "夏威夷州"],
        "legislature": [("capitol.hawaii.gov", "Hawaii State Legislature", "https://www.capitol.hawaii.gov/")],
        "agencies": [("health.hawaii.gov", "Hawaii Department of Health", "https://health.hawaii.gov/", ENVIRONMENT_TOPICS)],
    },
    "Idaho": {
        "abbr": "ID", "aliases": ["idaho", "爱达荷州"],
        "legislature": [("legislature.idaho.gov", "Idaho Legislature", "https://legislature.idaho.gov/")],
        "agencies": [("deq.idaho.gov", "Idaho Department of Environmental Quality", "https://www.deq.idaho.gov/", ENVIRONMENT_TOPICS)],
    },
    "Illinois": {
        "abbr": "IL", "aliases": ["illinois", "伊利诺伊州"],
        "legislature": [("ilga.gov", "Illinois General Assembly", "https://www.ilga.gov/")],
        "agencies": [("epa.illinois.gov", "Illinois Environmental Protection Agency", "https://epa.illinois.gov/", ENVIRONMENT_TOPICS)],
    },
    "Indiana": {
        "abbr": "IN", "aliases": ["indiana", "印第安纳州"],
        "legislature": [("iga.in.gov", "Indiana General Assembly", "https://iga.in.gov/")],
        "agencies": [("in.gov", "Indiana Department of Environmental Management", "https://www.in.gov/idem/", ENVIRONMENT_TOPICS)],
    },
    "Iowa": {
        "abbr": "IA", "aliases": ["iowa", "艾奥瓦州", "爱荷华州"],
        "bill_prefixes": ["HF", "SF", "HSB", "SSB", "HJR", "SJR", "HCR", "SCR", "HR", "SR"],
        "legislature": [("legis.iowa.gov", "Iowa Legislature", "https://www.legis.iowa.gov/")],
        "agencies": [("iowadnr.gov", "Iowa Department of Natural Resources", "https://www.iowadnr.gov/", ENVIRONMENT_TOPICS)],
    },
    "Kansas": {
        "abbr": "KS", "aliases": ["kansas", "堪萨斯州"],
        "legislature": [("kslegislature.gov", "Kansas Legislature", "https://www.kslegislature.gov/")],
        "agencies": [("kdhe.ks.gov", "Kansas Department of Health and Environment", "https://www.kdhe.ks.gov/", ENVIRONMENT_TOPICS)],
    },
    "Kentucky": {
        "abbr": "KY", "aliases": ["kentucky", "肯塔基州"],
        "legislature": [("legislature.ky.gov", "Kentucky General Assembly", "https://legislature.ky.gov/")],
        "agencies": [("eec.ky.gov", "Kentucky Energy and Environment Cabinet", "https://eec.ky.gov/", ENVIRONMENT_TOPICS)],
    },
    "Louisiana": {
        "abbr": "LA", "aliases": ["louisiana", "路易斯安那州"],
        "legislature": [("legis.la.gov", "Louisiana Legislature", "https://www.legis.la.gov/")],
        "agencies": [("deq.louisiana.gov", "Louisiana Department of Environmental Quality", "https://deq.louisiana.gov/", ENVIRONMENT_TOPICS)],
    },
    "Maine": {
        "abbr": "ME", "aliases": ["maine", "缅因州"],
        "bill_prefixes": ["LD", "HP", "SP"],
        "legislature": [("legislature.maine.gov", "Maine Legislature", "https://legislature.maine.gov/")],
        "agencies": [("maine.gov", "Maine Department of Environmental Protection", "https://www.maine.gov/dep/", ENVIRONMENT_TOPICS)],
    },
    "Maryland": {
        "abbr": "MD", "aliases": ["maryland", "马里兰州"],
        "legislature": [("mgaleg.maryland.gov", "Maryland General Assembly", "https://mgaleg.maryland.gov/")],
        "agencies": [("mde.maryland.gov", "Maryland Department of the Environment", "https://mde.maryland.gov/", ENVIRONMENT_TOPICS)],
    },
    "Massachusetts": {
        "abbr": "MA", "aliases": ["massachusetts", "麻萨诸塞州", "马萨诸塞州"],
        "bill_prefixes": ["H", "S"],
        "legislature": [("malegislature.gov", "Massachusetts Legislature", "https://malegislature.gov/")],
        "agencies": [("mass.gov", "Massachusetts Department of Environmental Protection", "https://www.mass.gov/orgs/massachusetts-department-of-environmental-protection", ENVIRONMENT_TOPICS)],
    },
    "Michigan": {
        "abbr": "MI", "aliases": ["michigan", "密歇根州"],
        "legislature": [("legislature.mi.gov", "Michigan Legislature", "https://www.legislature.mi.gov/")],
        "agencies": [("michigan.gov", "Michigan EGLE", "https://www.michigan.gov/egle", ENVIRONMENT_TOPICS)],
    },
    "Minnesota": {
        "abbr": "MN", "aliases": ["minnesota", "明尼苏达州"],
        "bill_prefixes": ["HF", "SF", "H", "S"],
        "legislature": [("revisor.mn.gov", "Minnesota Revisor of Statutes", "https://www.revisor.mn.gov/"), ("house.mn.gov", "Minnesota House", "https://www.house.mn.gov/"), ("senate.mn", "Minnesota Senate", "https://www.senate.mn/")],
        "agencies": [("pca.state.mn.us", "Minnesota Pollution Control Agency", "https://www.pca.state.mn.us/", ENVIRONMENT_TOPICS)],
    },
    "Mississippi": {
        "abbr": "MS", "aliases": ["mississippi", "密西西比州"],
        "legislature": [("legislature.ms.gov", "Mississippi Legislature", "https://www.legislature.ms.gov/")],
        "agencies": [("mdeq.ms.gov", "Mississippi Department of Environmental Quality", "https://www.mdeq.ms.gov/", ENVIRONMENT_TOPICS)],
    },
    "Missouri": {
        "abbr": "MO", "aliases": ["missouri", "密苏里州"],
        "legislature": [("house.mo.gov", "Missouri House", "https://house.mo.gov/"), ("senate.mo.gov", "Missouri Senate", "https://www.senate.mo.gov/")],
        "agencies": [("dnr.mo.gov", "Missouri Department of Natural Resources", "https://dnr.mo.gov/", ENVIRONMENT_TOPICS)],
    },
    "Montana": {
        "abbr": "MT", "aliases": ["montana", "蒙大拿州"],
        "legislature": [("legmt.gov", "Montana Legislature", "https://www.legmt.gov/"), ("laws.leg.mt.gov", "Montana Laws and Bills", "https://laws.leg.mt.gov/")],
        "agencies": [("deq.mt.gov", "Montana Department of Environmental Quality", "https://deq.mt.gov/", ENVIRONMENT_TOPICS)],
    },
    "Nebraska": {
        "abbr": "NE", "aliases": ["nebraska", "内布拉斯加州"],
        "bill_prefixes": ["LB", "LR"],
        "legislature": [("nebraskalegislature.gov", "Nebraska Legislature", "https://nebraskalegislature.gov/")],
        "agencies": [("dee.nebraska.gov", "Nebraska Department of Environment and Energy", "https://dee.nebraska.gov/", ENVIRONMENT_TOPICS)],
    },
    "Nevada": {
        "abbr": "NV", "aliases": ["nevada", "内华达州"],
        "legislature": [("leg.state.nv.us", "Nevada Legislature", "https://www.leg.state.nv.us/")],
        "agencies": [("ndep.nv.gov", "Nevada Division of Environmental Protection", "https://ndep.nv.gov/", ENVIRONMENT_TOPICS)],
    },
    "New Hampshire": {
        "abbr": "NH", "aliases": ["new hampshire", "新罕布什尔州"],
        "legislature": [("gc.nh.gov", "New Hampshire General Court", "https://gc.nh.gov/")],
        "agencies": [("des.nh.gov", "New Hampshire Department of Environmental Services", "https://www.des.nh.gov/", ENVIRONMENT_TOPICS)],
    },
    "New Jersey": {
        "abbr": "NJ", "aliases": ["new jersey", "新泽西州"],
        "bill_prefixes": ["A", "S", "ACR", "SCR", "AJR", "SJR", "AR", "SR"],
        "legislature": [("njleg.state.nj.us", "New Jersey Legislature", "https://www.njleg.state.nj.us/")],
        "agencies": [("dep.nj.gov", "New Jersey Department of Environmental Protection", "https://dep.nj.gov/", ENVIRONMENT_TOPICS)],
    },
    "New Mexico": {
        "abbr": "NM", "aliases": ["new mexico", "新墨西哥州"],
        "legislature": [("nmlegis.gov", "New Mexico Legislature", "https://www.nmlegis.gov/")],
        "agencies": [("env.nm.gov", "New Mexico Environment Department", "https://www.env.nm.gov/", ENVIRONMENT_TOPICS)],
    },
    "New York": {
        "abbr": "NY", "aliases": ["new york", "纽约州"],
        "bill_prefixes": ["A", "S", "J", "K"],
        "legislature": [("nysenate.gov", "New York State Senate", "https://www.nysenate.gov/"), ("nyassembly.gov", "New York State Assembly", "https://nyassembly.gov/")],
        "agencies": [("dec.ny.gov", "New York Department of Environmental Conservation", "https://dec.ny.gov/", ENVIRONMENT_TOPICS)],
    },
    "North Carolina": {
        "abbr": "NC", "aliases": ["north carolina", "北卡罗来纳州"],
        "legislature": [("ncleg.gov", "North Carolina General Assembly", "https://www.ncleg.gov/")],
        "agencies": [("deq.nc.gov", "North Carolina Department of Environmental Quality", "https://www.deq.nc.gov/", ENVIRONMENT_TOPICS)],
    },
    "North Dakota": {
        "abbr": "ND", "aliases": ["north dakota", "北达科他州"],
        "legislature": [("ndlegis.gov", "North Dakota Legislative Branch", "https://www.ndlegis.gov/")],
        "agencies": [("deq.nd.gov", "North Dakota Department of Environmental Quality", "https://deq.nd.gov/", ENVIRONMENT_TOPICS)],
    },
    "Ohio": {
        "abbr": "OH", "aliases": ["ohio", "俄亥俄州"],
        "legislature": [("legislature.ohio.gov", "Ohio Legislature", "https://www.legislature.ohio.gov/")],
        "agencies": [("epa.ohio.gov", "Ohio Environmental Protection Agency", "https://epa.ohio.gov/", ENVIRONMENT_TOPICS)],
    },
    "Oklahoma": {
        "abbr": "OK", "aliases": ["oklahoma", "俄克拉何马州"],
        "legislature": [("oklegislature.gov", "Oklahoma Legislature", "https://www.oklegislature.gov/")],
        "agencies": [("deq.ok.gov", "Oklahoma Department of Environmental Quality", "https://www.deq.ok.gov/", ENVIRONMENT_TOPICS)],
    },
    "Oregon": {
        "abbr": "OR", "aliases": ["oregon", "俄勒冈州"],
        "legislature": [("oregonlegislature.gov", "Oregon Legislature", "https://www.oregonlegislature.gov/")],
        "agencies": [("oregon.gov", "Oregon Department of Environmental Quality", "https://www.oregon.gov/deq/", ENVIRONMENT_TOPICS)],
    },
    "Pennsylvania": {
        "abbr": "PA", "aliases": ["pennsylvania", "宾夕法尼亚州"],
        "legislature": [("legis.state.pa.us", "Pennsylvania General Assembly", "https://www.legis.state.pa.us/")],
        "agencies": [("dep.pa.gov", "Pennsylvania Department of Environmental Protection", "https://www.dep.pa.gov/", ENVIRONMENT_TOPICS)],
    },
    "Rhode Island": {
        "abbr": "RI", "aliases": ["rhode island", "罗得岛州"],
        "legislature": [("rilegislature.gov", "Rhode Island General Assembly", "https://www.rilegislature.gov/")],
        "agencies": [("dem.ri.gov", "Rhode Island Department of Environmental Management", "https://dem.ri.gov/", ENVIRONMENT_TOPICS)],
    },
    "South Carolina": {
        "abbr": "SC", "aliases": ["south carolina", "南卡罗来纳州"],
        "legislature": [("scstatehouse.gov", "South Carolina Legislature", "https://www.scstatehouse.gov/")],
        "agencies": [("des.sc.gov", "South Carolina Department of Environmental Services", "https://des.sc.gov/", ENVIRONMENT_TOPICS)],
    },
    "South Dakota": {
        "abbr": "SD", "aliases": ["south dakota", "南达科他州"],
        "legislature": [("sdlegislature.gov", "South Dakota Legislature", "https://sdlegislature.gov/")],
        "agencies": [("danr.sd.gov", "South Dakota Department of Agriculture and Natural Resources", "https://danr.sd.gov/", ENVIRONMENT_TOPICS)],
    },
    "Tennessee": {
        "abbr": "TN", "aliases": ["tennessee", "田纳西州"],
        "legislature": [("capitol.tn.gov", "Tennessee General Assembly", "https://www.capitol.tn.gov/")],
        "agencies": [("tn.gov", "Tennessee Department of Environment and Conservation", "https://www.tn.gov/environment.html", ENVIRONMENT_TOPICS)],
    },
    "Texas": {
        "abbr": "TX", "aliases": ["texas", "德克萨斯州", "得克萨斯州"],
        "legislature": [("capitol.texas.gov", "Texas Legislature Online", "https://capitol.texas.gov/")],
        "agencies": [("tceq.texas.gov", "Texas Commission on Environmental Quality", "https://www.tceq.texas.gov/", ENVIRONMENT_TOPICS)],
    },
    "Utah": {
        "abbr": "UT", "aliases": ["utah", "犹他州"],
        "legislature": [("le.utah.gov", "Utah State Legislature", "https://le.utah.gov/")],
        "agencies": [("deq.utah.gov", "Utah Department of Environmental Quality", "https://deq.utah.gov/", ENVIRONMENT_TOPICS)],
    },
    "Vermont": {
        "abbr": "VT", "aliases": ["vermont", "佛蒙特州"],
        "legislature": [("legislature.vermont.gov", "Vermont General Assembly", "https://legislature.vermont.gov/")],
        "agencies": [("dec.vermont.gov", "Vermont Department of Environmental Conservation", "https://dec.vermont.gov/", ENVIRONMENT_TOPICS)],
    },
    "Virginia": {
        "abbr": "VA", "aliases": ["virginia", "弗吉尼亚州"],
        "legislature": [("lis.virginia.gov", "Virginia Legislative Information System", "https://lis.virginia.gov/")],
        "agencies": [("deq.virginia.gov", "Virginia Department of Environmental Quality", "https://www.deq.virginia.gov/", ENVIRONMENT_TOPICS)],
    },
    "Washington": {
        "abbr": "WA", "aliases": ["washington state", "washington", "华盛顿州"],
        "legislature": [("app.leg.wa.gov", "Washington Legislature Bill Information", "https://app.leg.wa.gov/"), ("leg.wa.gov", "Washington State Legislature", "https://leg.wa.gov/")],
        "agencies": [("ecology.wa.gov", "Washington Department of Ecology", "https://ecology.wa.gov/", ENVIRONMENT_TOPICS)],
    },
    "West Virginia": {
        "abbr": "WV", "aliases": ["west virginia", "西弗吉尼亚州"],
        "legislature": [("wvlegislature.gov", "West Virginia Legislature", "https://www.wvlegislature.gov/")],
        "agencies": [("dep.wv.gov", "West Virginia Department of Environmental Protection", "https://dep.wv.gov/", ENVIRONMENT_TOPICS)],
    },
    "Wisconsin": {
        "abbr": "WI", "aliases": ["wisconsin", "威斯康星州"],
        "legislature": [("legis.wisconsin.gov", "Wisconsin Legislature", "https://legis.wisconsin.gov/"), ("docs.legis.wisconsin.gov", "Wisconsin Legislative Documents", "https://docs.legis.wisconsin.gov/")],
        "agencies": [("dnr.wisconsin.gov", "Wisconsin Department of Natural Resources", "https://dnr.wisconsin.gov/", ENVIRONMENT_TOPICS)],
    },
    "Wyoming": {
        "abbr": "WY", "aliases": ["wyoming", "怀俄明州"],
        "legislature": [("wyoleg.gov", "Wyoming Legislature", "https://www.wyoleg.gov/")],
        "agencies": [("deq.wyoming.gov", "Wyoming Department of Environmental Quality", "https://deq.wyoming.gov/", ENVIRONMENT_TOPICS)],
    },
}

US_STATE_NAMES = list(US_STATE_PROFILES)


def _domain_matches(host: str, domain: str) -> bool:
    host = host.lower().strip(".")
    domain = domain.lower().strip(".")
    return host == domain or host.endswith("." + domain) or domain.endswith("." + host)


def normalize_bill_prefix(prefix: str) -> str:
    return re.sub(r"[^A-Z]", "", prefix.upper())


def bill_prefixes_for_state(state: str | None) -> tuple[str, ...]:
    if not state or state not in US_STATE_PROFILES:
        return COMMON_BILL_PREFIXES
    prefixes = US_STATE_PROFILES[state].get("bill_prefixes") or COMMON_BILL_PREFIXES
    return tuple(normalize_bill_prefix(str(item)) for item in prefixes)


def bill_prefix_allowed(state: str | None, prefix: str) -> bool:
    normalized = normalize_bill_prefix(prefix)
    return normalized in set(bill_prefixes_for_state(state))


def full_bill_name(prefix: str) -> str:
    return BILL_PREFIX_FULL_NAMES.get(normalize_bill_prefix(prefix), normalize_bill_prefix(prefix))


def state_abbreviation(state: str | None) -> str | None:
    if not state or state not in US_STATE_PROFILES:
        return None
    return str(US_STATE_PROFILES[state]["abbr"])


def detect_state(text: str, state_hint: str | None = None) -> str | None:
    if state_hint in US_STATE_PROFILES:
        return state_hint

    raw = " ".join(text.split())
    lower = raw.lower()

    # Check DC first to avoid interpreting "Washington, D.C." as Washington state.
    ordered_states = ["District of Columbia"] + [name for name in US_STATE_NAMES if name != "District of Columbia"]
    for state in ordered_states:
        profile = US_STATE_PROFILES[state]
        aliases = [state.lower(), *[str(item).lower() for item in profile.get("aliases") or []]]
        for alias in aliases:
            if not alias:
                continue
            if re.search(r"[\u4e00-\u9fff]", alias):
                if alias in raw:
                    return state
            elif re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", lower):
                return state

    # Two-letter abbreviations are only accepted when written in uppercase. This
    # prevents words such as "or" and "in" from being interpreted as states.
    for state, profile in US_STATE_PROFILES.items():
        abbr = str(profile["abbr"])
        if re.search(rf"\b{re.escape(abbr)}\b", raw):
            return state
    return None


def state_domains(state: str | None, *, include_agencies: bool = True) -> list[str]:
    if not state or state not in US_STATE_PROFILES:
        return []
    profile = US_STATE_PROFILES[state]
    domains = [str(row[0]) for row in profile.get("legislature") or []]
    if include_agencies:
        domains.extend(str(row[0]) for row in profile.get("agencies") or [])
    return list(dict.fromkeys(domains))


def state_legislature_domains(state: str | None) -> list[str]:
    if not state or state not in US_STATE_PROFILES:
        return []
    return [str(row[0]) for row in US_STATE_PROFILES[state].get("legislature") or []]


def state_environment_domains(state: str | None) -> list[str]:
    if not state or state not in US_STATE_PROFILES:
        return []
    return [str(row[0]) for row in US_STATE_PROFILES[state].get("agencies") or []]


def domain_belongs_to_state(domain: str, state: str | None) -> bool:
    return any(_domain_matches(domain, candidate) for candidate in state_domains(state))


def build_us_state_source_records() -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for state, profile in US_STATE_PROFILES.items():
        for domain, name, url in profile.get("legislature") or []:
            records.append(
                {
                    "domain": domain,
                    "name": name,
                    "level": "A",
                    "source_type": "Official state legislation",
                    "is_official": True,
                    "markets": ["US States"],
                    "state": state,
                    "topics": ["All"],
                    "monitoring_urls": [url],
                    "notes": f"{state}州/特区官方法案、法律或立法跟踪来源。",
                }
            )
        for domain, name, url, topics in profile.get("agencies") or []:
            records.append(
                {
                    "domain": domain,
                    "name": name,
                    "level": "B",
                    "source_type": "Official state environmental agency",
                    "is_official": True,
                    "markets": ["US States"],
                    "state": state,
                    "topics": list(topics),
                    "monitoring_urls": [url],
                    "notes": f"{state}州/特区环境、废弃物、包装、电池或化学品监管信息。",
                }
            )
    return records


def state_coverage_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for state, profile in US_STATE_PROFILES.items():
        rows.append(
            {
                "state": state,
                "abbreviation": str(profile["abbr"]),
                "bill_prefixes": ", ".join(bill_prefixes_for_state(state)),
                "legislature_domains": ", ".join(str(row[0]) for row in profile.get("legislature") or []),
                "environment_domains": ", ".join(str(row[0]) for row in profile.get("agencies") or []),
            }
        )
    return rows
