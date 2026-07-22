"""Safe mathematical expression evaluator.

Parses the expression into an AST and walks a strict whitelist of node
types, so nothing except arithmetic can execute. Never uses eval().
"""

import ast
import math
import operator
from typing import Any

_BINARY_OPS: dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS: dict[type, Any] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_FUNCTIONS: dict[str, Any] = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sqrt": math.sqrt,
    "log": math.log,
    "log2": math.log2,
    "log10": math.log10,
    "exp": math.exp,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "degrees": math.degrees,
    "radians": math.radians,
    "floor": math.floor,
    "ceil": math.ceil,
    "factorial": math.factorial,
}

_CONSTANTS: dict[str, float] = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
    "inf": math.inf,
}

MAX_POWER = 10_000
MAX_FACTORIAL = 5_000


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise ValueError("Only numeric constants are allowed")
    if isinstance(node, ast.Name):
        if node.id in _CONSTANTS:
            return _CONSTANTS[node.id]
        raise ValueError(f"Unknown identifier: {node.id}")
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _BINARY_OPS:
            raise ValueError(f"Operator not allowed: {op_type.__name__}")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if op_type is ast.Pow and abs(right) > MAX_POWER:
            raise ValueError("Exponent too large")
        return _BINARY_OPS[op_type](left, right)
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _UNARY_OPS:
            raise ValueError(f"Operator not allowed: {op_type.__name__}")
        return _UNARY_OPS[op_type](_eval_node(node.operand))
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCTIONS:
            raise ValueError("Only whitelisted math functions are allowed")
        if node.keywords:
            raise ValueError("Keyword arguments are not allowed")
        args = [_eval_node(arg) for arg in node.args]
        if node.func.id == "factorial" and (args and args[0] > MAX_FACTORIAL):
            raise ValueError("Factorial argument too large")
        return _FUNCTIONS[node.func.id](*args)
    raise ValueError(f"Expression element not allowed: {type(node).__name__}")


def evaluate(expression: str) -> str:
    """Evaluate a math expression and return the result as a string."""
    expression = expression.strip()
    if len(expression) > 500:
        return "Error: expression too long"
    try:
        tree = ast.parse(expression, mode="eval")
        result = _eval_node(tree)
    except ZeroDivisionError:
        return "Error: division by zero"
    except (ValueError, SyntaxError, OverflowError, TypeError) as exc:
        return f"Error: {exc}"
    if isinstance(result, float) and result.is_integer() and abs(result) < 1e15:
        return str(int(result))
    return str(result)


async def run(expression: str) -> str:
    return evaluate(expression)
