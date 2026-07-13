"""Dependency audit script — run with `uv run python tests/_audit_deps.py`."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

SRC = Path("src/apoch")


def get_imports(filepath: Path) -> set[str]:
    tree = ast.parse(filepath.read_text())
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


def get_deep_imports(filepath: Path) -> list[tuple[str, str]]:
    """Return (module, name) for all imports in file."""
    tree = ast.parse(filepath.read_text())
    result: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                result.append(("import", alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for alias in node.names:
                    result.append((node.module, alias.name))
    return result


passed = 0
failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name}")
        if detail:
            for line in detail.strip().split("\n"):
                print(f"     {line}")


# ------------------------------------------------------------------
# 1. Core never imports adapters
# ------------------------------------------------------------------
print("=" * 60)
print("1. Core never imports adapters")
print("=" * 60)

errors: list[str] = []
for pyfile in sorted((SRC / "core").rglob("*.py")):
    rel = pyfile.relative_to(SRC)
    for mod, name in get_deep_imports(pyfile):
        if "adapter" in mod.lower() or "adapter" in name.lower():
            errors.append(f"{rel}: {mod}.{name}")

check("Core → adapters prohibited imports", not errors, "\n".join(errors))

# ------------------------------------------------------------------
# 2. Adapters never import CLI
# ------------------------------------------------------------------
print()
print("=" * 60)
print("2. Adapters never import CLI")
print("=" * 60)

errors.clear()
for pyfile in sorted((SRC / "adapters").rglob("*.py")):
    rel = pyfile.relative_to(SRC)
    for mod, name in get_deep_imports(pyfile):
        full = f"{mod}.{name}" if name else mod
        if "cli" in full.split("."):
            errors.append(f"{rel}: {full}")

check("Adapters → CLI prohibited imports", not errors, "\n".join(errors))

# ------------------------------------------------------------------
# 3. CLI never imports OpenCodeConfig directly
# ------------------------------------------------------------------
print()
print("=" * 60)
print("3. CLI never imports OpenCodeConfig directly")
print("=" * 60)

errors.clear()
for pyfile in sorted((SRC / "cli").rglob("*.py")):
    rel = pyfile.relative_to(SRC)
    content = pyfile.read_text()
    tree = ast.parse(content)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "opencode.config" in alias.name or alias.name == "OpenCodeConfig":
                    errors.append(f"{rel}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and "opencode.config" in node.module:
                errors.append(f"{rel}: from {node.module} import ...")
            for alias in node.names:
                if alias.name == "OpenCodeConfig":
                    errors.append(f"{rel}: imports OpenCodeConfig")

check("CLI → OpenCodeConfig prohibited import", not errors, "\n".join(errors))

# ------------------------------------------------------------------
# 4. FastMCP exists only inside adapters/opencode/
# ------------------------------------------------------------------
print()
print("=" * 60)
print("4. FastMCP only inside adapters/opencode/")
print("=" * 60)

errors.clear()
for pyfile in sorted(SRC.rglob("*.py")):
    rel = pyfile.relative_to(SRC)
    content = pyfile.read_text()
    tree = ast.parse(content)
    has_mcp_import = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "mcp" in alias.name:
                    has_mcp_import = True
        elif isinstance(node, ast.ImportFrom):
            if node.module and "mcp" in node.module:
                has_mcp_import = True
    if has_mcp_import and "adapters/opencode" not in str(rel):
        errors.append(f"{rel}: imports mcp")

check("FastMCP confined to adapters/opencode/", not errors, "\n".join(errors))

# ------------------------------------------------------------------
# 5. OpenCodeConfig is the only opencode.json I/O
# ------------------------------------------------------------------
print()
print("=" * 60)
print("5. opencode.json I/O properly confined")
print("=" * 60)

errors.clear()
for pyfile in sorted(SRC.rglob("*.py")):
    rel = pyfile.relative_to(SRC)
    if str(rel).startswith(
        ("adapters/opencode/", "tests/", "cli/install.py", "cli/uninstall.py", "core/exceptions.py")
    ):
        continue  # Authorized locations
    content = pyfile.read_text()
    if "opencode.json" in content:
        errors.append(f"{rel}: references opencode.json outside adapters/opencode/")

# Verify install/uninstall don't import OpenCodeConfig
for fname in ("cli/install.py", "cli/uninstall.py"):
    content = (SRC / fname).read_text()
    tree = ast.parse(content)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and "opencode.config" in node.module:
                errors.append(f"{fname}: imports OpenCodeConfig")
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "opencode.config" in alias.name or "OpenCodeConfig" in alias.name:
                    errors.append(f"{fname}: imports OpenCodeConfig")

check("opencode.json I/O confined", not errors, "\n".join(errors))

# ------------------------------------------------------------------
# 6. No direct adapter class imports outside adapters/ + registry
# ------------------------------------------------------------------
print()
print("=" * 60)
print("6. Registry is the ONLY adapter resolution point")
print("=" * 60)

errors.clear()
for pyfile in sorted(SRC.rglob("*.py")):
    rel = pyfile.relative_to(SRC)
    if str(rel) in (
        "adapters/registry.py",
        "adapters/__init__.py",
        "adapters/opencode/__init__.py",
    ):
        continue
    content = pyfile.read_text()
    tree = ast.parse(content)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and "opencode.server" in node.module:
                for alias in node.names:
                    errors.append(f"{rel}: imports {alias.name} from {node.module}")

check("No direct imports from opencode.server outside allowed files", not errors, "\n".join(errors))

# ------------------------------------------------------------------
# 7. No circular imports (import apoch works)
# ------------------------------------------------------------------
print()
print("=" * 60)
print("7. No circular imports")
print("=" * 60)

result = subprocess.run(
    [sys.executable, "-c", "import apoch; print('OK')"],
    capture_output=True,
    text=True,
    timeout=30,
)
check("Package import succeeds", result.returncode == 0, result.stderr)

# ------------------------------------------------------------------
# 8. Constructor Injection
# ------------------------------------------------------------------
print()
print("=" * 60)
print("8. Constructor Injection intact")
print("=" * 60)

errors.clear()
for pyfile in sorted(SRC.rglob("*.py")):
    rel = pyfile.relative_to(SRC)
    content = pyfile.read_text()
    tree = ast.parse(content)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                    params = [arg.arg for arg in item.args.args if arg.arg != "self"]
                    names = (
                        "Engine",
                        "ModuleRegistry",
                        "Module",
                        "OpenCodeConfig",
                        "OpenCodeAdapter",
                        "AgentAdapter",
                    )
                    if node.name in names:
                        if not params:
                            errors.append(f"{rel}: {node.name}.__init__ has no parameters")
                        else:
                            print(f"     ✓ {rel}: {node.name}({', '.join(params)})")

check("All key classes have constructor params", not errors, "\n".join(errors))

# ------------------------------------------------------------------
# 9. No singletons
# ------------------------------------------------------------------
print()
print("=" * 60)
print("9. No singleton pattern")
print("=" * 60)

patterns = ["_instance", "_singleton", "instance = None"]
errors.clear()
for pyfile in sorted(SRC.rglob("*.py")):
    rel = pyfile.relative_to(SRC)
    content = pyfile.read_text()
    for line in content.splitlines():
        for pat in patterns:
            if pat in line and not line.strip().startswith("#"):
                errors.append(f"{rel}: {line.strip()}")

check("No singleton patterns", not errors, "\n".join(errors[:10]) if errors else "")
if errors and len(errors) > 10:
    print(f"     ... and {len(errors) - 10} more")

# ------------------------------------------------------------------
# 10. CLI no business logic (commands are 1-3 lines)
# ------------------------------------------------------------------
print()
print("=" * 60)
print("10. CLI commands are thin")
print("=" * 60)

for pyfile in sorted((SRC / "cli").rglob("*.py")):
    if pyfile.name in ("__init__.py", "app.py", "output.py"):
        continue
    rel = pyfile.relative_to(SRC)
    content = pyfile.read_text()
    tree = ast.parse(content)
    command_count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Count in the function body excluding decorators, docstring
            skip_types = (ast.Expr, ast.Import, ast.ImportFrom)
            body = [s for s in node.body if not isinstance(s, skip_types)]
            if len(body) <= 5:  # thin command
                command_count += 1
                print(f"     ✓ {rel}.{node.name}: {len(body)} statements")

print()
print("=" * 60)
print(f"RESULT: {passed} passed, {failed} failed")
print("=" * 60)
sys.exit(1 if failed > 0 else 0)
