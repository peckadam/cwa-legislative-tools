from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable, List, Optional, Set

import pandas as pd
import pydeck as pdk
import streamlit as st

from src.data_loader import load_datasets
from src.datc_loader import (
    load_datc_data,
    style_matrix,
    OWN_SYMBOL,
    NEIGHBOR_SYMBOL,
    WDA_REGIONS,
)


st.set_page_config(
    page_title="CWA Legislative Tools",
    page_icon="🏛️",
    layout="wide",
)

DATA_DIR = Path(__file__).parent / "data" / "processed"
DATC_EXCEL = Path(__file__).parent / "data" / "CWA_DATC_2026_Meeting_Matrix.xlsx"


@st.cache_data
def get_data():
    return load_datasets(DATA_DIR)


@st.cache_data
def get_datc_data():
    return load_datc_data(DATC_EXCEL)


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

def _base_bounds(data) -> List[float]:
    layers = [data["wda"], data["assembly"], data["senate"]]
    minx = min(g.total_bounds[0] for g in layers)
    miny = min(g.total_bounds[1] for g in layers)
    maxx = max(g.total_bounds[2] for g in layers)
    maxy = max(g.total_bounds[3] for g in layers)
    return [minx, miny, maxx, maxy]


def _build_geojson_layer(gdf, line_color, fill_color, line_width=1, opacity=0.08):
    return pdk.Layer(
        "GeoJsonLayer",
        data=gdf.__geo_interface__,
        stroked=True,
        filled=True,
        get_line_color=line_color,
        get_fill_color=fill_color,
        line_width_min_pixels=line_width,
        opacity=opacity,
        pickable=True,
        auto_highlight=True,
    )


def _filter_ids(gdf, col: str, ids: Iterable[str]):
    ids_set = set(ids)
    if not ids_set:
        return gdf.iloc[0:0]
    return gdf[gdf[col].isin(ids_set)]


def _fmt_int(v: Optional[float]) -> str:
    if pd.isna(v):
        return "—"
    return f"{int(round(float(v))):,}"


def _fmt_pct(v: object) -> str:
    if pd.isna(v):
        return "—"
    return f"{float(v):.1f}%"


def _safe_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _zoom_for_bounds(minx: float, miny: float, maxx: float, maxy: float) -> float:
    span_x = max(maxx - minx, 0.01)
    span_y = max(maxy - miny, 0.01)
    span = max(span_x, span_y)
    zoom = 8.5 - math.log2(span)
    return max(5.0, min(11.5, zoom))


def _view_state_from_bounds(bounds: List[float]) -> pdk.ViewState:
    minx, miny, maxx, maxy = bounds
    center_lat = (miny + maxy) / 2
    center_lon = (minx + maxx) / 2
    pad_x = max((maxx - minx) * 0.15, 0.05)
    pad_y = max((maxy - miny) * 0.15, 0.05)
    zoom = _zoom_for_bounds(minx - pad_x, miny - pad_y, maxx + pad_x, maxy + pad_y)
    return pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=zoom)


def _build_legislator_label(row: pd.Series) -> str:
    chamber = "Assembly" if row["chamber"] == "assembly" else "Senate"
    return f"{chamber} {int(row['district_number']):02d} – {row['full_name']}"


def _wdas_for_legislator(
    leg_row: pd.Series,
    assembly: pd.DataFrame,
    senate: pd.DataFrame,
    eligible_ad: pd.DataFrame,
    eligible_sd: pd.DataFrame,
    wda: pd.DataFrame,
) -> pd.DataFrame:
    if leg_row["chamber"] == "assembly":
        ad_id_series = assembly.loc[assembly["district_number"].astype(int) == int(leg_row["district_number"]), "ad_id"]
        if ad_id_series.empty:
            return pd.DataFrame()
        ad_id = ad_id_series.iloc[0]
        rows = eligible_ad[eligible_ad["ad_id"] == ad_id].copy()
        if rows.empty:
            return pd.DataFrame()
        rows = rows.merge(wda[["wda_id", "wda_name"]], on="wda_id", how="left")
        rows["chamber"] = "Assembly"
        rows["district_number"] = int(leg_row["district_number"])
        rows["legislator_id"] = leg_row["legislator_id"]
        rows["legislator_name"] = leg_row["full_name"]
        return rows[["legislator_id", "legislator_name", "chamber", "district_number",
                      "wda_id", "wda_name", "district_pop_in_overlap", "district_overlap_pct"]]

    sd_id_series = senate.loc[senate["district_number"].astype(int) == int(leg_row["district_number"]), "sd_id"]
    if sd_id_series.empty:
        return pd.DataFrame()
    sd_id = sd_id_series.iloc[0]
    rows = eligible_sd[eligible_sd["sd_id"] == sd_id].copy()
    if rows.empty:
        return pd.DataFrame()
    rows = rows.merge(wda[["wda_id", "wda_name"]], on="wda_id", how="left")
    rows["chamber"] = "Senate"
    rows["district_number"] = int(leg_row["district_number"])
    rows["legislator_id"] = leg_row["legislator_id"]
    rows["legislator_name"] = leg_row["full_name"]
    return rows[["legislator_id", "legislator_name", "chamber", "district_number",
                  "wda_id", "wda_name", "district_pop_in_overlap", "district_overlap_pct"]]


def _draft_notification_email(
    legislator_name: str,
    legislator_title: str,
    topic: str,
    wda_rows: pd.DataFrame,
) -> str:
    topic_line = topic.strip() if topic.strip() else "[topic]"
    lines = [
        f"Subject: CWA Outreach Coordination – {legislator_title} {legislator_name} – {topic_line}",
        "",
        "Dear Executive Directors,",
        "",
        f"The California Workforce Association (CWA) is communicating with {legislator_title} "
        f"{legislator_name} regarding {topic_line}.",
        "You are receiving this notification because your workforce development area serves "
        "constituents in this legislative district.",
        "",
        "Relevant overlap context:",
    ]
    for _, row in wda_rows.sort_values("district_pop_in_overlap", ascending=False).iterrows():
        lines.append(
            f"  • {row['wda_name']}: {_fmt_int(row['district_pop_in_overlap'])} residents "
            f"({_fmt_pct(row['district_overlap_pct'])} of district population)"
        )
    lines.extend([
        "",
        "Please coordinate any district-specific follow-up as appropriate.",
        "",
        "Sincerely,",
        "California Workforce Association",
    ])
    return "\n".join(lines)


def _render_wdb_contacts(wdb_contact: pd.DataFrame, wda_ids: Set[str]):
    st.subheader("WDB Executive Directors")
    rows = wdb_contact[wdb_contact["wda_id"].isin(wda_ids)]
    if rows.empty:
        st.info("No WDB contact rows found for this selection.")
        return
    table = rows[["organization_name", "executive_name", "title", "email", "phone"]].rename(
        columns={
            "organization_name": "Local Workforce Development Area",
            "executive_name": "Executive Director",
            "title": "Title",
            "email": "Email",
            "phone": "Phone",
        }
    )
    st.dataframe(
        table.sort_values(["Local Workforce Development Area", "Executive Director"]),
        use_container_width=True,
        hide_index=True,
    )


def _render_legislator_contacts(legislator: pd.DataFrame, legislator_office: pd.DataFrame, leg_ids: Set[str]):
    st.subheader("Legislator Contacts")
    leg_rows = legislator[legislator["legislator_id"].isin(leg_ids)]
    if leg_rows.empty:
        st.info("No legislator contact rows found for this selection.")
        return

    for _, leg in leg_rows.sort_values(["chamber", "district_number"]).iterrows():
        with st.container(border=True):
            party = _safe_text(leg.get("party", ""))
            suffix = f", {party}" if party else ""
            st.markdown(
                f"**{leg['full_name']}** "
                f"({leg['chamber'].title()} District {int(leg['district_number'])}{suffix})"
            )
            offices = legislator_office[legislator_office["legislator_id"] == leg["legislator_id"]]
            if offices.empty:
                st.write("No office details available.")
            else:
                for _, office in offices.iterrows():
                    label = _safe_text(office.get("label")) or _safe_text(office.get("office_type")) or "Office"
                    parts = [
                        label,
                        _safe_text(office.get("address", "")),
                        _safe_text(office.get("phone", "")),
                    ]
                    cform = _safe_text(office.get("contact_form_url", ""))
                    if cform:
                        parts.append(cform)
                    st.write(" | ".join([p for p in parts if p]))


def _assemble_context(data):
    wda = data["wda"]
    assembly = data["assembly"]
    senate = data["senate"]
    overlap_ad = data["wda_ad_overlap"].copy()
    overlap_sd = data["wda_sd_overlap"].copy()
    legislator = data["legislator"].copy()

    overlap_ad["is_display_eligible"] = overlap_ad["is_display_eligible"].astype(bool)
    overlap_sd["is_display_eligible"] = overlap_sd["is_display_eligible"].astype(bool)

    return wda, assembly, senate, overlap_ad, overlap_sd, legislator


# ---------------------------------------------------------------------------
# Page: Geographic Mapper
# ---------------------------------------------------------------------------

def render_mapper_page(data):
    wda, assembly, senate, overlap_ad, overlap_sd, legislator = _assemble_context(data)

    if data["source_mode"] == "demo":
        st.warning(
            "⚠️ Running with demo data — processed geographic files not found in /data/processed. "
            "Add production files there to switch automatically.",
            icon="⚠️",
        )

    with st.sidebar:
        st.header("🔍 Search")
        st.caption("Choose a lookup type to focus the map and relationship tables.")
        search_mode = st.selectbox(
            "Lookup type",
            ["Local Workforce Development Area", "Assembly District", "Senate District", "Legislator"],
            index=0,
        )

        selected_wda_id = None
        selected_ad_id = None
        selected_sd_id = None
        selected_leg_id = None

        if search_mode == "Local Workforce Development Area":
            options = wda[["wda_name", "wda_id"]].sort_values("wda_name")
            selected_name = st.selectbox("Select area", options["wda_name"].tolist())
            selected_wda_id = options.loc[options["wda_name"] == selected_name, "wda_id"].iloc[0]
        elif search_mode == "Assembly District":
            ad_nums = sorted(assembly["district_number"].astype(int).tolist())
            selected_num = st.selectbox("Assembly district", ad_nums)
            selected_ad_id = assembly.loc[assembly["district_number"] == selected_num, "ad_id"].iloc[0]
        elif search_mode == "Senate District":
            sd_nums = sorted(senate["district_number"].astype(int).tolist())
            selected_num = st.selectbox("Senate district", sd_nums)
            selected_sd_id = senate.loc[senate["district_number"] == selected_num, "sd_id"].iloc[0]
        else:
            leg_opts = legislator.sort_values("full_name")
            selected_name = st.selectbox("Legislator", leg_opts["full_name"].tolist())
            leg_row = leg_opts.loc[leg_opts["full_name"] == selected_name].iloc[0]
            selected_leg_id = leg_row["legislator_id"]
            if leg_row["chamber"] == "assembly":
                selected_ad_id = assembly.loc[
                    assembly["district_number"] == int(leg_row["district_number"]), "ad_id"
                ].iloc[0]
            else:
                selected_sd_id = senate.loc[
                    senate["district_number"] == int(leg_row["district_number"]), "sd_id"
                ].iloc[0]

        st.divider()
        st.header("🗺️ Map Layers")
        show_wda = st.checkbox("LWDA boundaries", value=True)
        show_ad = st.checkbox("Assembly boundaries", value=True)
        show_sd = st.checkbox("Senate boundaries", value=False)

    # ---- Resolve relationships ----
    related_wda_ids: Set[str] = set()
    related_ad_ids: Set[str] = set()
    related_sd_ids: Set[str] = set()
    related_leg_ids: Set[str] = set()

    eligible_ad = overlap_ad[overlap_ad["is_display_eligible"]]
    eligible_sd = overlap_sd[overlap_sd["is_display_eligible"]]

    rel_ad_rows = pd.DataFrame()
    rel_sd_rows = pd.DataFrame()

    if selected_wda_id:
        related_wda_ids = {selected_wda_id}
        rel_ad_rows = eligible_ad[eligible_ad["wda_id"] == selected_wda_id]
        rel_sd_rows = eligible_sd[eligible_sd["wda_id"] == selected_wda_id]
        related_ad_ids = set(rel_ad_rows["ad_id"].unique())
        related_sd_ids = set(rel_sd_rows["sd_id"].unique())

    if selected_ad_id:
        related_ad_ids.add(selected_ad_id)
        ad_rows = eligible_ad[eligible_ad["ad_id"] == selected_ad_id]
        related_wda_ids.update(ad_rows["wda_id"].unique())
        rel_ad_rows = ad_rows

    if selected_sd_id:
        related_sd_ids.add(selected_sd_id)
        sd_rows = eligible_sd[eligible_sd["sd_id"] == selected_sd_id]
        related_wda_ids.update(sd_rows["wda_id"].unique())
        rel_sd_rows = sd_rows

    if related_ad_ids:
        ad_nums = assembly[assembly["ad_id"].isin(related_ad_ids)]["district_number"].astype(int).tolist()
        related_leg_ids.update(
            legislator[
                (legislator["chamber"] == "assembly") & (legislator["district_number"].astype(int).isin(ad_nums))
            ]["legislator_id"].tolist()
        )

    if related_sd_ids:
        sd_nums = senate[senate["sd_id"].isin(related_sd_ids)]["district_number"].astype(int).tolist()
        related_leg_ids.update(
            legislator[
                (legislator["chamber"] == "senate") & (legislator["district_number"].astype(int).isin(sd_nums))
            ]["legislator_id"].tolist()
        )

    if selected_leg_id:
        related_leg_ids.add(selected_leg_id)

    # ---- Build map ----
    bounds = _base_bounds(data)
    focus_bounds = bounds
    if selected_wda_id:
        sel = _filter_ids(wda, "wda_id", [selected_wda_id])
        if not sel.empty:
            focus_bounds = list(sel.total_bounds)
    elif selected_ad_id:
        sel = _filter_ids(assembly, "ad_id", [selected_ad_id])
        if not sel.empty:
            focus_bounds = list(sel.total_bounds)
    elif selected_sd_id:
        sel = _filter_ids(senate, "sd_id", [selected_sd_id])
        if not sel.empty:
            focus_bounds = list(sel.total_bounds)
    elif related_wda_ids or related_ad_ids or related_sd_ids:
        focus_frames = []
        if related_wda_ids:
            f = _filter_ids(wda, "wda_id", related_wda_ids)
            if not f.empty:
                focus_frames.append(f)
        if related_ad_ids:
            f = _filter_ids(assembly, "ad_id", related_ad_ids)
            if not f.empty:
                focus_frames.append(f)
        if related_sd_ids:
            f = _filter_ids(senate, "sd_id", related_sd_ids)
            if not f.empty:
                focus_frames.append(f)
        if focus_frames:
            minx = min(f.total_bounds[0] for f in focus_frames)
            miny = min(f.total_bounds[1] for f in focus_frames)
            maxx = max(f.total_bounds[2] for f in focus_frames)
            maxy = max(f.total_bounds[3] for f in focus_frames)
            focus_bounds = [minx, miny, maxx, maxy]
    view_state = _view_state_from_bounds(focus_bounds)

    layers = []
    if show_wda:
        layers.append(_build_geojson_layer(wda, [10, 96, 152], [20, 105, 179, 25], line_width=2, opacity=0.2))
    if show_ad:
        layers.append(_build_geojson_layer(assembly, [184, 115, 51], [184, 115, 51, 20], line_width=2, opacity=0.2))
    if show_sd:
        layers.append(_build_geojson_layer(senate, [62, 145, 72], [62, 145, 72, 20], line_width=2, opacity=0.2))

    if related_wda_ids:
        layers.append(_build_geojson_layer(
            _filter_ids(wda, "wda_id", related_wda_ids), [0, 38, 64], [0, 102, 204, 80], line_width=4, opacity=0.45
        ))
    if related_ad_ids:
        layers.append(_build_geojson_layer(
            _filter_ids(assembly, "ad_id", related_ad_ids), [130, 59, 0], [255, 140, 0, 70], line_width=4, opacity=0.45
        ))
    if related_sd_ids:
        layers.append(_build_geojson_layer(
            _filter_ids(senate, "sd_id", related_sd_ids), [20, 94, 29], [50, 205, 50, 70], line_width=4, opacity=0.45
        ))

    st.subheader("Interactive Map")
    st.caption("Map auto-focuses to the selected area or district.")
    st.pydeck_chart(
        pdk.Deck(
            map_style="mapbox://styles/mapbox/light-v11",
            initial_view_state=view_state,
            layers=layers,
            tooltip={"text": "{wda_name}{district_number}"},
        ),
        use_container_width=True,
    )

    # ---- Selection summary ----
    st.subheader("Selection Summary")
    summary_lines = []
    if selected_wda_id:
        wda_name = wda.loc[wda["wda_id"] == selected_wda_id, "wda_name"].iloc[0]
        summary_lines.append(f"Local Area: **{wda_name}**")
    if selected_ad_id:
        ad_num = int(assembly.loc[assembly["ad_id"] == selected_ad_id, "district_number"].iloc[0])
        summary_lines.append(f"Assembly District: **{ad_num}**")
    if selected_sd_id:
        sd_num = int(senate.loc[senate["sd_id"] == selected_sd_id, "district_number"].iloc[0])
        summary_lines.append(f"Senate District: **{sd_num}**")
    if selected_leg_id:
        leg_name = legislator.loc[legislator["legislator_id"] == selected_leg_id, "full_name"].iloc[0]
        summary_lines.append(f"Legislator: **{leg_name}**")

    if summary_lines:
        cols = st.columns(len(summary_lines))
        for i, line in enumerate(summary_lines):
            cols[i].markdown(line)
    else:
        st.write("No selection")
    st.caption(
        f"Related: {len(related_wda_ids)} local areas · "
        f"{len(related_ad_ids)} Assembly districts · {len(related_sd_ids)} Senate districts"
    )

    st.divider()
    st.subheader("District Overlap Relationships")
    st.caption("Showing relationships where the local area accounts for ≥1% of district population.")
    tab1, tab2 = st.tabs(["Assembly Overlaps", "Senate Overlaps"])

    with tab1:
        if rel_ad_rows.empty:
            st.info("No Assembly overlaps for the current selection.")
        else:
            table = (
                rel_ad_rows
                .merge(wda[["wda_id", "wda_name"]], on="wda_id", how="left")
                .merge(assembly[["ad_id", "district_number"]], on="ad_id", how="left")
            )
            table = table[[
                "wda_name", "district_number",
                "district_pop_in_overlap", "district_total_pop", "district_overlap_pct",
                "wda_pop_in_overlap", "wda_total_pop", "wda_overlap_pct",
            ]].rename(columns={
                "wda_name": "Local Area",
                "district_number": "Assembly District",
                "district_pop_in_overlap": "District Pop. in Area",
                "district_total_pop": "District Total Pop.",
                "district_overlap_pct": "District Share in Area",
                "wda_pop_in_overlap": "LWDA Pop. in District",
                "wda_total_pop": "LWDA Total Pop.",
                "wda_overlap_pct": "LWDA Share in District",
            })
            table["District Share in Area"] = table["District Share in Area"].map(_fmt_pct)
            table["LWDA Share in District"] = table["LWDA Share in District"].map(_fmt_pct)
            st.dataframe(
                table.sort_values(["Assembly District", "Local Area"]),
                use_container_width=True, hide_index=True,
            )

    with tab2:
        if rel_sd_rows.empty:
            st.info("No Senate overlaps for the current selection.")
        else:
            table = (
                rel_sd_rows
                .merge(wda[["wda_id", "wda_name"]], on="wda_id", how="left")
                .merge(senate[["sd_id", "district_number"]], on="sd_id", how="left")
            )
            table = table[[
                "wda_name", "district_number",
                "district_pop_in_overlap", "district_total_pop", "district_overlap_pct",
                "wda_pop_in_overlap", "wda_total_pop", "wda_overlap_pct",
            ]].rename(columns={
                "wda_name": "Local Area",
                "district_number": "Senate District",
                "district_pop_in_overlap": "District Pop. in Area",
                "district_total_pop": "District Total Pop.",
                "district_overlap_pct": "District Share in Area",
                "wda_pop_in_overlap": "LWDA Pop. in District",
                "wda_total_pop": "LWDA Total Pop.",
                "wda_overlap_pct": "LWDA Share in District",
            })
            table["District Share in Area"] = table["District Share in Area"].map(_fmt_pct)
            table["LWDA Share in District"] = table["LWDA Share in District"].map(_fmt_pct)
            st.dataframe(
                table.sort_values(["Senate District", "Local Area"]),
                use_container_width=True, hide_index=True,
            )

    st.divider()
    st.subheader("Local Area Summaries")
    st.caption("Expand a local area to view overlap counts and leadership contact information.")
    if related_wda_ids:
        card_rows = wda[wda["wda_id"].isin(related_wda_ids)][["wda_id", "wda_name"]]
    else:
        card_rows = wda[["wda_id", "wda_name"]]

    for _, row in card_rows.sort_values("wda_name").iterrows():
        wda_id = row["wda_id"]
        ad_cnt = int(eligible_ad[eligible_ad["wda_id"] == wda_id]["ad_id"].nunique())
        sd_cnt = int(eligible_sd[eligible_sd["wda_id"] == wda_id]["sd_id"].nunique())
        contact = data["wdb_contact"][data["wdb_contact"]["wda_id"] == wda_id]
        with st.expander(row["wda_name"], expanded=False):
            st.write(f"Overlapping districts: {ad_cnt} Assembly, {sd_cnt} Senate")
            if not contact.empty:
                c = contact.iloc[0]
                st.write(
                    f"Executive Director: {c.get('executive_name', '—')}, {c.get('title', '—')} | "
                    f"Email: {c.get('email', '—')} | Phone: {c.get('phone', '—')}"
                )

    st.divider()
    st.subheader("Export & Notifications")
    st.caption(
        "Select one or more legislators to generate a deduplicated local area contact list, "
        "export CSV files, and draft a notification email."
    )
    leg_for_export = legislator.copy()
    leg_for_export["label"] = leg_for_export.apply(_build_legislator_label, axis=1)
    label_to_id = {r["label"]: r["legislator_id"] for _, r in leg_for_export.iterrows()}

    default_labels = []
    if selected_leg_id:
        selected_label = leg_for_export.loc[leg_for_export["legislator_id"] == selected_leg_id, "label"]
        if not selected_label.empty:
            default_labels = [selected_label.iloc[0]]

    selected_labels = st.multiselect(
        "Select one or more legislators",
        options=leg_for_export.sort_values(["chamber", "district_number"])["label"].tolist(),
        default=default_labels,
    )

    export_relationships = pd.DataFrame()
    if selected_labels:
        selected_ids = [label_to_id[x] for x in selected_labels]
        chunks = []
        for leg_id in selected_ids:
            leg_row = legislator[legislator["legislator_id"] == leg_id].iloc[0]
            chunk = _wdas_for_legislator(leg_row, assembly, senate, eligible_ad, eligible_sd, wda)
            if not chunk.empty:
                chunks.append(chunk)
        if chunks:
            export_relationships = pd.concat(chunks, ignore_index=True)

    if export_relationships.empty:
        st.info("Select legislators above to generate deduplicated WDB contact lists and exports.")
    else:
        wdb = data["wdb_contact"].copy()
        merged = export_relationships.merge(wdb, on="wda_id", how="left")
        merged["Local Workforce Development Area"] = merged["organization_name"].fillna(merged["wda_name"])
        merged["Executive Director"] = merged["executive_name"].fillna("")
        merged["Title"] = merged["title"].fillna("Executive Director")
        merged["Email"] = merged["email"].fillna("")
        merged["Phone"] = merged["phone"].fillna("")

        dedup_contacts = (
            merged.groupby(
                ["wda_id", "Local Workforce Development Area", "Executive Director", "Title", "Email", "Phone"],
                as_index=False,
            )
            .agg(
                Districts=("district_number", lambda x: ", ".join(sorted({str(int(v)) for v in x}))),
                Legislators=("legislator_name", lambda x: ", ".join(sorted(set(x)))),
            )
            .sort_values(["Local Workforce Development Area", "Executive Director"])
        )

        st.markdown("**Deduplicated WDB Executive Director List**")
        st.dataframe(
            dedup_contacts[[
                "Local Workforce Development Area", "Executive Director",
                "Title", "Email", "Phone", "Districts",
            ]],
            use_container_width=True, hide_index=True,
        )

        recipient_emails = sorted({
            e.strip() for e in dedup_contacts["Email"].tolist()
            if isinstance(e, str) and e.strip()
        })
        st.text_area(
            "To field (deduplicated emails)",
            value="; ".join(recipient_emails) if recipient_emails else "",
            height=80,
        )

        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button(
                "⬇️ Download WDB Contact List (CSV)",
                data=dedup_contacts[[
                    "Local Workforce Development Area", "Executive Director",
                    "Title", "Email", "Phone", "Districts", "Legislators",
                ]].to_csv(index=False),
                file_name="wdb_executive_director_contacts.csv",
                mime="text/csv",
            )
        with col_dl2:
            st.download_button(
                "⬇️ Download Relationship Data (CSV)",
                data=export_relationships.to_csv(index=False),
                file_name="legislator_wda_relationships.csv",
                mime="text/csv",
            )

        st.divider()
        primary_label = st.selectbox("Draft notification email for", selected_labels)
        topic = st.text_input("Topic", value="workforce policy priorities")
        primary_id = label_to_id[primary_label]
        primary_leg = legislator[legislator["legislator_id"] == primary_id].iloc[0]
        title = "Assemblymember" if primary_leg["chamber"] == "assembly" else "Senator"
        primary_rows = export_relationships[export_relationships["legislator_id"] == primary_id]
        draft = _draft_notification_email(primary_leg["full_name"], title, topic, primary_rows)
        st.text_area("Draft Notification Email", value=draft, height=260)
        st.download_button(
            "⬇️ Download Draft Email (.txt)",
            data=draft,
            file_name="draft_notification_email.txt",
            mime="text/plain",
        )

    st.divider()
    _render_wdb_contacts(
        data["wdb_contact"],
        related_wda_ids if related_wda_ids else set(wda["wda_id"].tolist()),
    )
    _render_legislator_contacts(data["legislator"], data["legislator_office"], related_leg_ids)


# ---------------------------------------------------------------------------
# Page: Day at the Capitol 2026
# ---------------------------------------------------------------------------

def render_datc_page(datc: dict):
    if not datc.get("data_loaded"):
        st.error(
            "Meeting Matrix data not found. Make sure "
            "`data/CWA_DATC_2026_Meeting_Matrix.xlsx` exists in the project folder."
        )
        return

    stats = datc["summary_stats"]
    matrix_full: pd.DataFrame = datc["matrix"]
    wda_order: list = datc["wda_order"]
    wda_abbrevs: dict = datc["wda_abbrevs"]
    area_attendees: dict = datc["area_attendees"]

    # ---- Summary banner ----
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Local Areas Attending", stats["total_areas"])
    c2.metric("Legislators Covered", f"{stats['covered_legislators']} / {stats['total_legislators']}")
    c3.metric("Must-Schedule Meetings", stats["must_schedule"])
    c4.metric("High Priority", stats["high_priority"])
    c5.metric("Total Attendees", stats["total_attendees"])

    st.divider()

    # ---- Filters (sidebar) ----
    with st.sidebar:
        st.header("🏛️ Filters")

        chamber_filter = st.radio(
            "Chamber",
            ["All", "Assembly", "Senate"],
            horizontal=True,
        )

        priority_filter = st.radio(
            "Priority",
            ["All", "High", "General"],
            horizontal=True,
        )

        coverage_filter = st.radio(
            "Coverage",
            ["All legislators", "Covered only", "No coverage only"],
            horizontal=True,
        )

        st.divider()
        st.header("📋 Highlight Area")
        highlight_wda = st.selectbox(
            "Highlight a local area",
            ["(none)"] + wda_order,
            index=0,
        )

        st.divider()
        st.header("🗂️ Show Columns")
        show_priority_cols = st.checkbox("Priority / Must Schedule", value=True)

    # ---- Filter the matrix ----
    df = matrix_full.copy()

    if chamber_filter != "All":
        df = df[df["Chamber"] == chamber_filter]

    if priority_filter != "All":
        df = df[df["Priority"] == priority_filter]

    if coverage_filter == "Covered only":
        has_any = df[wda_order].apply(lambda row: any(v in (OWN_SYMBOL, NEIGHBOR_SYMBOL) for v in row), axis=1)
        df = df[has_any]
    elif coverage_filter == "No coverage only":
        has_any = df[wda_order].apply(lambda row: any(v in (OWN_SYMBOL, NEIGHBOR_SYMBOL) for v in row), axis=1)
        df = df[~has_any]

    # ---- Build display columns ----
    # Use abbreviated names as column headers
    rename_map = {wda: wda_abbrevs.get(wda, wda) for wda in wda_order}
    display_cols = ["District", "Legislator", "Party"]
    if show_priority_cols:
        display_cols += ["Priority", "Must Schedule"]
    display_cols += wda_order  # WDA columns added after info cols

    df_display = df[display_cols].copy()
    df_display = df_display.rename(columns=rename_map)
    display_wda_cols = [rename_map.get(w, w) for w in wda_order]

    # ---- Legend and column notes ----
    st.markdown(
        f"**Legend:** &nbsp; "
        f"<span style='background:#c8e6c9;padding:2px 8px;border-radius:3px'>"
        f"**{OWN_SYMBOL}** Own district</span> &nbsp; "
        f"<span style='background:#fff9c4;padding:2px 8px;border-radius:3px'>"
        f"**{NEIGHBOR_SYMBOL}** Neighboring district</span>",
        unsafe_allow_html=True,
    )
    st.caption(
        f"Showing {len(df_display)} of {len(matrix_full)} legislators. "
        "Scroll right to see all local areas. Click a column header to sort."
    )

    # ---- Highlight a specific WDA ----
    highlight_col = rename_map.get(highlight_wda, highlight_wda) if highlight_wda != "(none)" else None

    # Apply styling
    def _style_row(row):
        styles = [""] * len(row)
        for i, col in enumerate(row.index):
            val = row[col]
            if col in display_wda_cols:
                if val == OWN_SYMBOL:
                    bg = "#c8e6c9"
                    fw = "bold"
                elif val == NEIGHBOR_SYMBOL:
                    bg = "#fff9c4"
                    fw = "normal"
                else:
                    bg = "white"
                    fw = "normal"
                border = f"2px solid #1a73e8;" if (col == highlight_col and val != "") else ""
                styles[i] = f"background-color:{bg};text-align:center;font-weight:{fw};{border}"
            elif col == "Priority" and val == "High":
                styles[i] = "color:#c62828;font-weight:bold;"
            elif col == "Must Schedule" and val == "Yes":
                styles[i] = "color:#c62828;font-weight:bold;"
        return styles

    styled = df_display.style.apply(_style_row, axis=1)

    # Configure column widths
    col_config = {
        "District": st.column_config.TextColumn("District", width="small"),
        "Legislator": st.column_config.TextColumn("Legislator", width="medium"),
        "Party": st.column_config.TextColumn("Party", width="small"),
    }
    if show_priority_cols:
        col_config["Priority"] = st.column_config.TextColumn("Priority", width="small")
        col_config["Must Schedule"] = st.column_config.TextColumn("Sched?", width="small")
    for abbr in display_wda_cols:
        col_config[abbr] = st.column_config.TextColumn(abbr, width="small")

    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        column_config=col_config,
        height=600,
    )

    # ---- Export ----
    st.divider()
    col_exp1, col_exp2 = st.columns([1, 3])
    with col_exp1:
        export_df = df[["Chamber", "District", "Legislator", "Party", "Priority", "Must Schedule"] + wda_order].copy()
        st.download_button(
            "⬇️ Download Coverage Matrix (CSV)",
            data=export_df.to_csv(index=False),
            file_name="datc_coverage_matrix.csv",
            mime="text/csv",
        )

    st.divider()

    # ---- Attending area details ----
    st.subheader("Attending Local Areas")
    st.caption("Click to expand each area and see who is attending Day at the Capitol.")

    # Group by region
    region_groups: dict = {}
    for area_name in wda_order:
        region = WDA_REGIONS.get(area_name, "Other")
        region_groups.setdefault(region, []).append(area_name)

    region_order = ["Bay Area", "Northern CA", "Central Valley", "Central Coast",
                    "Southern CA", "Orange County", "Inland Empire", "San Diego", "Border", "Other"]

    for region in region_order:
        if region not in region_groups:
            continue
        with st.expander(f"**{region}** ({len(region_groups[region])} areas)", expanded=False):
            for area_name in region_groups[region]:
                people = area_attendees.get(area_name, [])
                own_count = int(matrix_full[area_name].eq(OWN_SYMBOL).sum()) if area_name in matrix_full.columns else 0
                nbr_count = int(matrix_full[area_name].eq(NEIGHBOR_SYMBOL).sum()) if area_name in matrix_full.columns else 0
                st.markdown(
                    f"**{area_name}** — {own_count} own-district meetings, {nbr_count} neighbor meetings"
                )
                if people:
                    for p in people:
                        st.write(f"  • {p}")
                else:
                    st.write("  *(attendee details not available)*")
                st.write("")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    data = get_data()
    datc = get_datc_data()

    # ---- Navigation ----
    with st.sidebar:
        st.image(
            "https://img.icons8.com/fluency/48/000000/capitol.png",
            width=40,
        )
        st.title("CWA Legislative Tools")
        page = st.radio(
            "Navigate to",
            ["📍 Geographic Mapper", "🏛️ Day at the Capitol 2026"],
            label_visibility="collapsed",
        )
        st.divider()

    if page == "📍 Geographic Mapper":
        st.title("CA LWDA & Legislative District Mapper")
        st.caption(
            "Select a local workforce development area, district, or legislator to explore "
            "geographic overlap relationships and generate contact lists."
        )
        render_mapper_page(data)

    elif page == "🏛️ Day at the Capitol 2026":
        st.title("Day at the Capitol 2026")
        st.caption(
            "Coverage matrix showing which local areas are meeting with each legislator — "
            f"**{OWN_SYMBOL}** indicates the area's own district; "
            f"**{NEIGHBOR_SYMBOL}** indicates a geographically proximate neighboring district."
        )
        render_datc_page(datc)


if __name__ == "__main__":
    main()
