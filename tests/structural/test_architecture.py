"""
Structural architecture tests.

Enforce layered architecture invariants via AST analysis — no service
initialization required. These tests catch violations before they spread.

Layer order (lowest to highest):
  core / models / configs  →  services  →  api/routes

Rules enforced:
  1. Routes use service getters only — never bypass into implementation files
  2. Services never import from routes (no upward dependency)
  3. Models and configs stay at the base layer
  4. Service implementation files ≤ 400 LOC
  5. Route files ≤ 200 LOC
  6. No bare print() in src/ — use Loguru
  7. service_manager.py exposes initialize_* and get_* functions
  8. No hardcoded localhost addresses in service files

Known-debt tracking:
  Each test maintains a _KNOWN_* set of existing violations.
  - New violations outside the set → test FAILS (regression guard)
  - Known-debt entry no longer triggers → test FAILS (remove stale entry)
  To pay off debt: fix the violation AND remove it from the _KNOWN_* set.
"""

import ast
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

BACKEND = Path(__file__).parent.parent.parent
SRC = BACKEND / "src"
ROUTES_DIR = SRC / "api" / "routes"
SERVICES_DIR = SRC / "services"
MODELS_DIR = SRC / "models"
CONFIGS_DIR = SRC / "configs"


# ── Helpers ───────────────────────────────────────────────────────────────────


def parse_imports(file: Path) -> list[str]:
    """Return all imported module paths from a Python source file."""
    tree = ast.parse(file.read_text(encoding="utf-8"))
    result: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.append(node.module)
    return result


def count_loc(file: Path) -> int:
    """Count non-empty, non-comment lines."""
    return sum(
        1
        for line in file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    )


def find_print_calls(file: Path) -> list[int]:
    """Return line numbers of bare print() calls."""
    tree = ast.parse(file.read_text(encoding="utf-8"))
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "print"
    ]


def _debt_check(
    actual: set,
    known: set,
    label_new: str,
    label_stale: str,
) -> list[str]:
    """
    Return error strings if actual violations differ from known debt.
    Bidirectional: catches both regressions and stale debt entries.
    """
    errors: list[str] = []
    new = actual - known
    stale = known - actual
    if new:
        errors.append(f"{label_new}:\n" + "\n".join(f"  {v}" for v in sorted(new)))  # type: ignore[arg-type]
    if stale:
        errors.append(
            f"{label_stale} (remove from _KNOWN_* set):\n"
            + "\n".join(f"  {v}" for v in sorted(stale))  # type: ignore[arg-type]
        )
    return errors


# ── Test: Import Layering ─────────────────────────────────────────────────────


class TestImportLayering:
    """Unidirectional import flow must be maintained across layers."""

    # TODO: export WebSocketErrorType from src.services or move error_classifier to src.core
    _KNOWN_ROUTE_BYPASSES: set[tuple[str, str]] = {
        ("websocket.py", "src.services.websocket_service.error_classifier"),
    }

    def test_routes_use_service_getters_not_implementations(self):
        """
        Routes may import from src.services (getters) or src.services.<name> (__init__).
        Routes must NOT reach into src.services.<name>.<impl_file>.

        Why: bypassing getters tightly couples routes to implementation
        details — e.g. swapping a service provider would require route changes.
        """
        actual: set[tuple[str, str]] = set()
        for route_file in ROUTES_DIR.glob("*.py"):
            if route_file.name == "__init__.py":
                continue
            for imp in parse_imports(route_file):
                parts = imp.split(".")
                if len(parts) >= 4 and parts[0] == "src" and parts[1] == "services":
                    actual.add((route_file.name, imp))

        errors = _debt_check(
            actual,
            self._KNOWN_ROUTE_BYPASSES,
            "NEW route-bypasses-getter violations (fix before merging)",
            "Stale known-debt entries",
        )
        assert not errors, "\n\n".join(errors)

    def test_services_never_import_routes(self):
        """
        Services must not import from src.api.* (upward dependency).
        No known debt — this must always be clean.
        """
        violations: list[str] = []
        for py_file in SERVICES_DIR.rglob("*.py"):
            for imp in parse_imports(py_file):
                if imp.startswith("src.api"):
                    rel = py_file.relative_to(SRC)
                    violations.append(f"  {rel}: `{imp}`")
        assert (
            not violations
        ), "Services must not import from API routes:\n" + "\n".join(violations)

    def test_models_stay_at_base_layer(self):
        """
        Model files are data contracts — they must not import from
        services or routes. No known debt — this must always be clean.
        """
        violations: list[str] = []
        for model_file in MODELS_DIR.glob("*.py"):
            for imp in parse_imports(model_file):
                if imp.startswith("src.services") or imp.startswith("src.api"):
                    violations.append(f"  {model_file.name}: `{imp}`")
        assert (
            not violations
        ), "Models must not import from services or routes:\n" + "\n".join(violations)

    def test_configs_stay_at_base_layer(self):
        """
        Config files must not depend on runtime business logic.
        No known debt — this must always be clean.
        """
        violations: list[str] = []
        for config_file in CONFIGS_DIR.rglob("*.py"):
            for imp in parse_imports(config_file):
                if imp.startswith("src.services") or imp.startswith("src.api"):
                    rel = config_file.relative_to(SRC)
                    violations.append(f"  {rel}: `{imp}`")
        assert (
            not violations
        ), "Configs must not import from services or routes:\n" + "\n".join(violations)


# ── Test: File Size Limits ────────────────────────────────────────────────────


class TestFileSizeLimits:
    """Keep files focused. Large files signal mixed responsibilities."""

    _SERVICE_LOC_LIMIT = 400
    _ROUTE_LOC_LIMIT = 200
    _SERVICE_EXEMPT = {"__init__.py", "service_manager.py"}

    # TODO: split processor.py — extract task lifecycle and event handling
    _KNOWN_LARGE_SERVICE_FILES: set[str] = {
        "services/websocket_service/message_processor/processor.py",
    }

    # TODO: extract ltm operations to ltm_service, keep route as thin handler
    _KNOWN_LARGE_ROUTE_FILES: set[str] = {
        "api/routes/ltm.py",
    }

    def test_service_files_within_loc_limit(self):
        """
        Service implementation files must stay under 400 LOC.
        Exempt: service_manager.py (orchestrator), __init__.py (exports).
        """
        actual: set[str] = set()
        for py_file in SERVICES_DIR.rglob("*.py"):
            if py_file.name in self._SERVICE_EXEMPT:
                continue
            if count_loc(py_file) > self._SERVICE_LOC_LIMIT:
                actual.add(str(py_file.relative_to(SRC)))

        errors = _debt_check(
            actual,
            self._KNOWN_LARGE_SERVICE_FILES,
            f"NEW service files over {self._SERVICE_LOC_LIMIT} LOC (split into sub-modules)",
            "Stale known-debt entries (file was refactored — remove from list)",
        )
        assert not errors, "\n\n".join(errors)

    def test_route_files_within_loc_limit(self):
        """
        Route files should be thin — business logic belongs in services.
        """
        actual: set[str] = set()
        for route_file in ROUTES_DIR.glob("*.py"):
            if route_file.name == "__init__.py":
                continue
            if count_loc(route_file) > self._ROUTE_LOC_LIMIT:
                actual.add(str(route_file.relative_to(SRC)))

        errors = _debt_check(
            actual,
            self._KNOWN_LARGE_ROUTE_FILES,
            f"NEW route files over {self._ROUTE_LOC_LIMIT} LOC (move logic to services)",
            "Stale known-debt entries (file was refactored — remove from list)",
        )
        assert not errors, "\n\n".join(errors)


# ── Test: Code Conventions ────────────────────────────────────────────────────


class TestCodeConventions:
    """Enforce conventions that static linters cannot check."""

    # main.py: intentional startup messages — TODO: replace with structured logger
    # service files: debugging artifacts — TODO: replace with logger.debug()
    _KNOWN_PRINT_FILES: set[str] = {
        "main.py",
        "services/agent_service/agent_factory.py",
        "services/agent_service/utils/message_util.py",
        "services/agent_service/utils/text_processor.py",
        "services/ltm_service/ltm_factory.py",
        "services/tts_service/tts_factory.py",
        "services/tts_service/vllm_omni.py",
    }

    # Factory defaults and delegate URLs — TODO: move to YAML config
    _KNOWN_LOCALHOST_FILES: set[str] = {
        "services/tts_service/vllm_omni.py",
        "services/tts_service/tts_factory.py",
        "services/agent_service/agent_factory.py",
        "services/agent_service/tools/delegate/delegate_task.py",
        "services/websocket_service/manager/disconnect_handler.py",
    }

    def test_no_bare_print_in_src(self):
        """
        All logging must go through Loguru (src.core.logger).
        Bare print() bypasses request-ID tracking and log level filtering.
        Fix: `from src.core.logger import logger` → `logger.info(...)`
        """
        actual: set[str] = set()
        for py_file in SRC.rglob("*.py"):
            if find_print_calls(py_file):
                actual.add(str(py_file.relative_to(SRC)))

        errors = _debt_check(
            actual,
            self._KNOWN_PRINT_FILES,
            "NEW files using bare print() (use Loguru logger instead)",
            "Stale known-debt entries (print() removed — update list)",
        )
        assert not errors, "\n\n".join(errors)

    def test_service_manager_exposes_required_interface(self):
        """
        service_manager.py is the single initialization point for all services.
        It must expose initialize_*() and get_*() functions.
        No known debt — this must always be clean.
        """
        manager = SERVICES_DIR / "service_manager.py"
        content = manager.read_text(encoding="utf-8")
        assert (
            "def initialize_" in content or "async def initialize_" in content
        ), "service_manager.py must define initialize_*() functions"
        assert (
            "def get_" in content
        ), "service_manager.py must define get_*() getter functions"

    def test_no_hardcoded_localhost_in_services(self):
        """
        Service files must not hardcode network addresses.
        Use YAML config (yaml_files/) or environment variables instead.
        Checks non-comment source lines only.
        """
        suspicious = ("localhost:", "127.0.0.1:", "0.0.0.0:")
        actual: set[str] = set()
        for py_file in SERVICES_DIR.rglob("*.py"):
            lines = py_file.read_text(encoding="utf-8").splitlines()
            for line in lines:
                stripped = line.strip()
                if (
                    not stripped
                    or stripped.startswith("#")
                    or stripped.startswith('"""')
                    or stripped.startswith("'''")
                ):
                    continue
                if any(p in line for p in suspicious):
                    actual.add(str(py_file.relative_to(SRC)))
                    break

        errors = _debt_check(
            actual,
            self._KNOWN_LOCALHOST_FILES,
            "NEW hardcoded network addresses in services (move to YAML config)",
            "Stale known-debt entries (address moved to config — update list)",
        )
        assert not errors, "\n\n".join(errors)
