from pathlib import Path

from app.reports.aggregator import movement_statistics


ROOT = Path(__file__).resolve().parents[1]


def test_final_movement_uses_mean_and_median_without_forcing_ten():
    result = movement_statistics([6, 7, 9, 7, 7, 8, 10, 8], total_outlets=10)

    assert result["mean"] == 7.75
    assert result["median"] == 7.5
    assert result["analysis"] == 7.7
    assert result["display"] == 8
    assert result["valid_count"] == 8
    assert result["coverage"] == 80.0
    assert result["provisional"] is False


def test_real_zero_is_valid_but_blank_is_excluded():
    result = movement_statistics([0, None, "", 10], total_outlets=3)

    assert result["valid_count"] == 2
    assert result["analysis"] == 5.0
    assert result["display"] == 5


def test_small_sample_is_provisional():
    assert movement_statistics([2, 4], total_outlets=10)["provisional"] is True


def test_map_dashboard_assets_and_duplicate_polling_handler_exist():
    run_bot = (ROOT / "app/bot/run_bot.py").read_text(encoding="utf-8")

    assert "_start_web_server()" in run_bot
    assert "app.add_error_handler(_telegram_error_handler)" in run_bot
    assert "isinstance(context.error, Conflict)" in run_bot
    assert (ROOT / "app/web/map.html").is_file()
    assert (ROOT / "app/web/map.css").is_file()


def test_horeca_report_does_not_print_channel_specialist_label():
    source = (ROOT / "app/reports/excel_report.py").read_text(encoding="utf-8")

    assert 'ws["A3"] = f"Dealer : {dealer}    CHANNEL SPECIALIST' not in source
