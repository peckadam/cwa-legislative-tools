from __future__ import annotations

from pathlib import Path
from typing import Dict, Any

import geopandas as gpd
import pandas as pd
from shapely.geometry import box


REQUIRED_FILES = {
    "wda": "wda.geojson",
    "assembly": "assembly.geojson",
    "senate": "senate.geojson",
    "wda_ad_overlap": "wda_ad_overlap.csv",
    "wda_sd_overlap": "wda_sd_overlap.csv",
    "wdb_contact": "wdb_contact.csv",
    "legislator": "legislator.csv",
    "legislator_office": "legislator_office.csv",
}


def _load_geo(path: Path) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")
    return gdf


def _load_real(data_dir: Path) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    data["wda"] = _load_geo(data_dir / REQUIRED_FILES["wda"])
    data["assembly"] = _load_geo(data_dir / REQUIRED_FILES["assembly"])
    data["senate"] = _load_geo(data_dir / REQUIRED_FILES["senate"])

    for name in [
        "wda_ad_overlap",
        "wda_sd_overlap",
        "wdb_contact",
        "legislator",
        "legislator_office",
    ]:
        data[name] = pd.read_csv(data_dir / REQUIRED_FILES[name])

    staff_path = data_dir / "legislator_staff.csv"
    data["legislator_staff"] = pd.read_csv(staff_path) if staff_path.exists() else pd.DataFrame()
    data["source_mode"] = "processed"
    return data


def _demo_data() -> Dict[str, Any]:
    wda = gpd.GeoDataFrame(
        [
            {"wda_id": "WDA_SF", "wda_name": "San Francisco WDA", "geometry": box(-122.53, 37.70, -122.35, 37.84)},
            {"wda_id": "WDA_EB", "wda_name": "East Bay WDA", "geometry": box(-122.35, 37.65, -121.90, 37.95)},
            {"wda_id": "WDA_SC", "wda_name": "Silicon Valley WDA", "geometry": box(-122.10, 37.20, -121.70, 37.55)},
        ],
        crs="EPSG:4326",
    )

    assembly = gpd.GeoDataFrame(
        [
            {"ad_id": "AD17", "district_number": 17, "geometry": box(-122.52, 37.65, -122.15, 37.90)},
            {"ad_id": "AD18", "district_number": 18, "geometry": box(-122.25, 37.55, -121.75, 37.90)},
        ],
        crs="EPSG:4326",
    )

    senate = gpd.GeoDataFrame(
        [
            {"sd_id": "SD11", "district_number": 11, "geometry": box(-122.55, 37.60, -122.00, 37.95)},
            {"sd_id": "SD13", "district_number": 13, "geometry": box(-122.20, 37.15, -121.65, 37.75)},
        ],
        crs="EPSG:4326",
    )

    wda_ad_overlap = pd.DataFrame(
        [
            {
                "wda_id": "WDA_SF",
                "ad_id": "AD17",
                "district_pop_in_overlap": 220000,
                "district_total_pop": 510000,
                "district_overlap_pct": 43.137,
                "wda_pop_in_overlap": 220000,
                "wda_total_pop": 310000,
                "wda_overlap_pct": 70.968,
                "is_display_eligible": True,
            },
            {
                "wda_id": "WDA_EB",
                "ad_id": "AD17",
                "district_pop_in_overlap": 120000,
                "district_total_pop": 510000,
                "district_overlap_pct": 23.529,
                "wda_pop_in_overlap": 120000,
                "wda_total_pop": 430000,
                "wda_overlap_pct": 27.907,
                "is_display_eligible": True,
            },
            {
                "wda_id": "WDA_EB",
                "ad_id": "AD18",
                "district_pop_in_overlap": 260000,
                "district_total_pop": 530000,
                "district_overlap_pct": 49.057,
                "wda_pop_in_overlap": 260000,
                "wda_total_pop": 430000,
                "wda_overlap_pct": 60.465,
                "is_display_eligible": True,
            },
            {
                "wda_id": "WDA_SC",
                "ad_id": "AD18",
                "district_pop_in_overlap": 220000,
                "district_total_pop": 530000,
                "district_overlap_pct": 41.509,
                "wda_pop_in_overlap": 220000,
                "wda_total_pop": 340000,
                "wda_overlap_pct": 64.706,
                "is_display_eligible": True,
            },
        ]
    )

    wda_sd_overlap = pd.DataFrame(
        [
            {
                "wda_id": "WDA_SF",
                "sd_id": "SD11",
                "district_pop_in_overlap": 240000,
                "district_total_pop": 1020000,
                "district_overlap_pct": 23.529,
                "wda_pop_in_overlap": 240000,
                "wda_total_pop": 310000,
                "wda_overlap_pct": 77.419,
                "is_display_eligible": True,
            },
            {
                "wda_id": "WDA_EB",
                "sd_id": "SD11",
                "district_pop_in_overlap": 260000,
                "district_total_pop": 1020000,
                "district_overlap_pct": 25.49,
                "wda_pop_in_overlap": 260000,
                "wda_total_pop": 430000,
                "wda_overlap_pct": 60.465,
                "is_display_eligible": True,
            },
            {
                "wda_id": "WDA_EB",
                "sd_id": "SD13",
                "district_pop_in_overlap": 140000,
                "district_total_pop": 1010000,
                "district_overlap_pct": 13.861,
                "wda_pop_in_overlap": 140000,
                "wda_total_pop": 430000,
                "wda_overlap_pct": 32.558,
                "is_display_eligible": True,
            },
            {
                "wda_id": "WDA_SC",
                "sd_id": "SD13",
                "district_pop_in_overlap": 300000,
                "district_total_pop": 1010000,
                "district_overlap_pct": 29.703,
                "wda_pop_in_overlap": 300000,
                "wda_total_pop": 340000,
                "wda_overlap_pct": 88.235,
                "is_display_eligible": True,
            },
        ]
    )

    wdb_contact = pd.DataFrame(
        [
            {
                "wda_id": "WDA_SF",
                "organization_name": "San Francisco Workforce Development Board",
                "executive_name": "Alex Rivera",
                "title": "Executive Director",
                "email": "alex.rivera@sfwdb.org",
                "phone": "(415) 555-0101",
            },
            {
                "wda_id": "WDA_EB",
                "organization_name": "East Bay Workforce Board",
                "executive_name": "Jordan Lee",
                "title": "Executive Director",
                "email": "jordan.lee@ebwdb.org",
                "phone": "(510) 555-0188",
            },
            {
                "wda_id": "WDA_SC",
                "organization_name": "Silicon Valley Workforce Board",
                "executive_name": "Taylor Kim",
                "title": "Executive Director",
                "email": "taylor.kim@svwdb.org",
                "phone": "(408) 555-0142",
            },
        ]
    )

    legislator = pd.DataFrame(
        [
            {
                "legislator_id": "ASM_17",
                "chamber": "assembly",
                "district_number": 17,
                "full_name": "Asm. Example One",
                "party": "D",
            },
            {
                "legislator_id": "ASM_18",
                "chamber": "assembly",
                "district_number": 18,
                "full_name": "Asm. Example Two",
                "party": "D",
            },
            {
                "legislator_id": "SEN_11",
                "chamber": "senate",
                "district_number": 11,
                "full_name": "Sen. Example Three",
                "party": "D",
            },
            {
                "legislator_id": "SEN_13",
                "chamber": "senate",
                "district_number": 13,
                "full_name": "Sen. Example Four",
                "party": "D",
            },
        ]
    )

    legislator_office = pd.DataFrame(
        [
            {
                "legislator_id": "ASM_17",
                "office_type": "capitol",
                "label": "Capitol Office",
                "address": "1021 O St, Sacramento, CA",
                "phone": "(916) 555-0117",
                "email": "",
                "contact_form_url": "https://example.org/asm17/contact",
            },
            {
                "legislator_id": "ASM_17",
                "office_type": "district",
                "label": "San Francisco District Office",
                "address": "455 Golden Gate Ave, San Francisco, CA",
                "phone": "(415) 555-0117",
                "email": "",
                "contact_form_url": "",
            },
            {
                "legislator_id": "SEN_11",
                "office_type": "capitol",
                "label": "Capitol Office",
                "address": "1021 O St, Sacramento, CA",
                "phone": "(916) 555-0211",
                "email": "",
                "contact_form_url": "https://example.org/sen11/contact",
            },
        ]
    )

    return {
        "wda": wda,
        "assembly": assembly,
        "senate": senate,
        "wda_ad_overlap": wda_ad_overlap,
        "wda_sd_overlap": wda_sd_overlap,
        "wdb_contact": wdb_contact,
        "legislator": legislator,
        "legislator_office": legislator_office,
        "legislator_staff": pd.DataFrame(),
        "source_mode": "demo",
    }


def load_datasets(data_dir: Path) -> Dict[str, Any]:
    missing = [f for f in REQUIRED_FILES.values() if not (data_dir / f).exists()]
    if missing:
        return _demo_data()
    return _load_real(data_dir)
