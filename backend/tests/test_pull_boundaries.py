"""Pull uses primary sources only (BUILD_PLAN §0): nothing in finn/pull may import a search, news or web client."""
import pathlib
import re

BANNED = re.compile(r"^\s*(from|import)\s+(tavily|serpapi|googlesearch|duckduckgo\w*|newsapi|feedparser|bs4|requests|httpx)\b"
                    r"|^\s*from\s+\.\.(push\.mgmt|sources\.fetchers)\s+import\s+.*(tavily|search|news)", re.M | re.I)


def test_pull_has_no_web_news_or_search_code():
    pull = pathlib.Path(__file__).resolve().parents[1] / "finn" / "pull"
    offenders = [f"{p.name}: {m.group(0).strip()}" for p in pull.glob("*.py") for m in BANNED.finditer(p.read_text())]
    assert offenders == []
    assert not re.search(r"tavily|api\.search|newsapi", " ".join(p.read_text().lower() for p in pull.glob("*.py")))
