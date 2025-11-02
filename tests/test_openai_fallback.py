import pytest

from case_monitor import openai_mode


@pytest.fixture(autouse=True)
def clear_openai_env(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def test_run_openai_falls_back_to_scraper(monkeypatch, tmp_path):
    fallback_called = {"value": False}

    def fake_run_scrape(**kwargs):
        fallback_called["value"] = True
        assert kwargs["url"] == "https://example.com"
        assert kwargs["return_result"] is True
        return {"status": "ok", "url": kwargs["url"], "message": "fallback"}

    monkeypatch.setattr(openai_mode, "run_scrape", fake_run_scrape)

    result = openai_mode.run_openai(
        url="https://example.com",
        state_path=tmp_path / "state.txt",
        report_path=tmp_path / "report.json",
        screenshot_path=tmp_path / "page.png",
        return_result=True,
    )

    assert fallback_called["value"] is True
    assert result["message"] == "fallback"
