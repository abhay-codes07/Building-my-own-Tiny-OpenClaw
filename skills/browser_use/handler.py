"""
browser_use skill — Playwright-driven web browser.

Browser and page instances are reused across tool calls within one
process to avoid the overhead of launching Chromium on every request.
"""

from playwright.async_api import async_playwright

# Module-level browser state — created on first use, reused after
_playwright = None
_browser    = None
_page       = None

CONTENT_LIMIT = 4000  # chars; keeps responses inside LLM context windows


async def _get_page():
    global _playwright, _browser, _page

    if _browser and _page:
        return _page

    _playwright = await async_playwright().start()
    _browser    = await _playwright.chromium.launch(headless=True)
    _page       = await _browser.new_page()

    # Block common ad/tracker domains to speed up page loads
    await _page.route(
        "**/{ads,analytics,tracking,pixel}/**",
        lambda route: route.abort(),
    )
    return _page


tools = [
    {
        "name": "browse_url",
        "description": (
            "Navigate to a URL and return the page title and visible text. "
            "Use for reading articles, documentation, or any public web page."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Full URL to visit (https://…)"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "click_element",
        "description": "Click an element on the current page using a CSS selector or visible text.",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector (e.g. 'button.submit') or text match (e.g. 'text=Sign In')",
                },
            },
            "required": ["selector"],
        },
    },
    {
        "name": "fill_input",
        "description": "Type text into a form field on the current page.",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector for the input element"},
                "text":     {"type": "string", "description": "Text to type into the field"},
            },
            "required": ["selector", "text"],
        },
    },
    {
        "name": "get_page_content",
        "description": "Return the visible text of the current page or a specific element.",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "Optional CSS selector. Omit to get full page body text.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_page_links",
        "description": "Return all hyperlinks found on the current page.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max number of links to return (default 20).",
                },
            },
            "required": [],
        },
    },
]


async def execute(tool_name: str, tool_input: dict, context: dict):
    try:
        page = await _get_page()

        if tool_name == "browse_url":
            url = tool_input["url"]
            if not url.startswith("http"):
                url = "https://" + url

            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            title = await page.title()
            text  = await page.inner_text("body")
            return {
                "title":           title,
                "url":             page.url,
                "content_preview": text.strip()[:CONTENT_LIMIT],
            }

        if tool_name == "click_element":
            await page.click(tool_input["selector"], timeout=5000)
            await page.wait_for_load_state("domcontentloaded")
            return {
                "clicked":   tool_input["selector"],
                "new_url":   page.url,
                "new_title": await page.title(),
            }

        if tool_name == "fill_input":
            await page.fill(tool_input["selector"], tool_input["text"])
            return {"filled": tool_input["selector"], "text": tool_input["text"]}

        if tool_name == "get_page_content":
            selector = tool_input.get("selector") or "body"
            text     = await page.inner_text(selector)
            return {"url": page.url, "content": text.strip()[:CONTENT_LIMIT]}

        if tool_name == "get_page_links":
            limit = int(tool_input.get("limit", 20))
            links = await page.evaluate(
                """(limit) => {
                    const anchors = Array.from(document.querySelectorAll('a[href]'));
                    return anchors.slice(0, limit).map(a => ({
                        text: a.innerText.trim().slice(0, 80),
                        href: a.href,
                    }));
                }""",
                limit,
            )
            return {"url": page.url, "links": links}

        return {"error": f"Unknown tool: {tool_name}"}

    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}
