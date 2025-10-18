# NGT Case Monitor

This repository contains an automated, AI-assisted monitor for the National Green Tribunal case page at `https://www.greentribunal.gov.in/caseDetails/PUNE/2704138000312025?page=order`. A scheduled GitHub Actions workflow fetches the page every day at **09:00 IST (03:30 UTC)**, captures a headless Chromium screenshot, extracts structured details using OpenAI Vision, compares results with the previous run, and emails you only when something changes or the fetch fails.

## How It Works

- `ngt_watch_openai.py` launches Playwright (Chromium) to capture `page.png`, asks OpenAI Vision (`gpt-4o-mini`) to summarise case metadata, and produces `result.json`.
- `.state/last_hash.txt` stores the hash of the latest known state so that change detection works across workflow runs.
- The workflow defined in `.github/workflows/check-ngt.yaml` installs dependencies with pip caching, runs the AI watcher, uploads both the screenshot and `result.json` as artifacts, commits the updated state file when a change occurs, and sends an email notification whenever the status is not `ok`.

## Local Setup

1. Install Python 3.11 or newer.
2. Install the required packages:

   ```powershell
   pip install -r requirements.txt
   ```

3. Install Playwright browsers (first run only):

   ```powershell
   python -m playwright install
   ```

4. Run the AI watcher locally (requires `OPENAI_API_KEY` in your environment):

   ```powershell
   $env:OPENAI_API_KEY="sk-..."
   python ngt_watch_openai.py
   ```

The script writes `result.json` and `page.png`. Clean them up afterward if you do not want them tracked by git.

## GitHub Actions Configuration

The workflow runs automatically every day at 09:00 IST. You can also trigger it manually from the **Actions** tab using the **Run workflow** button.

Add the following **repository secrets** under **Settings → Secrets and variables → Actions**:

| Secret Name       | Example Value / Notes                                   |
|-------------------|---------------------------------------------------------|
| `OPENAI_API_KEY`  | API key with access to `gpt-4o-mini`                     |
| `SMTP_SERVER`     | `smtp.gmail.com`                                         |
| `SMTP_PORT`       | `587` (TLS)                                             |
| `SMTP_USERNAME`   | Email/username used to authenticate                      |
| `SMTP_PASSWORD`   | App password or SMTP credential                          |
| `TO_EMAIL`        | Recipient email address                                  |
| `FROM_EMAIL`      | Displayed sender email address                           |
| `HTTP_PROXY`      | *(Optional)* proxy URL such as `http://user:pass@host:port` |
| `HTTPS_PROXY`     | *(Optional)* secure proxy URL                             |

> **Note:** If you use Gmail, create an **App Password** (requires 2FA) and use it for `SMTP_PASSWORD`; regular passwords are blocked by Google.

## Troubleshooting

- **Connection errors / blocking:** The script marks runs as `error` when it cannot fetch the page or detects anti-bot responses. Inspect `result.json` (or the email body) for details. Configure `HTTP_PROXY`/`HTTPS_PROXY` secrets if you need to route requests through a proxy.
- **Spam filtering:** Messages sent via generic SMTP accounts may land in spam. Consider a transactional provider (e.g., SendGrid, SES) if this becomes an issue.
- **State reset:** Deleting `.state/last_hash.txt` forces the next run to treat the page as changed and record a fresh baseline.
