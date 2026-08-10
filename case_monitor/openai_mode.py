"""Playwright + OpenAI monitoring implementation."""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Optional

from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .logging_utils import setup_logging
from .scrape import run_scrape
from .state import (
    DEFAULT_REPORT_PATH,
    DEFAULT_STATE_PATH,
    read_last_hash,
    write_last_hash,
    write_report,
)

DEFAULT_URL = "https://www.greentribunal.gov.in/caseDetails/PUNE/2704138000312025?page=order"
DEFAULT_SCREENSHOT = Path("page.png")

PROMPT = """
From this NGT case webpage screenshot, extract and summarize:
1. Case Status (Pending / Disposed / Order Reserved / etc.)
2. Next Hearing Date
3. Recent Order Summary
4. Any other remarks or updates.

Return JSON in the format:
{
    "case_status": "...",
    "next_hearing_date": "...",
    "order_summary": "...",
    "remarks": "..."
}
"""


class ScreenshotError(RuntimeError):
    """Raised when a screenshot could not be captured."""


def _create_client(api_key: Optional[str]) -> Optional[OpenAI]:
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def take_screenshot(url: str, screenshot_path: Path) -> None:
    logger = logging.getLogger(__name__)
    proxy_server = (
        os.getenv("PLAYWRIGHT_PROXY")
        or os.getenv("HTTPS_PROXY")
        or os.getenv("HTTP_PROXY")
        or ""
    )

    launch_kwargs: dict = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
    if proxy_server:
        launch_kwargs["proxy"] = {"server": proxy_server}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**launch_kwargs)
        page = browser.new_page()
        try:
            logger.info("Navigating to %s", url)
            page.goto(url, wait_until="load", timeout=60000)
            page.screenshot(path=screenshot_path, full_page=True)
            logger.info("Screenshot saved to %s", screenshot_path)
        except PlaywrightTimeoutError as exc:  # pragma: no cover - requires Playwright runtime
            page.screenshot(path=screenshot_path, full_page=True)
            logger.exception("Timed out loading page")
            raise ScreenshotError(f"Timed out loading page: {exc}") from exc
        except Exception:
            if page.content():  # pragma: no cover - requires Playwright runtime
                page.screenshot(path=screenshot_path, full_page=True)
            logger.exception("Unexpected error when capturing screenshot")
            raise
        finally:
            browser.close()


def create_placeholder_screenshot(message: str, screenshot_path: Path) -> None:
    img = Image.new("RGB", (1600, 900), color="white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    text = "NGT Case Monitor\n" + message
    draw.multiline_text((40, 40), text, fill="black", font=font, spacing=4)
    img.save(screenshot_path, format="PNG")


def analyze_with_openai(client: OpenAI, screenshot_path: Path) -> dict:
    logger = logging.getLogger(__name__)
    with screenshot_path.open("rb") as screenshot_file:
        image_b64 = base64.b64encode(screenshot_file.read()).decode("utf-8")

    logger.info("Sending screenshot to OpenAI for analysis")
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an NGT case webpage analyst."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT.strip()},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                    },
                ],
            },
        ],
        response_format={"type": "json_object"},
    )

    message_content = response.choices[0].message.content
    if not message_content:
        raise RuntimeError("OpenAI response did not include any content.")

    logger.info("Received structured response from OpenAI")
    return json.loads(message_content)


def run_openai(
    *,
    url: Optional[str] = None,
    state_path: Path = DEFAULT_STATE_PATH,
    report_path: Path = DEFAULT_REPORT_PATH,
    screenshot_path: Path = DEFAULT_SCREENSHOT,
    client: Optional[OpenAI] = None,
    allow_fallback: bool = True,
    return_result: bool = False,
) -> Optional[dict]:
    setup_logging()
    logger = logging.getLogger(__name__)

    url = url or os.getenv("NGT_URL", DEFAULT_URL)
    logger.info("Starting OpenAI-assisted monitoring for %s", url)

    api_key = os.getenv("OPENAI_API_KEY")
    if client is None:
        client = _create_client(api_key)

    if client is None:
        logger.warning("OPENAI_API_KEY is not set; falling back to HTTP scraping mode")
        if not allow_fallback:
            raise RuntimeError("OPENAI_API_KEY environment variable is not set.")
        return run_scrape(
            url=url,
            state_path=state_path,
            report_path=report_path,
            return_result=return_result,
        )

    result = {"status": "ok", "url": url}

    try:
        take_screenshot(url, screenshot_path)
        parsed = analyze_with_openai(client, screenshot_path)
        result.update(parsed)

        content_str = json.dumps(parsed, sort_keys=True)
        curr_hash = hashlib.sha256(content_str.encode("utf-8")).hexdigest()
        last_hash = read_last_hash(state_path)

        if curr_hash != last_hash:
            result["status"] = "changed"
            result["message"] = "Change detected in case details."
            logger.info("Detected change in OpenAI summary; updating stored hash")
            write_last_hash(curr_hash, state_path)
        else:
            result["message"] = "No change detected."
            logger.info("No changes detected in OpenAI summary")

    except Exception as exc:  # noqa: BLE001
        logger.exception("Error during OpenAI monitoring")
        if not screenshot_path.exists():
            create_placeholder_screenshot(f"Error: {exc}", screenshot_path)
        result = {
            "status": "error",
            "message": str(exc),
            "url": url,
        }

    write_report(result, report_path)
    return result if return_result else None


def main() -> None:
    run_openai(return_result=False)


__all__ = [
    "PROMPT",
    "analyze_with_openai",
    "create_placeholder_screenshot",
    "run_openai",
    "take_screenshot",
]
