from app.services.report_service import parse_multi_report_command_args


def test_parse_five_dealers_space_separated():
    dealers, date_str = parse_multi_report_command_args(
        ["CPH2", "CA2", "KDL1", "CA1", "CA7", "2026-07-14"]
    )
    assert dealers == ["CPH2", "CA2", "KDL1", "CA1", "CA7"]
    assert date_str == "2026-07-14"


def test_parse_comma_separated_and_remove_duplicates():
    dealers, date_str = parse_multi_report_command_args(
        ["CPH2,CA2,KDL1", "CA2", "CA1,CA7", "2026-07-14"]
    )
    assert dealers == ["CPH2", "CA2", "KDL1", "CA1", "CA7"]
    assert date_str == "2026-07-14"


def test_parse_rejects_unknown_dealer():
    try:
        parse_multi_report_command_args(["CPH2", "BAD1", "2026-07-14"])
    except ValueError as exc:
        assert "Unknown dealer" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
