import json

from case_monitor import state


def test_state_read_write_roundtrip(tmp_path):
    state_path = tmp_path / "state.txt"
    report_path = tmp_path / "report.json"

    state.write_last_hash("abc123", state_path)
    assert state.read_last_hash(state_path) == "abc123"

    payload = {"status": "ok"}
    state.write_report(payload, report_path)
    written = json.loads(report_path.read_text(encoding="utf-8"))
    assert written == payload
