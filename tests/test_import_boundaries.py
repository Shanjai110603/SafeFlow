"""Tests enforcing strict architectural import boundaries via AST analysis.

Boundary Rules:
1. safeflow.core must NEVER import from safeflow.plugins or safeflow.adapters.
2. safeflow.plugins may only import from safeflow.core (public API/schema) and external libraries.
3. safeflow.plugins must NEVER import from each other (e.g. plugin A importing plugin B).
4. safeflow.adapters may only import from safeflow.core.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SAFEFLOW_ROOT = REPO_ROOT / "safeflow"


def get_imports_from_file(file_path: Path) -> list[str]:
    """Parse a python file with AST and return all imported module paths."""
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    imported_modules: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.append(node.module)

    return imported_modules


def test_core_does_not_import_plugins_or_adapters():
    """Verify safeflow.core has zero imports from plugins or adapters."""
    core_dir = SAFEFLOW_ROOT / "core"
    assert core_dir.exists()

    violations = []
    for py_file in core_dir.rglob("*.py"):
        imports = get_imports_from_file(py_file)
        for imp in imports:
            if imp.startswith("safeflow.plugins") or imp.startswith("safeflow.adapters"):
                violations.append(f"{py_file.relative_to(REPO_ROOT)} imports forbidden: {imp}")

    assert not violations, f"Core import boundary violations detected:\n" + "\n".join(violations)


def test_plugins_do_not_import_each_other():
    """Verify that plugins only import safeflow.core and never sibling plugins."""
    plugins_dir = SAFEFLOW_ROOT / "plugins"
    assert plugins_dir.exists()

    plugin_packages = [
        p.name for p in plugins_dir.iterdir()
        if p.is_dir() and (p / "__init__.py").exists()
    ]

    violations = []
    for plugin_name in plugin_packages:
        current_plugin_dir = plugins_dir / plugin_name
        for py_file in current_plugin_dir.rglob("*.py"):
            imports = get_imports_from_file(py_file)
            for imp in imports:
                for other_plugin in plugin_packages:
                    if other_plugin != plugin_name:
                        if imp == f"safeflow.plugins.{other_plugin}" or imp.startswith(f"safeflow.plugins.{other_plugin}."):
                            violations.append(
                                f"{py_file.relative_to(REPO_ROOT)} illegally imports sibling plugin: {imp}"
                            )

    assert not violations, f"Cross-plugin import boundary violations detected:\n" + "\n".join(violations)


def test_adapters_do_not_import_plugins():
    """Verify that adapters do not import plugins."""
    adapters_dir = SAFEFLOW_ROOT / "adapters"
    assert adapters_dir.exists()

    violations = []
    for py_file in adapters_dir.rglob("*.py"):
        imports = get_imports_from_file(py_file)
        for imp in imports:
            if imp.startswith("safeflow.plugins"):
                violations.append(f"{py_file.relative_to(REPO_ROOT)} imports forbidden: {imp}")

    assert not violations, f"Adapter import boundary violations detected:\n" + "\n".join(violations)
