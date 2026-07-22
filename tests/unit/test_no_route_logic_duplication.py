"""Guard: REST routes stay thin adapters (no duplicated business logic)."""

import ast
from pathlib import Path

ALLOWED_CALL_NAMES = {
    "to_http_exception",
    "model_dump",
    "Depends",
    "get_flow_service",
    "get_run_service",
    "create",
    "get",
    "list",
    "update",
    "start",
    "status",
    "resume",
}


def _route_module_paths() -> list[Path]:
    root = Path(__file__).resolve().parents[2] / "src" / "navbe" / "api" / "v1" / "routes"
    return [root / "flows.py", root / "runs.py"]


def _call_names_in_body(fn: ast.AsyncFunctionDef | ast.FunctionDef) -> set[str]:
    """Collect call names from the function body only (ignore decorators)."""
    names: set[str] = set()
    for stmt in fn.body:
        for child in ast.walk(stmt):
            if isinstance(child, ast.Call):
                func = child.func
                if isinstance(func, ast.Name):
                    names.add(func.id)
                elif isinstance(func, ast.Attribute):
                    names.add(func.attr)
    return names


def test_flows_and_runs_routes_only_call_service_methods() -> None:
    """Route bodies may only call service methods + error/model helpers."""
    for path in _route_module_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            if node.name.startswith("_") or node.name[0].isupper():
                continue
            # Skip pydantic request models' methods if any.
            if node.name in {"model_post_init"}:
                continue
            calls = _call_names_in_body(node)
            unexpected = {
                name
                for name in calls
                if name not in ALLOWED_CALL_NAMES
                and not name.endswith("Error")
                and name
                not in {
                    "dict",
                    "list",
                    "str",
                    "HTTPException",
                    "APIRouter",
                    "BaseModel",
                }
            }
            # Attribute calls like service.create are already covered by attr names.
            assert not unexpected, f"{path.name}::{node.name} has unexpected calls: {unexpected}"
