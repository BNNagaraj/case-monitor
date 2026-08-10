from types import SimpleNamespace

import requests

from case_monitor import scrape


def test_extract_key_text_prefers_key_lines():
    html = """
    <html><body>
    <div>Random intro</div>
    <div>Case Status: Pending</div>
    <div>Next Hearing: 01-01-2025</div>
    </body></html>
    """
    result = scrape.extract_key_text(html)
    assert "Case Status" in result
    assert "Next Hearing" in result
    assert "Random" not in result


def test_extract_key_text_fallback_returns_all_text():
    html = "<html><body><p>Nothing important here</p></body></html>"
    result = scrape.extract_key_text(html)
    assert "Nothing important here" in result


def test_looks_blocked_detects_patterns():
    assert scrape.looks_blocked("Access Denied", 200)
    assert scrape.looks_blocked("anything", 500)


def test_fetch_retries_and_backoff(monkeypatch):
    call_count = {"value": 0}

    def fake_get(url, headers, timeout):
        call_count["value"] += 1
        if call_count["value"] == 1:
            raise requests.exceptions.Timeout("boom")
        return SimpleNamespace(status_code=200, text="ok")

    sleep_calls = []

    monkeypatch.setattr(scrape.requests, "get", fake_get)
    monkeypatch.setattr(scrape.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    result = scrape.fetch("https://example.com", max_retries=2, initial_delay=1)

    assert result.html == "ok"
    assert len(result.attempts) == 2
    assert sleep_calls == [1]
