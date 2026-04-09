"""
calculator skill — safe mathematical expression evaluator.

Uses Python's ast module to parse and evaluate expressions without
calling eval() on arbitrary code, preventing code injection.

Supported operations: +, -, *, /, //, %, ** and math functions
(sqrt, log, sin, cos, tan, abs, round, floor, ceil, pi, e, tau).
"""

import ast
import math
import operator

# Whitelist of allowed binary operators
_OPERATORS = {
    ast.Add:  operator.add,
    ast.Sub:  operator.sub,
    ast.Mult: operator.mul,
    ast.Div:  operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod:  operator.mod,
    ast.Pow:  operator.pow,
}

# Whitelist of allowed unary operators
_UNARY_OPERATORS = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# Whitelisted math functions and constants
_SAFE_NAMES: dict = {
    "sqrt":  math.sqrt,
    "log":   math.log,
    "log10": math.log10,
    "log2":  math.log2,
    "sin":   math.sin,
    "cos":   math.cos,
    "tan":   math.tan,
    "asin":  math.asin,
    "acos":  math.acos,
    "atan":  math.atan,
    "abs":   abs,
    "round": round,
    "floor": math.floor,
    "ceil":  math.ceil,
    "pi":    math.pi,
    "e":     math.e,
    "tau":   math.tau,
    "inf":   math.inf,
}


def _eval_node(node):
    """Recursively evaluate a whitelisted AST node."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value

    if isinstance(node, ast.Name):
        if node.id in _SAFE_NAMES:
            return _SAFE_NAMES[node.id]
        raise ValueError(f"Name not allowed: {node.id!r}")

    if isinstance(node, ast.BinOp):
        op = _OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError(f"Operator not allowed: {type(node.op).__name__}")
        left  = _eval_node(node.left)
        right = _eval_node(node.right)
        return op(left, right)

    if isinstance(node, ast.UnaryOp):
        op = _UNARY_OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unary operator not allowed: {type(node.op).__name__}")
        return op(_eval_node(node.operand))

    if isinstance(node, ast.Call):
        func = _eval_node(node.func)
        if not callable(func):
            raise ValueError("Tried to call a non-function")
        args = [_eval_node(a) for a in node.args]
        return func(*args)

    raise ValueError(f"Expression type not allowed: {type(node).__name__}")


def _safe_eval(expression: str) -> float:
    tree = ast.parse(expression.strip(), mode="eval")
    return _eval_node(tree.body)


tools = [
    {
        "name": "calculate",
        "description": (
            "Evaluate a mathematical expression and return the result. "
            "Supports +, -, *, /, //, %, ** and functions: "
            "sqrt, log, log10, log2, sin, cos, tan, abs, round, floor, ceil. "
            "Constants: pi, e, tau."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "The math expression to evaluate, e.g. '2 ** 10' or 'sqrt(144)'",
                },
            },
            "required": ["expression"],
        },
    },
]


async def execute(tool_name: str, tool_input: dict, context: dict):
    if tool_name != "calculate":
        return {"error": f"Unknown tool: {tool_name}"}

    expression = tool_input.get("expression", "").strip()
    if not expression:
        return {"error": "expression must not be empty"}

    try:
        result = _safe_eval(expression)
        # Round floating-point noise (e.g. 0.30000000000000004 → 0.3)
        if isinstance(result, float) and not math.isfinite(result):
            return {"expression": expression, "result": str(result)}
        rounded = round(result, 10)
        # Return int if the result is a whole number
        display = int(rounded) if rounded == int(rounded) else rounded
        return {"expression": expression, "result": display}

    except ZeroDivisionError:
        return {"error": "Division by zero"}
    except (ValueError, TypeError) as exc:
        return {"error": f"Invalid expression: {exc}"}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Calculation failed: {exc}"}
