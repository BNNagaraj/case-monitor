"""HTTP-based monitoring implementation."""
from __future__ import annotations

import hashlib
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from .logging_utils import setup_logging
from .state import DEFAULT_REPORT_PATH, DEFAULT_STATE_PATH, read_last_hash, write_last_hash, write_report

DEFAULT_URL = "https://www.greentribunal.gov.in/caseDetails/PUNE/2704138000312025?page=order"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

BLOCK_PATTERNS = [
    r"access denied",
    r"forbidden",
    r"blocked",
    r"bot",
    r"captcha",
    r"unusual traffic",
    r"rate limit",
    r"http 40[3-9]",
    r"error 50[0-9]",
]


@dataclass
class FetchAttempt:
    attempt: int
    status_code: Optional[int]
    error: Optional[str]


@dataclass
class FetchResult:
    status_code: int
    html: str
    error: str
    attempts: List[FetchAttempt]


def extract_key_text(html: str) -> str:
    """Conservative extractor: prefer lines with key phrases; fall back to all text."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
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
    return any(re.search(pattern, low) for pattern in BLOCK_PATTERNS)


def fetch(
    url: str,
    *,
    max_retries: int = 3,
    initial_delay: float = 5.0,
    backoff_factor: float = 2.0,
    timeout: int = 20,
) -> FetchResult:
    logger = logging.getLogger(__name__)
    attempts: List[FetchAttempt] = []
    sleep_for = max(initial_delay, 0)
    last_error: str = ""
    status_code: int = 0

    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Fetching %s (attempt %s/%s)", url, attempt, max_retries)
            response = requests.get(url, headers=HEADERS, timeout=timeout)
            status_code = response.status_code
            if response.status_code == 200 and response.text:
                attempts.append(FetchAttempt(attempt, response.status_code, None))
                logger.info("Fetch succeeded with HTTP %s", response.status_code)
                return FetchResult(response.status_code, response.text, "", attempts)
            last_error = f"HTTP {response.status_code}"
        except requests.RequestException as exc:  # pragma: no cover - network errors simulated in tests
            last_error = str(exc)
            status_code = 0
        attempts.append(FetchAttempt(attempt, status_code or None, last_error))
        logger.warning("Fetch attempt %s failed: %s", attempt, last_error)
        if attempt < max_retries:
            logger.info("Sleeping %.1fs before retry", sleep_for)
            time.sleep(sleep_for)
            sleep_for = max(sleep_for * backoff_factor, 0)

    return FetchResult(status_code, "", last_error or "Unknown fetch error", attempts)


def run_scrape(
    *,
    url: Optional[str] = None,
    state_path: Path = DEFAULT_STATE_PATH,
    report_path: Path = DEFAULT_REPORT_PATH,
    return_result: bool = False,
) -> Optional[dict]:
    setup_logging()
    logger = logging.getLogger(__name__)

    url = url or os.getenv("NGT_URL", DEFAULT_URL)
    logger.info("Starting scrape for %s", url)

    fetch_result = fetch(url)
    result = {
        "status": "ok",
        "http_status": fetch_result.status_code,
        "message": "",
        "excerpt": "",
        "url": url,
        "attempts": [attempt.__dict__ for attempt in fetch_result.attempts],
    }

    if not fetch_result.html:
        result["status"] = "error"
        result["message"] = f"Failed to fetch the page. Details: {fetch_result.error or f'HTTP {fetch_result.status_code}'}"
        logger.error(result["message"])
        write_report(result, report_path)
        return result if return_result else None

    if looks_blocked(fetch_result.html, fetch_result.status_code):
        result["status"] = "error"
        result["message"] = f"Site may be blocking or unstable. HTTP {fetch_result.status_code}."
        result["excerpt"] = fetch_result.html[:1000]
        logger.error(result["message"])
        write_report(result, report_path)
        return result if return_result else None

    key_text = extract_key_text(fetch_result.html)
    curr_hash = hashlib.sha256(key_text.encode("utf-8")).hexdigest()
    last_hash = read_last_hash(state_path)

    if curr_hash != last_hash:
        result["status"] = "changed"
        result["message"] = "Change detected in Case Status / Next Hearing / Orders."
        result["excerpt"] = key_text[:5000]
        logger.info("Change detected; updating stored hash")
        write_last_hash(curr_hash, state_path)
    else:
        result["status"] = "ok"
        result["message"] = "No change."
        logger.info("No changes detected")

    write_report(result, report_path)
    return result if return_result else None


def main() -> None:
    run_scrape(return_result=False)


__all__ = [
    "BLOCK_PATTERNS",
    "FetchAttempt",
    "FetchResult",
    "HEADERS",
    "extract_key_text",
    "fetch",
    "looks_blocked",
    "main",
    "run_scrape",
]
