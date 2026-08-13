import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools import calculator, datetime_tool, rag_search, weather, web_search

logger = logging.getLogger("synapse.agent.toolkit")

TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "web_search": {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web for current information, news, facts, or anything "
                "outside your training data. Returns titles, URLs and snippets."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"},
                    "max_results": {
                        "type": "integer",
                        "description": "Number of results (1-10), default 5",
                    },
                },
                "required": ["query"],
            },
        },
    },
    "get_weather": {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather and a 3-day forecast for a city or place.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City or place name, e.g. 'Patiala' or 'New York'",
                    }
                },
                "required": ["location"],
            },
        },
    },
    "calculator": {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": (
                "Evaluate a mathematical expression precisely. Supports arithmetic, "
                "powers, sqrt, log, trigonometry, factorial and constants pi and e."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Expression such as 'sqrt(2) * (3 + 4)**2'",
                    }
                },
                "required": ["expression"],
            },
        },
    },
    "get_current_datetime": {
        "type": "function",
        "function": {
            "name": "get_current_datetime",
            "description": "Get the current date and time, optionally in a specific IANA timezone.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "IANA timezone like 'Asia/Kolkata'. Defaults to UTC.",
                    }
                },
                "required": [],
            },
        },
    },
    "search_documents": {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": (
                "Search the user's uploaded documents (their private knowledge base) "
                "for passages relevant to a query. Always use this when the user asks "
                "about their files or uploaded content."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to look for"}
                },
                "required": ["query"],
            },
        },
    },
}


def build_tool_schemas(include_documents: bool) -> list[dict[str, Any]]:
    names = ["web_search", "get_weather", "calculator", "get_current_datetime"]
    if include_documents:
        names.append("search_documents")
    return [TOOL_SCHEMAS[name] for name in names]


async def dispatch(
    name: str, raw_arguments: str, db: AsyncSession, user_id: int
) -> str:
    try:
        args = json.loads(raw_arguments) if raw_arguments else {}
        if not isinstance(args, dict):
            args = {}
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid tool arguments (not valid JSON)."})

    try:
        if name == "web_search":
            return await web_search.run(
                str(args.get("query", "")), int(args.get("max_results", 5) or 5)
            )
        if name == "get_weather":
            return await weather.run(str(args.get("location", "")))
        if name == "calculator":
            return await calculator.run(str(args.get("expression", "")))
        if name == "get_current_datetime":
            return await datetime_tool.run(str(args.get("timezone", "UTC") or "UTC"))
        if name == "search_documents":
            return await rag_search.run(db, user_id, str(args.get("query", "")))
        return json.dumps({"error": f"Unknown tool: {name}"})
    except Exception as exc:
        logger.exception("tool %s failed", name)
        return json.dumps({"error": f"Tool {name} failed: {exc}"})
