from __future__ import annotations

from app.kobo.client import KoboClient
from app.kobo.parser import normalize_submission


def main() -> None:
    rows = KoboClient().fetch_submissions()
    print(f"Fetched Kobo rows: {len(rows)}")
    if not rows:
        return
    first = rows[0]
    print("First row keys:")
    for k in first.keys():
        print(" -", k)
    print("\nNormalized first row:")
    data = normalize_submission(first)
    for k in ["submission_id", "region", "dealer", "report_date", "outlet_name", "outlet_type", "location_text", "key_issue_text", "suggestion_text"]:
        print(f"{k}: {data.get(k)}")


if __name__ == "__main__":
    main()
