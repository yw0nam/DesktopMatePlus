"""
Structural tests for DevEx files.

Verify that Makefile, Dockerfile, and docker-compose.yml exist and contain
the required targets/directives/services. These tests are intentionally
lightweight — they validate presence and structure, not Docker build correctness.
"""

from pathlib import Path

import yaml

BACKEND = Path(__file__).parent.parent.parent

MAKEFILE = BACKEND / "Makefile"
DOCKERFILE = BACKEND / "Dockerfile"
COMPOSE = BACKEND / "docker-compose.yml"

REQUIRED_MAKEFILE_TARGETS = {"lint", "test", "e2e", "run", "fmt", "clean"}
REQUIRED_COMPOSE_SERVICES = {"backend", "mongo", "qdrant", "neo4j"}


class TestMakefile:
    """Makefile must exist and expose required targets."""

    def test_makefile_exists(self):
        assert MAKEFILE.exists(), "Makefile not found in backend root"

    def test_required_targets_present(self):
        content = MAKEFILE.read_text(encoding="utf-8")
        missing = {t for t in REQUIRED_MAKEFILE_TARGETS if f"{t}:" not in content}
        assert not missing, f"Missing Makefile targets: {sorted(missing)}"

    def test_phony_declared(self):
        content = MAKEFILE.read_text(encoding="utf-8")
        assert ".PHONY" in content, "Makefile must declare .PHONY targets"


class TestDockerfile:
    """Dockerfile must exist and contain required directives."""

    def test_dockerfile_exists(self):
        assert DOCKERFILE.exists(), "Dockerfile not found in backend root"

    def test_has_from_directive(self):
        content = DOCKERFILE.read_text(encoding="utf-8")
        assert any(
            line.startswith("FROM") for line in content.splitlines()
        ), "Dockerfile must have a FROM directive"

    def test_has_expose_directive(self):
        content = DOCKERFILE.read_text(encoding="utf-8")
        assert "EXPOSE" in content, "Dockerfile must have an EXPOSE directive"

    def test_has_cmd_directive(self):
        content = DOCKERFILE.read_text(encoding="utf-8")
        assert "CMD" in content, "Dockerfile must have a CMD directive"

    def test_exposes_port_5500(self):
        content = DOCKERFILE.read_text(encoding="utf-8")
        assert "5500" in content, "Dockerfile must expose port 5500"


class TestDockerCompose:
    """docker-compose.yml must exist and define required services."""

    def test_compose_exists(self):
        assert COMPOSE.exists(), "docker-compose.yml not found in backend root"

    def test_compose_is_valid_yaml(self):
        content = COMPOSE.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        assert isinstance(
            parsed, dict
        ), "docker-compose.yml must be a valid YAML mapping"

    def test_required_services_present(self):
        content = COMPOSE.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        services = set(parsed.get("services", {}).keys())
        missing = REQUIRED_COMPOSE_SERVICES - services
        assert not missing, f"Missing docker-compose services: {sorted(missing)}"

    def test_backend_has_build(self):
        content = COMPOSE.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        backend = parsed["services"]["backend"]
        assert "build" in backend, "backend service must have a build directive"

    def test_backend_depends_on_mongo_and_qdrant(self):
        content = COMPOSE.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        backend = parsed["services"]["backend"]
        depends = backend.get("depends_on", {})
        deps = set(depends.keys()) if isinstance(depends, dict) else set(depends)
        assert {"mongo", "qdrant"}.issubset(
            deps
        ), "backend service must depend on mongo and qdrant"

    def test_volumes_defined_for_mongo_and_qdrant(self):
        content = COMPOSE.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        volumes = set(parsed.get("volumes", {}).keys())
        assert "mongo_data" in volumes, "mongo_data volume must be defined"
        assert "qdrant_data" in volumes, "qdrant_data volume must be defined"
