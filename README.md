# Spin-off Tracker

Spin-off Tracker is a script-based Python project that scrapes recently completed stock spin-offs, keeps a persistent local universe, builds weekly and daily chart images for each parent/spun-off company, and sends those images to Telegram in company-pairs.

## Architecture

- `src/scrape_spinoffs.py` scrapes StockAnalysis year pages plus the recent page and filters completed spin-offs to the last 18 months.
- `src/universe.py` stores a cleaned, deduplicated universe in `data/tracked_spinoffs.json` so the daily job can fall back to local state if the scrape fails.
- `src/fetch_prices.py` pulls `1Day` and `1Week` stock bars from Alpaca Market Data API.
- `src/charting.py` renders one candlestick chart per ticker and timeframe.
- `src/combine_images.py` assembles one two-panel image per company, with weekly on top and daily below.
- `src/telegram_sender.py` sends each spin-off pair to Telegram as separate images in sequence, child first and parent second when both exist.
- `src/run_daily.py` is the main scheduled entrypoint.
- `src/send_all_to_telegram.py` is the one-shot script that immediately generates and sends every current pair.
- `src/run_scheduler.py` waits for the configured 9:00 schedule and launches the daily job automatically.

## Project Layout

```text
Spinoff Automation/
  config/
    settings.example.yaml
  data/
    tracked_spinoffs.json
  output/
    charts/
    logs/
  src/
    __init__.py
    charting.py
    combine_images.py
    fetch_prices.py
    logging_utils.py
    run_daily.py
    run_scheduler.py
    scrape_spinoffs.py
    send_all_to_telegram.py
    settings.py
    telegram_sender.py
    universe.py
  requirements.txt
  README.md
```

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

3. Copy `config/settings.example.yaml` to `config/settings.yaml` if you want to override defaults.
4. Create a local `.env` file from `.env.example`, or set market-data and Telegram credentials in environment variables.

Example `.env`:

```dotenv
APCA_API_KEY_ID=your_alpaca_key_id
APCA_API_SECRET_KEY=your_alpaca_secret_key
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id,another_chat_id
```

Environment variable alternative:

```bash
set APCA_API_KEY_ID=your_alpaca_key_id
set APCA_API_SECRET_KEY=your_alpaca_secret_key
set TELEGRAM_BOT_TOKEN=your_bot_token
set TELEGRAM_CHAT_ID=your_chat_id
```

PowerShell:

```powershell
$env:APCA_API_KEY_ID="your_alpaca_key_id"
$env:APCA_API_SECRET_KEY="your_alpaca_secret_key"
$env:TELEGRAM_BOT_TOKEN="your_bot_token"
$env:TELEGRAM_CHAT_ID="your_chat_id,another_chat_id"
```

## Running

Scrape and persist the universe only:

```bash
python -m src.scrape_spinoffs
```

Run the full daily workflow:

```bash
python -m src.run_daily
```

Run the one-shot Telegram sender script:

```bash
python -m src.send_all_to_telegram
```

Or run it directly:

```bash
python src/send_all_to_telegram.py
```

Useful flags:

- `python -m src.run_daily --skip-telegram`
- `python -m src.run_daily --skip-refresh`
- `python -m src.run_daily --max-pairs 5`
- `python -m src.send_all_to_telegram --max-pairs 5`

Run the built-in scheduler:

```bash
python -m src.run_scheduler
```

The scheduler uses the `schedule` section in the YAML file and runs the daily job at the configured `hour` and `minute`.

## GitHub Actions

The repository includes [send-spinoff-charts.yml](C:/Codex/Spinoff%20Automation/.github/workflows/send-spinoff-charts.yml).

It supports:

- `workflow_dispatch` for manual runs
- a daily schedule at `01:00 UTC`, which is `09:00` in `Asia/Hong_Kong`

Add these repository secrets before enabling the workflow:

- `APCA_API_KEY_ID`
- `APCA_API_SECRET_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

`TELEGRAM_CHAT_ID` can be a comma-separated list if you want the bot to send to multiple Telegram users.

The workflow installs dependencies and runs:

```bash
python -m src.send_all_to_telegram
```

## Configuration

Non-secret settings live in YAML:

- StockAnalysis base URL and request timeout
- Alpaca market-data API base URL, feed, and adjustment mode
- universe file path and refresh behavior
- chart output location
- whether local chart output is deleted before and after each run
- chart bar counts for daily and weekly charts
- Telegram delivery behavior
- optional max pairs per run
- scheduler timezone and run time

Secrets stay in environment variables:

- `APCA_API_KEY_ID`
- `APCA_API_SECRET_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## Output

- During a normal Telegram run, chart files are created only long enough to send and are then deleted.
- If you run with `--skip-telegram`, the generated chart files remain under `output/charts/YYYY-MM-DD/` for inspection.
- Logs are written to `output/logs/`.

## Known Limitations

- The scraper depends on the public StockAnalysis table layout remaining compatible with `pandas.read_html`.
- Alpaca market data requires both `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY`.
- Historical stock bars come from `https://data.alpaca.markets/v2`; the paper trading base URL `https://paper-api.alpaca.markets/v2` is for trading/account endpoints, not stock-bar downloads.
- Free Alpaca plans commonly use the `iex` feed, which may have thinner historical coverage than premium SIP data.
- Very new or thinly traded symbols may have incomplete or stale daily/weekly data, which can lead to placeholder panels or skipped pairs if no usable history is returned.
- Telegram delivery is sequential rather than grouped, so large runs can produce many individual messages.

## Next Steps

- Add retry and backoff for Alpaca downloads if rate limits become an issue.
- Add a small smoke-test suite for scraper parsing and price resampling.
- Add optional image cleanup or retention rules for older daily runs.

## Source Notes

- Initial universe source: https://stockanalysis.com/actions/spinoffs/
- Alpaca Historical API base URL docs: https://docs.alpaca.markets/docs/historical-api
- Alpaca Trading API getting started docs: https://docs.alpaca.markets/docs/getting-started-with-trading-api
- Telegram Bot API reference for `sendPhoto` and `sendMediaGroup`: https://core.telegram.org/bots/api
