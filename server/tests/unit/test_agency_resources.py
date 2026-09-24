from szyg.api import agency_routes
from szyg.agency_manifest import RESOURCE_DIRNAME, RETAINED_DIVISIONS


def test_agency_resources_use_internal_package_root():
    root = agency_routes._resolve_agency_root()

    assert root.name == RESOURCE_DIRNAME
    assert "external" not in root.parts
    assert (root / "divisions.json").is_file()
    assert all((root / division).is_dir() for division in RETAINED_DIVISIONS)


def test_agency_market_localizes_catalog_for_english():
    agency_routes._build_cache()
    source = next(item for item in agency_routes._cache_agents if item["name"] != item["name_en"])

    english = agency_routes._localized_agent(source, "en-US")
    chinese = agency_routes._localized_agent(source, "zh-CN")
    division = agency_routes._localized_division(agency_routes._cache_divisions[0], "en-US")

    assert english["name"] == source["name_en"]
    assert english["description"] == source["description_en"]
    assert chinese["name"] == source["name"]
    assert division["label"] == agency_routes._cache_divisions[0]["label_en"]
