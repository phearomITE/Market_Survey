from datetime import date
from types import SimpleNamespace

from app.reports.movement_multi_export import build_movement_rows, parse_movement_multi_dates


def _metric(name, score):
    return SimpleNamespace(product_name=name, movement_score=score)


def test_movement_multi_dates_and_all_product_columns():
    dates = parse_movement_multi_dates(
        ["2026-07-04", "2026-07-18", "2026-07-25"]
    )
    assert dates == [date(2026, 7, 4), date(2026, 7, 18), date(2026, 7, 25)]

    submission = SimpleNamespace(
        id=1,
        report_date=date(2026, 7, 25),
        submission_time=None,
        region="R1",
        dealer="CA1",
        gps_latitude=11.5,
        gps_longitude=104.9,
        outlet_name="Test",
        outlet_type="Drink Shop",
        phone_number="012",
        product_metrics=[_metric("CB LITE NCP", 10)],
        competitor_metrics=[
            _metric("GB SNOW NCP", 8),
            _metric("Hanuman LITE NCP", 7),
            _metric("Krud LITE NCP", 6),
            _metric("Greet LITE NCP", 5),
        ],
    )
    row = build_movement_rows([submission])[0]
    assert row[8:] == [10, 8, 7, 6, 5]


def test_bot_registers_export_commands():
    source = open("app/bot/run_bot.py", encoding="utf-8").read()
    assert 'CommandHandler("raw_movement", raw_movement_cmd)' in source
    assert 'CommandHandler("export", export_cmd)' in source
