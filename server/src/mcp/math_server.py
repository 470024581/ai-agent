"""
Math MCP Service (FastMCP over stdio)

Run with:
  python -m src.mcp.math_server

This exposes simple math tools over MCP stdio transport so that
MultiServerMCPClient can launch it via {"command": "python", "args": [path], "transport": "stdio"}.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from typing import Union
import ast
import operator as op


mcp = FastMCP("Math")


@mcp.tool()
async def add(a: float, b: float) -> float:
    """Add two numbers and return the result."""
    return float(a) + float(b)


@mcp.tool()
async def sub(a: float, b: float) -> float:
    """Subtract b from a and return the result."""
    return float(a) - float(b)


@mcp.tool()
async def mul(a: float, b: float) -> float:
    """Multiply two numbers and return the result."""
    return float(a) * float(b)


@mcp.tool()
async def div(a: float, b: float) -> Union[float, dict]:
    """Divide a by b. Returns error dict if b is zero."""
    if float(b) == 0.0:
        return {"error": "Division by zero"}
    return float(a) / float(b)


# Safe expression evaluator for basic arithmetic
_ALLOWED_BINOPS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
    ast.Mod: op.mod,
}
_ALLOWED_UNARY = {
    ast.UAdd: op.pos,
    ast.USub: op.neg,
}


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARY:
        return _ALLOWED_UNARY[type(node.op)](_eval_node(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, ast.Div) and right == 0.0:
            raise ZeroDivisionError("division by zero")
        return _ALLOWED_BINOPS[type(node.op)](left, right)
    raise ValueError("Unsupported expression")


@mcp.tool()
async def calc(expression: str) -> Union[float, dict]:
    """Safely evaluate a basic arithmetic expression (e.g., "(3 + 5) * 12")."""
    try:
        tree = ast.parse(expression, mode="eval")
        result = _eval_node(tree)
        return float(result)
    except ZeroDivisionError:
        return {"error": "Division by zero"}
    except Exception as e:
        return {"error": f"Invalid expression: {str(e)}"}


if __name__ == "__main__":
    # FastMCP manages its own event loop in stdio mode
    mcp.run(transport="stdio")


