"""
Unit tests for the calculator skill's safe evaluator.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from skills.calculator.handler import _safe_eval, execute


class TestSafeEval:
    def test_basic_arithmetic(self):
        assert _safe_eval("2 + 3") == 5
        assert _safe_eval("10 - 4") == 6
        assert _safe_eval("3 * 7") == 21
        assert _safe_eval("10 / 4") == 2.5
        assert _safe_eval("10 // 3") == 3
        assert _safe_eval("10 % 3") == 1

    def test_power(self):
        assert _safe_eval("2 ** 10") == 1024

    def test_math_functions(self):
        import math
        assert _safe_eval("sqrt(144)") == 12.0
        assert abs(_safe_eval("sin(0)")) < 1e-10
        assert abs(_safe_eval("cos(0)") - 1.0) < 1e-10

    def test_constants(self):
        import math
        assert abs(_safe_eval("pi") - math.pi) < 1e-10
        assert abs(_safe_eval("e") - math.e) < 1e-10

    def test_nested_expression(self):
        result = _safe_eval("round(sqrt(2), 4)")
        assert result == round(2 ** 0.5, 4)

    def test_disallows_import(self):
        with pytest.raises(Exception):
            _safe_eval("__import__('os')")

    def test_disallows_string_literal(self):
        with pytest.raises(Exception):
            _safe_eval("'hello'")

    def test_zero_division_is_caught(self):
        with pytest.raises(ZeroDivisionError):
            _safe_eval("1 / 0")


@pytest.mark.asyncio
class TestExecute:
    async def test_returns_int_for_whole_numbers(self):
        result = await execute("calculate", {"expression": "4 * 4"}, {})
        assert result["result"] == 16
        assert isinstance(result["result"], int)

    async def test_returns_float_for_decimals(self):
        result = await execute("calculate", {"expression": "1 / 3"}, {})
        assert isinstance(result["result"], float)

    async def test_empty_expression_returns_error(self):
        result = await execute("calculate", {"expression": ""}, {})
        assert "error" in result

    async def test_unknown_tool_returns_error(self):
        result = await execute("not_a_tool", {}, {})
        assert "error" in result
