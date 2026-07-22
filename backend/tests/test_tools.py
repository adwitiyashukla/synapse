"""Tool unit tests, with emphasis on calculator safety."""

import json

import pytest

from app.agent.tools import calculator, datetime_tool


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("2 + 2", "4"),
        ("6 * 7", "42"),
        ("2 ** 10", "1024"),
        ("sqrt(144)", "12"),
        ("round(pi, 2)", "3.14"),
        ("factorial(5)", "120"),
        ("(3 + 4) * -2", "-14"),
        ("10 / 4", "2.5"),
        ("min(3, 1, 2)", "1"),
    ],
)
async def test_calculator_valid(expression: str, expected: str) -> None:
    assert await calculator.run(expression) == expected


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('ls')",
        "open('/etc/passwd')",
        "().__class__.__bases__",
        "exec('print(1)')",
        "lambda: 1",
        "[x for x in range(10)]",
        "'a' * 100",
        "x = 5",
        "10 / 0",
        "2 ** 999999",
    ],
)
async def test_calculator_rejects_unsafe(expression: str) -> None:
    result = await calculator.run(expression)
    assert result.startswith("Error")


async def test_datetime_tool() -> None:
    payload = json.loads(await datetime_tool.run("Asia/Kolkata"))
    assert payload["timezone"] == "Asia/Kolkata"
    assert "iso" in payload and "date" in payload


async def test_datetime_tool_bad_timezone() -> None:
    payload = json.loads(await datetime_tool.run("Not/AZone"))
    assert "error" in payload
