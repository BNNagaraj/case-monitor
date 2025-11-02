import os, time, hashlib, json, re
from typing import Tuple
import requests
from bs4 import BeautifulSoup

URL = os.getenv("NGT_URL", "https://www.greentribunal.gov.in/caseDetails/PUNE/2704138000312025?page=order")
STATE_FILE = ".state/last_hash.txt"
REPORT_FILE = "result.json"

HEADERS = {
    # Pretend to be a real browser to reduce bot-blocking
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

BLOCK_PATTERNS = [
    r"access denied", r"forbidden", r"blocked", r"bot", r"captcha",
    r"unusual traffic", r"rate limit", r"http 40[3-9]", r"error 50[0-9]"
]

def read_last_hash() -> str:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""

def write_last_hash(h: str) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        f.write(h)

def extract_key_text(html: str) -> str:
    """Conservative extractor: prefer lines with key phrases; fall back to all text."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    # Prefer relevant sections if present
    key_lines = []
    for line in text.splitlines():
        low = line.lower()
        if any(k in low for k in ["case status", "next hearing", "order", "orders", "hearing"]):
            key_lines.append(line)
    if key_lines:
        return "\n".join(key_lines)
    return text

def looks_blocked(html_or_msg: str, status_code: int) -> bool:
    if status_code >= 400:
        return True
    low = html_or_msg.lower()
    return any(re.search(p, low) for p in BLOCK_PATTERNS)

def fetch(max_retries=3, sleep_between=10, timeout=20) -> Tuple[int, str, str]:
    last_err = ""
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(URL, headers=HEADERS, timeout=timeout)
            if r.status_code == 200 and r.text:
                return r.status_code, r.text, ""
            last_err = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            last_err = str(e)
        time.sleep(sleep_between)
    return 0, "", last_err or "Unknown fetch error"

def main():
    status_code, html, err = fetch()
    result = {
        "status": "ok",  # ok | changed | error
        "http_status": status_code,
        "message": "",
        "excerpt": "",
        "url": URL,
    }

    if not html:
        # Could not fetch content at all → treat as error (website down/blocked)
        result["status"] = "error"
        result["message"] = f"Failed to fetch the page. Details: {err or f'HTTP {status_code}'}"
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return

    if looks_blocked(html, status_code):
        result["status"] = "error"
        result["message"] = f"Site may be blocking or unstable. HTTP {status_code}."
        # Include a small excerpt to help you see what was returned
        result["excerpt"] = html[:1000]
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return

    key_text = extract_key_text(html)
    curr_hash = hashlib.sha256(key_text.encode("utf-8")).hexdigest()
    last_hash = read_last_hash()

    if curr_hash != last_hash:
        result["status"] = "changed"
        result["message"] = "Change detected in Case Status / Next Hearing / Orders."
        # Include a concise excerpt for the email body
        result["excerpt"] = key_text[:5000]
        write_last_hash(curr_hash)
    else:
        result["status"] = "ok"
        result["message"] = "No change."

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
