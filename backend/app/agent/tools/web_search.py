import asyncio
import json
import logging

logger = logging.getLogger("synapse.tools.web_search")

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS


def _search_sync(query: str, max_results: int) -> list[dict[str, str]]:
    with DDGS() as ddgs:
        results = ddgs.text(query, max_results=max_results)
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            }
            for r in results or []
        ]


async def run(query: str, max_results: int = 5) -> str:
    max_results = max(1, min(int(max_results or 5), 10))
    try:
        results = await asyncio.wait_for(
            asyncio.to_thread(_search_sync, query, max_results), timeout=20
        )
    except asyncio.TimeoutError:
        return json.dumps({"error": "Web search timed out. Try again."})
    except Exception as exc:
        logger.warning("web search failed: %s", exc)
        return json.dumps({"error": f"Web search failed: {exc}"})
    if not results:
        return json.dumps({"results": [], "note": "No results found."})
    return json.dumps({"results": results}, ensure_ascii=False)
