# Web Scraper with BeautifulSoup

A command-line Python scraper that fetches a page, parses it with
BeautifulSoup, and exports useful structured data.

## Install

```powershell
pip install -r requirements_scraper.txt
```

## Run

Print a JSON summary:

```powershell
python web_scraper.py https://example.com
```

Save links and page metadata to JSON:

```powershell
python web_scraper.py https://example.com --format json --output page.json
```

Extract matching elements with a CSS selector:

```powershell
python web_scraper.py https://news.ycombinator.com --selector ".titleline > a" --format csv --output headlines.csv
```

Print a readable text report:

```powershell
python web_scraper.py https://example.com --format text
```

## What It Extracts

- Page title and description
- `h1`, `h2`, and `h3` headings
- Links with absolute URLs
- Images with absolute URLs
- Optional CSS selector matches
- A plain-text page excerpt

## Notes

The scraper checks `robots.txt` by default. Use `--ignore-robots` only when you
have permission to scrape the target page.
