# NGT Case Monitor

This repository contains an automated monitor for the National Green Tribunal case page at `https://www.greentribunal.gov.in/caseDetails/PUNE/2704138000312025?page=order`. A scheduled GitHub Actions workflow fetches the page every day at **09:00 IST (03:30 UTC)**, compares key text with the previous run, and sends an email if there is either a change or a monitoring failure (e.g., request blocked, HTTP error).

## How It Works

- `ngt_watch.py` pulls the target page, extracts lines mentioning case status, next hearing, or orders, and hashes the content to detect changes.
- `.state/last_hash.txt` stores the hash of the latest known state so that change detection works across workflow runs.
- The workflow defined in `.github/workflows/check-ngt.yaml` installs dependencies, runs the watcher, commits the updated state file when a change occurs, and sends an email notification whenever the status is not `ok`.

## Local Setup

1. Install Python 3.11 or newer.
2. Install the required packages:

   ```powershell
   pip install -r requirements.txt
   ```

3. Run the watcher locally if you want to test it outside GitHub Actions:

   ```powershell
   python ngt_watch.py
   ```

The script writes `result.json` describing the run outcome. Remove the file afterward if you do not want it tracked by git.

## GitHub Actions Configuration

The workflow runs automatically every day at 09:00 IST. You can also trigger it manually from the **Actions** tab using the **Run workflow** button.

To allow the workflow to send email notifications, add the following **repository secrets** under **Settings → Secrets and variables → Actions**:

| Secret Name     | Example Value / Notes                          |
|-----------------|------------------------------------------------|
| `SMTP_SERVER`   | `smtp.gmail.com`                               |
| `SMTP_PORT`     | `587` (TLS)                                    |
| `SMTP_USERNAME` | Email/username used to authenticate            |
| `SMTP_PASSWORD` | App password or SMTP credential                |
| `TO_EMAIL`      | Recipient email address                        |
| `FROM_EMAIL`    | Displayed sender email address                 |

> **Note:** If you use Gmail, create an **App Password** (requires 2FA) and use it for `SMTP_PASSWORD`; regular passwords are blocked by Google.

## Troubleshooting

- **Connection errors / blocking:** The script marks runs as `error` when it cannot fetch the page or detects anti-bot responses. Inspect `result.json` (or the email body) for details.
- **Spam filtering:** Messages sent via generic SMTP accounts may land in spam. Consider a transactional provider (e.g., SendGrid, SES) if this becomes an issue.
- **State reset:** Deleting `.state/last_hash.txt` forces the next run to treat the page as changed and record a fresh baseline.
