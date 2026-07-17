from __future__ import annotations

import hmac
import json

import streamlit as st

import db
from config import SETTINGS
from exporters import intelligence_to_xlsx, regulation_to_docx, regulations_to_xlsx
from llm import analyze_document
from search import build_query_variants, detect_query_intent, enrich_result, resolve_jurisdictions, search_all
from source_registry import JURISDICTIONS, SOURCES, TOPICS, filtered_sources, source_rows

st.set_page_config(page_title="Cleva Regulatory Library", page_icon="📚", layout="wide")


def require_access() -> None:
    """Require an optional shared password before exposing API-backed features."""
    expected = SETTINGS.app_password.strip()
    if not expected or st.session_state.get("cleva_authenticated"):
        return

    st.title("Cleva Global Regulatory Library")
    st.caption("公司法规情报与人工审核知识库")
    entered = st.text_input("访问密码", type="password")
    if st.button("进入系统", type="primary"):
        if entered and hmac.compare_digest(entered, expected):
            st.session_state["cleva_authenticated"] = True
            st.rerun()
        else:
            st.error("访问密码不正确。")
    st.stop()


require_access()
db.init_db()

st.title("Cleva Global Regulatory Library")
st.caption("精选信息源 / 官方法规实时搜索 → AI初步整理 → 人工审核 → 法规库或情报库 → Excel / Word导出")

with st.sidebar:
    st.subheader("运行配置")
    st.write(f"Search provider: `{SETTINGS.search_provider}`")
    st.write(f"LLM provider: `{SETTINGS.llm_provider}`")
    model_name = SETTINGS.deepseek_model if SETTINGS.llm_provider == "deepseek" else SETTINGS.openai_model
    st.write(f"LLM model: `{model_name}`")
    st.warning("AI结果仅供初筛。第三方解读不能直接替代官方法规原文。")
    st.caption("v0.3：新增法规编号识别、州/联邦智能路由、官方源优先排序和低相关结果过滤。")
    if SETTINGS.deployment_mode == "cloud_demo":
        st.warning("云端演示版当前使用本地 SQLite。应用重启或重新部署后，新增数据可能丢失；正式公司版应改用持久数据库。")

search_tab, review_tab, library_tab, intelligence_tab, sources_tab = st.tabs(
    ["🔎 实时搜索", "✅ 待审核", "📚 正式法规库", "📰 法规情报库", "🌐 信息源中心"]
)

SEARCH_MODES = {
    "快速检索（推荐日常使用）": "quick",
    "仅官方来源（用于最终核验）": "official",
    "深度检索（多关键词 + 全网补充）": "deep",
}

with search_tab:
    st.subheader("法规与专业信息源实时搜索")
    c1, c2 = st.columns([2, 1])
    with c1:
        query = st.text_input(
            "搜索词",
            placeholder="例如：EU PPWR packaging recyclability；欧洲吸尘器环保法规",
        )
    with c2:
        topic = st.selectbox("法规主题", ["All"] + TOPICS)

    jurisdictions = st.multiselect(
        "国家/地区",
        JURISDICTIONS,
        default=["EU"],
    )

    c3, c4 = st.columns([1, 2])
    with c3:
        mode_label = st.selectbox("检索模式", list(SEARCH_MODES))
        search_mode = SEARCH_MODES[mode_label]
    with c4:
        if search_mode == "quick":
            st.info("优先搜索已维护的官方和专业信息源，速度快、结果更聚焦、较省搜索额度。")
        elif search_mode == "official":
            st.info("只搜索政府、监管机构及官方法规数据库，适合最终真实性核验。")
        else:
            st.warning("会执行多组关键词并增加一次全网搜索，覆盖更广，但会消耗更多Brave请求。")

    available_sources = filtered_sources(
        jurisdictions or JURISDICTIONS,
        scope="official" if search_mode == "official" else "curated",
        topic=topic,
    )
    source_options = {f"{source['name']}  [{source['level']}]": str(source["domain"]) for source in available_sources}
    selected_source_labels = st.multiselect(
        "指定信息源（可选；不选择则搜索当前地区和主题下的全部已维护来源）",
        list(source_options),
    )
    selected_domains = [source_options[label] for label in selected_source_labels]

    c5, c6, c7 = st.columns(3)
    with c5:
        provider_options = list(dict.fromkeys([SETTINGS.search_provider, "official-only"]))
        provider = st.selectbox("搜索方式", provider_options, index=0)
    with c6:
        fetch_full_text = st.checkbox("抓取网页/PDF正文", value=True)
    with c7:
        use_ai = st.checkbox("使用AI整理字段", value=SETTINGS.llm_provider != "none")

    if query.strip():
        intent = detect_query_intent(query)
        variants = build_query_variants(query, topic, search_mode)
        effective_jurisdictions = resolve_jurisdictions(query, jurisdictions)
        st.caption(f"本次将执行 {len(variants)} 组关键词；可检索的信息源约 {len(available_sources)} 个。")
        if intent.notes:
            st.info("智能识别：" + "；".join(intent.notes))
        if effective_jurisdictions != jurisdictions:
            st.warning(
                "根据搜索词，本次实际检索范围已自动调整为："
                + ", ".join(effective_jurisdictions)
                + "。界面中的原选择不会被改写。"
            )

    if st.button("开始实时搜索", type="primary", disabled=not query.strip() or not jurisdictions):
        run_id = db.create_search_run(query, jurisdictions, topic, provider, search_mode)
        try:
            raw_results = search_all(
                query,
                jurisdictions,
                provider,
                search_mode=search_mode,
                topic=topic,
                selected_domains=selected_domains or None,
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"搜索失败：{exc}")
            raw_results = []

        progress = st.progress(0)
        saved = []
        for idx, result in enumerate(raw_results):
            item = enrich_result(result, fetch_full_text=fetch_full_text)
            if use_ai:
                try:
                    item["ai_data"] = analyze_document(item, query, topic)
                except Exception as exc:  # noqa: BLE001
                    item["ai_data"] = {
                        "record_type": "Unclear",
                        "summary_cn": item.get("snippet"),
                        "uncertainty_notes": [f"AI分析失败：{exc}"],
                    }
            candidate_id = db.upsert_candidate(run_id, item)
            saved.append((candidate_id, item))
            progress.progress((idx + 1) / max(len(raw_results), 1))
        st.session_state["latest_results"] = saved
        if saved:
            st.success(f"已找到并保存 {len(saved)} 条高相关候选结果，全部进入待审核区。")
        else:
            detected = detect_query_intent(query)
            if detected.is_exact_legal_citation:
                st.warning("没有找到达到精确编号匹配阈值的结果。系统已主动隐藏不含目标法规/法案编号的网页，请尝试仅选择对应州、补充年份或使用深度检索。")
            else:
                st.warning("没有找到达到相关度阈值的结果，请调整地区、主题或关键词。")

    for candidate_id, item in st.session_state.get("latest_results", []):
        ai = item.get("ai_data") or {}
        source_badge = "官方原文源" if item.get("is_official") else ("精选专业源" if item.get("is_curated") else "全网来源")
        label = ai.get("chinese_title") or item.get("title")
        with st.expander(f"{label}  |  {item.get('source_name')}  |  {source_badge}"):
            st.markdown(f"[打开来源页面]({item.get('url')})")
            st.write(item.get("snippet") or "")
            cols = st.columns(6)
            cols[0].metric("检索匹配分", item.get("relevance_score", 0))
            cols[1].metric("来源等级", item.get("source_level") or "-")
            cols[2].metric("来源类型", item.get("source_type") or "-")
            cols[3].metric("地区", item.get("jurisdiction_group") or "-")
            cols[4].metric("建议记录类型", ai.get("record_type") or "待审核")
            cols[5].metric("AI相关度", ai.get("relevance_level") or "待审核")
            if item.get("relevance_reasons"):
                st.caption("排序依据：" + "；".join(item["relevance_reasons"][:5]))
            if item.get("verification_required"):
                st.warning("该页面不是法律原文，入正式法规库前必须找到并核验其引用的政府或法规数据库链接。")
            if ai.get("summary_cn"):
                st.markdown("**AI中文摘要**")
                st.write(ai["summary_cn"])
            st.caption(f"候选记录ID：{candidate_id}。请到“待审核”页面决定进入正式法规库或法规情报库。")

with review_tab:
    st.subheader("候选资料人工审核")
    reviewer = st.text_input("审核人", value="")
    pending = db.list_candidates("pending")
    st.write(f"待审核：{len(pending)} 条")

    for row in pending:
        ai = json.loads(row["ai_json"] or "{}")
        label = ai.get("chinese_title") or row["title"]
        suggested_type = ai.get("record_type") or "Unclear"
        with st.expander(f"#{row['id']}  {label}  |  AI建议：{suggested_type}"):
            st.markdown(f"[打开来源页面]({row['url']})")
            st.write(
                f"来源：{row['source_name']} | Level {row['source_level']} | "
                f"类型：{row['source_type'] or '-'} | 官方原文源：{'是' if row['is_official'] else '否'}"
            )
            st.write(ai.get("summary_cn") or row["snippet"] or "无摘要")
            if ai.get("uncertainty_notes"):
                st.warning("；".join(map(str, ai["uncertainty_notes"])))

            related_official_url = st.text_input(
                "对应的官方法规链接（第三方来源作为正式法规入库时必填；作为情报资料时可选）",
                value=ai.get("related_official_url") or "",
                key=f"official_url_{row['id']}",
                placeholder="例如：https://eur-lex.europa.eu/...",
            )
            note = st.text_area("审核备注", key=f"note_{row['id']}")

            a, b, c, d = st.columns(4)
            regulation_disabled = not reviewer.strip() or (not row["is_official"] and not related_official_url.strip())
            if a.button(
                "作为正式法规入库",
                key=f"approve_reg_{row['id']}",
                type="primary",
                disabled=regulation_disabled,
            ):
                try:
                    db.promote_candidate_to_regulation(
                        row["id"],
                        reviewer.strip(),
                        official_url=related_official_url.strip() or None,
                        note=note,
                    )
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(str(exc))

            if b.button(
                "作为法规情报入库",
                key=f"approve_intel_{row['id']}",
                disabled=not reviewer.strip(),
            ):
                db.promote_candidate_to_intelligence(
                    row["id"],
                    reviewer.strip(),
                    related_official_url=related_official_url,
                    note=note,
                )
                st.rerun()

            if c.button("不相关", key=f"reject_{row['id']}", disabled=not reviewer.strip()):
                db.review_candidate(row["id"], "reject", reviewer.strip(), note)
                st.rerun()
            if d.button("重复", key=f"dup_{row['id']}", disabled=not reviewer.strip()):
                db.review_candidate(row["id"], "duplicate", reviewer.strip(), note)
                st.rerun()

            if not row["is_official"]:
                st.caption("第三方页面可直接进入法规情报库；进入正式法规库前，必须在上方补充官方原文链接。")

with library_tab:
    st.subheader("正式法规知识库")
    keyword = st.text_input("库内搜索", placeholder="法规名称、编号、摘要关键词", key="reg_search")
    rows = db.list_regulations(keyword)
    st.write(f"正式法规：{len(rows)} 条")
    if rows:
        xlsx = regulations_to_xlsx([dict(row) for row in rows])
        st.download_button(
            "导出当前结果为Excel",
            data=xlsx,
            file_name="Cleva_Regulatory_Library.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    for row in rows:
        title = row["chinese_title"] or row["original_title"]
        with st.expander(f"#{row['id']}  {title}"):
            st.markdown(f"[打开官方原文]({row['official_url']})")
            if row["discovery_url"]:
                st.markdown(f"[查看最初发现该法规的解读页面]({row['discovery_url']})")
            st.write(
                f"编号：{row['regulation_number'] or '-'} | 地区：{row['jurisdiction'] or '-'} | "
                f"状态：{row['legal_status'] or '-'}"
            )
            st.write(row["summary_cn"] or "无摘要")
            st.markdown("**Cleva初步影响**")
            st.write(row["cleva_impact"] or "待评估")
            docx = regulation_to_docx(dict(row))
            st.download_button(
                "导出Word法规卡片",
                data=docx,
                file_name=f"regulation_{row['id']}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"docx_{row['id']}",
            )

with intelligence_tab:
    st.subheader("法规情报与专业解读资料库")
    st.caption("保存Intertek、TBT、REACH24H、CAA等来源的解读、预警、注册通知和行业动态；不等同于正式法律原文。")
    keyword = st.text_input("情报库搜索", placeholder="主题、来源、摘要关键词", key="intel_search")
    rows = db.list_intelligence(keyword)
    st.write(f"情报资料：{len(rows)} 条")
    if rows:
        xlsx = intelligence_to_xlsx([dict(row) for row in rows])
        st.download_button(
            "导出当前情报为Excel",
            data=xlsx,
            file_name="Cleva_Regulatory_Intelligence.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    for row in rows:
        title = row["chinese_title"] or row["original_title"]
        with st.expander(f"#{row['id']}  {title}  |  {row['source_name']}"):
            st.markdown(f"[打开原始解读/通知页面]({row['source_url']})")
            if row["related_official_url"]:
                st.markdown(f"[打开关联官方法规]({row['related_official_url']})")
            st.write(
                f"来源类型：{row['source_type'] or '-'} | 来源等级：{row['source_level'] or '-'} | "
                f"地区：{row['jurisdiction'] or '-'}"
            )
            st.write(row["summary_cn"] or "无摘要")
            st.markdown("**Cleva初步影响**")
            st.write(row["cleva_impact"] or "待评估")

with sources_tab:
    st.subheader("信息源中心")
    st.caption("A级/B级官方来源用于法律核验；B/C/D级专业和行业来源用于发现线索、理解法规和跟踪申报实务。")

    c1, c2, c3 = st.columns(3)
    with c1:
        market_filter = st.selectbox("市场筛选", ["All"] + JURISDICTIONS + ["Global"])
    with c2:
        type_values = sorted({str(source["source_type"]) for source in SOURCES})
        type_filter = st.selectbox("来源类型", ["All"] + type_values)
    with c3:
        level_filter = st.selectbox("来源等级", ["All", "A", "B", "C", "D"])

    rows = source_rows()
    filtered = []
    for row in rows:
        if market_filter != "All" and market_filter not in row["适用市场"]:
            continue
        if type_filter != "All" and row["来源类型"] != type_filter:
            continue
        if level_filter != "All" and row["等级"] != level_filter:
            continue
        filtered.append(row)
    st.dataframe(filtered, use_container_width=True, hide_index=True)

    st.markdown("### 已加入的重点专业信息源")
    st.write(
        "Intertek、技术性贸易措施资讯网、REACH24H、In Compliance Magazine、"
        "Deutsche Recycling、GWP、Product Compliance Institute、Circular Action Alliance和《电器》杂志。"
    )
    st.info("系统会将这些第三方页面默认识别为“法规情报”。只有补充并核验官方原文链接后，才能作为正式法规入库。")
