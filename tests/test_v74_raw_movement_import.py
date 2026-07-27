from __future__ import annotations

import ast
from pathlib import Path


def test_raw_movement_service_function_exists():
    service = Path("app/services/report_service.py").read_text(encoding="utf-8")
    tree = ast.parse(service)
    functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "generate_raw_movement_export" in functions
    assert "create_raw_movement_export" in service


def test_raw_movement_module_exists():
    path = Path("app/reports/raw_movement_export.py")
    assert path.exists()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "create_raw_movement_export" in functions
