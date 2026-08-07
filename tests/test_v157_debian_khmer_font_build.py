from pathlib import Path


def test_dockerfile_uses_a_debian_bookworm_khmer_font() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert "fonts-noto-core" in dockerfile
    assert "Noto Sans Khmer" in dockerfile
    assert "fonts-khmeros-core" not in dockerfile


def test_runtime_report_font_matches_the_docker_font() -> None:
    report_source = Path("app/reports/excel_report.py").read_text(
        encoding="utf-8"
    )
    render_source = Path("app/services/render_service.py").read_text(
        encoding="utf-8"
    )

    assert 'SUMMARY_FONT_NAME = "Noto Sans Khmer"' in report_source
    assert '"Noto Sans Khmer"' in render_source
