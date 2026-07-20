from types import SimpleNamespace

from app.reports.aggregator import combine_location_visit
from app.reports.data_export import _header_key, _joined_locations


def test_location_variants_are_combined_without_duplicates():
    rows = [
        SimpleNamespace(location_text="Phnom Penh, Psar prek pnov"),
        SimpleNamespace(location_text="psar prek pov, Saroang"),
        SimpleNamespace(location_text="Samroang, Praek Pnov"),
        SimpleNamespace(location_text="ព្រែកព្នៅ, ដំបូកខ្ពស់, Pnov"),
    ]

    expected = "Phnom Penh, Prek Pnov, Samroang, ដំបូកខ្ពស់"
    assert combine_location_visit([row.location_text for row in rows]) == expected
    assert _joined_locations(rows) == expected


def test_approved_location_header_key():
    assert _header_key("Location of Visit Text") == "locationofvisittext"
