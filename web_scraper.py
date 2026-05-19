from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO


DEFAULT_USER_AGENT = (
    "BeautifulSoupDemoScraper/1.0 "
    "(educational project; contact: local-user)"
)


@dataclass
class Heading:
    level: str
    text: str


@dataclass
class Link:
    text: str
    url: str


@dataclass
class Image:
    alt: str
    url: str


@dataclass
class SelectedElement:
    tag: str
    text: str
    href: str
    src: str


@dataclass
class ScrapedPage:
    requested_url: str
    final_url: str
    fetched_at: str
    title: str
    description: str
    headings: list[Heading]
    links: list[Link]
    images: list[Image]
    selected_elements: list[SelectedElement]
    text_excerpt: str


def load_beautifulsoup() -> Any:
    try:
        from bs4 import BeautifulSoup
    except ImportError as error:
        raise SystemExit(
            "Missing dependency: beautifulsoup4\n"
            "Install it with: pip install -r requirements_scraper.txt"
        ) from error
    return BeautifulSoup


def fetch_html(url: str, user_agent: str, timeout: int) -> tuple[str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get_content_charset() or "utf-8"
            html = response.read().decode(content_type, errors="replace")
            return html, response.geturl()
    except urllib.error.HTTPError as error:
        raise SystemExit(f"HTTP error {error.code}: {error.reason}") from error
    except urllib.error.URLError as error:
        raise SystemExit(f"Could not fetch URL: {error.reason}") from error


def can_fetch(url: str, user_agent: str, timeout: int) -> bool:
    parsed = urllib.parse.urlparse(url)
    robots_url = urllib.parse.urlunparse(
        (parsed.scheme, parsed.netloc, "/robots.txt", "", "", "")
    )
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)
    try:
        request = urllib.request.Request(robots_url, headers={"User-Agent": user_agent})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            lines = response.read().decode("utf-8", errors="replace").splitlines()
        parser.parse(lines)
    except (urllib.error.URLError, TimeoutError, OSError):
        return True
    return parser.can_fetch(user_agent, url)


def normalize_url(url: str) -> str:
    if re.match(r"^https?://", url, re.I):
        return url
    return f"https://{url}"


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def absolute_attr(base_url: str, value: str | None) -> str:
    if not value:
        return ""
    return urllib.parse.urljoin(base_url, value)


def page_text(soup: Any, limit: int) -> str:
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()

    lines = [clean_text(line) for line in soup.get_text("\n").splitlines()]
    text = "\n".join(line for line in lines if line)
    return text[:limit] if limit > 0 else text


def scrape_page(
    url: str,
    selector: str,
    limit: int,
    text_limit: int,
    user_agent: str,
    timeout: int,
    ignore_robots: bool,
) -> ScrapedPage:
    requested_url = normalize_url(url)
    if not ignore_robots and not can_fetch(requested_url, user_agent, timeout):
        raise SystemExit(
            "The site's robots.txt rules do not allow this URL to be fetched. "
            "Use --ignore-robots only if you have permission."
        )

    html, final_url = fetch_html(requested_url, user_agent, timeout)
    BeautifulSoup = load_beautifulsoup()
    soup = BeautifulSoup(html, "html.parser")

    title = clean_text(soup.title.get_text()) if soup.title else ""
    description_tag = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    description = ""
    if description_tag and description_tag.get("content"):
        description = clean_text(description_tag["content"])

    headings = [
        Heading(level=tag.name, text=clean_text(tag.get_text()))
        for tag in soup.select("h1, h2, h3")
        if clean_text(tag.get_text())
    ][:limit]

    links = []
    for tag in soup.find_all("a", href=True):
        text = clean_text(tag.get_text()) or "(no text)"
        absolute_url = urllib.parse.urljoin(final_url, tag["href"])
        links.append(Link(text=text, url=absolute_url))
        if len(links) >= limit:
            break

    images = []
    for tag in soup.find_all("img", src=True):
        alt = clean_text(tag.get("alt", ""))
        absolute_url = urllib.parse.urljoin(final_url, tag["src"])
        images.append(Image(alt=alt, url=absolute_url))
        if len(images) >= limit:
            break

    selected_elements = []
    if selector:
        for tag in soup.select(selector)[:limit]:
            selected_elements.append(
                SelectedElement(
                    tag=tag.name,
                    text=clean_text(tag.get_text()),
                    href=absolute_attr(final_url, tag.get("href")),
                    src=absolute_attr(final_url, tag.get("src")),
                )
            )

    return ScrapedPage(
        requested_url=requested_url,
        final_url=final_url,
        fetched_at=datetime.now().isoformat(timespec="seconds"),
        title=title,
        description=description,
        headings=headings,
        links=links,
        images=images,
        selected_elements=selected_elements,
        text_excerpt=page_text(soup, text_limit),
    )


def page_to_dict(page: ScrapedPage) -> dict[str, Any]:
    return asdict(page)


def write_json(page: ScrapedPage, destination: TextIO) -> None:
    json.dump(page_to_dict(page), destination, indent=2, ensure_ascii=False)
    destination.write("\n")


def write_text(page: ScrapedPage, destination: TextIO) -> None:
    destination.write(f"Title: {page.title or '(untitled)'}\n")
    destination.write(f"URL: {page.final_url}\n")
    if page.description:
        destination.write(f"Description: {page.description}\n")

    if page.headings:
        destination.write("\nHeadings\n")
        for heading in page.headings:
            destination.write(f"- {heading.level.upper()}: {heading.text}\n")

    if page.selected_elements:
        destination.write("\nSelected Elements\n")
        for element in page.selected_elements:
            detail = element.href or element.src
            suffix = f" [{detail}]" if detail else ""
            destination.write(f"- <{element.tag}> {element.text}{suffix}\n")

    if page.links:
        destination.write("\nLinks\n")
        for link in page.links:
            destination.write(f"- {link.text}: {link.url}\n")

    if page.text_excerpt:
        destination.write("\nText Excerpt\n")
        destination.write(page.text_excerpt)
        destination.write("\n")


def write_csv(page: ScrapedPage, destination: TextIO) -> None:
    if page.selected_elements:
        writer = csv.DictWriter(destination, fieldnames=["tag", "text", "href", "src"])
        writer.writeheader()
        for element in page.selected_elements:
            writer.writerow(asdict(element))
        return

    writer = csv.DictWriter(destination, fieldnames=["text", "url"])
    writer.writeheader()
    for link in page.links:
        writer.writerow(asdict(link))


def write_output(page: ScrapedPage, output_format: str, output_path: str) -> None:
    if output_path:
        path = Path(output_path)
        with path.open("w", encoding="utf-8", newline="") as destination:
            write_by_format(page, output_format, destination)
        print(f"Saved {output_format.upper()} output to {path}")
        return

    write_by_format(page, output_format, sys.stdout)


def write_by_format(page: ScrapedPage, output_format: str, destination: TextIO) -> None:
    if output_format == "json":
        write_json(page, destination)
    elif output_format == "csv":
        write_csv(page, destination)
    else:
        write_text(page, destination)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scrape a web page with BeautifulSoup and export structured data."
    )
    parser.add_argument("url", help="Page URL to scrape, such as https://example.com")
    parser.add_argument(
        "-s",
        "--selector",
        default="",
        help="Optional CSS selector to extract, such as 'article h2 a'",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=("json", "csv", "text"),
        default="json",
        help="Output format. CSV exports selected elements, or links when no selector is used.",
    )
    parser.add_argument("-o", "--output", default="", help="File path for exported data.")
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of headings, links, images, or selected elements.",
    )
    parser.add_argument(
        "--text-limit",
        type=int,
        default=2000,
        help="Maximum text excerpt length. Use 0 for no limit.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="Network timeout in seconds.",
    )
    parser.add_argument(
        "--user-agent",
        default=DEFAULT_USER_AGENT,
        help="User-Agent header sent with requests.",
    )
    parser.add_argument(
        "--ignore-robots",
        action="store_true",
        help="Skip robots.txt checking. Only use when you have permission.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    page = scrape_page(
        url=args.url,
        selector=args.selector,
        limit=max(args.limit, 1),
        text_limit=max(args.text_limit, 0),
        user_agent=args.user_agent,
        timeout=max(args.timeout, 1),
        ignore_robots=args.ignore_robots,
    )
    write_output(page, args.format, args.output)


if __name__ == "__main__":
    main()
