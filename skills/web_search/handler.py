"""
web_search skill — lightweight DuckDuckGo search via their HTML
interface (no API key required).

Fetches the DuckDuckGo HTML results page and extracts titles, URLs,
and snippets with a simple regex-free parser so there are no external
HTML-parsing dependencies.
"""

import re
import html

import httpx

SEARCH_URL     = "https://html.duckduckgo.com/html/"
DEFAULT_LIMIT  = 5
REQUEST_TIMEOUT = 10  # seconds

# Minimal headers to look like a real browser request
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

tools = [
    {
        "name": "search_web",
        "description": (
            "Search DuckDuckGo and return the top results. "
            "Returns title, URL, and a short snippet per result. "
            "Always prefer this over asking the user to open a browser."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query.",
                },
                "num_results": {
                    "type": "integer",
                    "description": f"Number of results to return (default {DEFAULT_LIMIT}, max 10).",
                },
            },
            "required": ["query"],
        },
    },
]


def _parse_results(html_text: str, limit: int) -> list[dict]:
    """
    Extract search results from DuckDuckGo's HTML response.

    DuckDuckGo HTML results have a predictable structure:
      <a class="result__a" href="...">Title</a>
      <a class="result__snippet">Snippet text…</a>
    """
    results = []

    # Match result blocks
    result_blocks = re.findall(
        r'<div class="result[^"]*"[^>]*>(.*?)</div>\s*</div>',
        html_text,
        re.DOTALL,
    )

    for block in result_blocks:
        if len(results) >= limit:
            break

        # Title + URL
        title_match = re.search(
            r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
            block,
            re.DOTALL,
        )
        # Snippet
        snippet_match = re.search(
            r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
            block,
            re.DOTALL,
        )

        if not title_match:
            continue

        raw_url  = title_match.group(1)
        title    = re.sub(r"<[^>]+>", "", title_match.group(2)).strip()
        snippet  = re.sub(r"<[^>]+>", "", snippet_match.group(1)).strip() if snippet_match else ""

        # DuckDuckGo sometimes wraps URLs in a redirect — extract the real URL
        uddg_match = re.search(r"uddg=([^&]+)", raw_url)
        url = (
            html.unescape(uddg_match.group(1))
            if uddg_match
            else html.unescape(raw_url)
        )

        # Skip ad placeholders
        if not url.startswith("http") or "duckduckgo.com" in url:
            continue

        results.append({
            "title":   html.unescape(title),
            "url":     url,
            "snippet": html.unescape(snippet),
        })

    return results


async def execute(tool_name: str, tool_input: dict, context: dict):
    if tool_name != "search_web":
        return {"error": f"Unknown tool: {tool_name}"}

    query = tool_input.get("query", "").strip()
    if not query:
        return {"error": "query must not be empty"}

    limit = min(int(tool_input.get("num_results", DEFAULT_LIMIT)), 10)

    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
            resp = await client.post(SEARCH_URL, data={"q": query, "b": "", "kl": "us-en"})

        if resp.status_code != 200:
            return {"error": f"DuckDuckGo returned HTTP {resp.status_code}"}

        results = _parse_results(resp.text, limit)

        return {
            "query":   query,
            "count":   len(results),
            "results": results,
        }

    except httpx.TimeoutException:
        return {"error": "Search request timed out"}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}
