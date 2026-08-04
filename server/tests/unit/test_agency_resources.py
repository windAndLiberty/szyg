from szyg.api import agency_routes
from szyg.agency_manifest import RESOURCE_DIRNAME, RETAINED_DIVISIONS


def test_agency_resources_use_internal_package_root():
    root = agency_routes._resolve_agency_root()

    assert root.name == RESOURCE_DIRNAME
    assert "external" not in root.parts
    assert (root / "divisions.json").is_file()
    assert all((root / division).is_dir() for division in RETAINED_DIVISIONS)
