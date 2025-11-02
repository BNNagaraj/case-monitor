# NGT Case Monitor

This repository contains an automated, AI-assisted monitor for the National Green Tribunal case page at `https://www.greentribunal.gov.in/caseDetails/PUNE/2704138000312025?page=order`. A scheduled GitHub Actions workflow fetches the page every day at **09:00 IST (03:30 UTC)**, captures a headless Chromium screenshot, optionally asks OpenAI Vision for a structured summary, compares results with the previous run, and records artifacts whenever something changes or the fetch fails.

## How It Works

- `python -m case_monitor --mode scrape` performs a lightweight HTTP scrape, extracts the key case text with BeautifulSoup, and produces `result.json`.
- `python -m case_monitor --mode openai` launches Playwright (Chromium) to capture `page.png`, asks OpenAI Vision (`gpt-4o-mini`) to summarise case metadata, and produces `result.json`. If the OpenAI client is unavailable, the command automatically falls back to the scraping mode unless you pass `--no-fallback`.
- `.state/last_hash.txt` stores the hash of the latest known state so that change detection works across workflow runs.
- The workflow defined in `.github/workflows/case-monitor.yaml` restores the last known hash from the previous run, installs dependencies, runs the selected watcher, and uploads the screenshot and `result.json` as short-lived artifacts for review.

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

4. Run the scraper locally:

   ```powershell
   python -m case_monitor --mode scrape
   ```

5. Run the AI watcher locally (requires `OPENAI_API_KEY` in your environment):

   ```powershell
   $env:OPENAI_API_KEY="sk-..."
   python -m case_monitor --mode openai
   ```

Both commands write `result.json`. The AI mode also writes `page.png`. Clean them up afterward if you do not want them tracked by git.

## Observability

Both execution modes emit structured logs to stdout. Set `CASE_MONITOR_LOG_LEVEL=DEBUG` to see fetch retries, proxy selection, and OpenAI request progress, which is especially useful when diagnosing bot protection or API failures.

## GitHub Actions Configuration

The workflow runs automatically every day at 09:00 IST. You can also trigger it manually from the **Actions** tab using the **Run workflow** button.

Add the following **repository secrets** under **Settings → Secrets and variables → Actions** (all optional except the OpenAI key when running the AI workflow):

| Secret Name      | Example Value / Notes                                      |
|------------------|------------------------------------------------------------|
| `OPENAI_API_KEY` | API key with access to `gpt-4o-mini`                        |
| `HTTP_PROXY`     | *(Optional)* proxy URL such as `http://user:pass@host:port` |
| `HTTPS_PROXY`    | *(Optional)* secure proxy URL                               |

## Continuous Monitoring Workflow

The `Case monitor` workflow restores the previous `.state/last_hash.txt` from a retained artifact, executes `python -m case_monitor` in the requested mode, then uploads the refreshed hash, `result.json`, and `page.png` artifacts. Trigger it manually from the **Actions** tab (choose `scrape` or `openai` mode) or let the scheduled 03:30 UTC run execute automatically. Inspect `result.json` and `page.png` from the workflow artifacts for each run.

## Testing

Run the automated checks locally with:

```powershell
pytest
```

## Troubleshooting

- **Connection errors / blocking:** The script marks runs as `error` when it cannot fetch the page or detects anti-bot responses. Inspect `result.json` in the workflow artifacts for details. Configure `HTTP_PROXY`/`HTTPS_PROXY` secrets if you need to route requests through a proxy.
- **OpenAI disabled:** When `OPENAI_API_KEY` is missing, the OpenAI mode automatically falls back to the scraping mode. Pass `--no-fallback` to force a failure instead.
- **State reset:** Deleting `.state/last_hash.txt` forces the next run to treat the page as changed and record a fresh baseline.
