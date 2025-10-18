import base64
import hashlib
import json
import os
from pathlib import Path

from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

STATE_FILE = ".state/last_hash.txt"
REPORT_FILE = "result.json"
SCREENSHOT = "page.png"

URL = os.getenv(
        "NGT_URL",
        "https://www.greentribunal.gov.in/caseDetails/PUNE/2704138000312025?page=order",
)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

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


def read_last_hash() -> str:
    try:
        return Path(STATE_FILE).read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def write_last_hash(h: str) -> None:
    state_path = Path(STATE_FILE)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(h, encoding="utf-8")


def take_screenshot() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        try:
            page.goto(URL, wait_until="load", timeout=60000)
            page.screenshot(path=SCREENSHOT, full_page=True)
        except PlaywrightTimeoutError as exc:
            page.screenshot(path=SCREENSHOT, full_page=True)
            raise RuntimeError(f"Timed out loading page: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            if page.content():
                page.screenshot(path=SCREENSHOT, full_page=True)
            raise
        finally:
            browser.close()


def create_placeholder_screenshot(message: str) -> None:
    img = Image.new("RGB", (1600, 900), color="white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    text = "NGT Case Monitor\n" + message
    draw.multiline_text((40, 40), text, fill="black", font=font, spacing=4)
    img.save(SCREENSHOT, format="PNG")


def analyze_with_openai() -> dict:
    if not client:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set.")

    with open(SCREENSHOT, "rb") as screenshot_file:
        image_b64 = base64.b64encode(screenshot_file.read()).decode("utf-8")

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

    return json.loads(message_content)


def main() -> None:
    result = {"status": "ok", "url": URL}

    try:
        take_screenshot()
        parsed = analyze_with_openai()
        result.update(parsed)

        content_str = json.dumps(parsed, sort_keys=True)
        curr_hash = hashlib.sha256(content_str.encode("utf-8")).hexdigest()
        last_hash = read_last_hash()

        if curr_hash != last_hash:
            result["status"] = "changed"
            result["message"] = "Change detected in case details."
            write_last_hash(curr_hash)
        else:
            result["message"] = "No change detected."

    except Exception as exc:  # noqa: BLE001
        if not Path(SCREENSHOT).exists():
            create_placeholder_screenshot(f"Error: {exc}")
        result = {
            "status": "error",
            "message": str(exc),
            "url": URL,
        }

    Path(REPORT_FILE).write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
