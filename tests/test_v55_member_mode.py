from __future__ import annotations

from types import SimpleNamespace

from app.reports.member_mode import most_frequent_member
from app.reports.summary_report import build_summary_rows


def _row(member, outlet, dealer="CA1"):
    return SimpleNamespace(
        dealer=dealer,
        member_no=member,
        outlet_name=outlet,
        total_outlet_visit_target=None,
    )


def test_most_frequent_member_uses_highest_submission_count():
    rows = (
        [_row(7, f"Outlet 7-{i}") for i in range(9)]
        + [_row(8, f"Outlet 8-{i}") for i in range(3)]
        + [_row(1, "Outlet 1")]
        + [_row(69966165, "Wrong Telegram ID")]
        + [_row(None, "Blank Member")]
    )

    assert most_frequent_member(rows) == "7"


def test_summary_report_uses_only_most_frequent_member():
    rows = (
        [_row("7", f"Outlet A-{i}") for i in range(5)]
        + [_row("8", f"Outlet B-{i}") for i in range(2)]
        + [_row("69966165", "Outlet Wrong")]
        # Summary-marker row must not influence the selected Member.
        + [_row("3", "បូកសរុបរួម")]
    )

    summary_rows = build_summary_rows(rows)
    ca1 = next(row for row in summary_rows if row["dealer"] == "CA1")

    assert ca1["member"] == "7"
    assert ca1["total_submissions"] == 8
    assert ca1["total_outlets"] == 8
