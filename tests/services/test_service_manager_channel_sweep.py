"""Tests for initialize_channel_service and initialize_sweep_service in service_manager."""

from pathlib import Path
from unittest.mock import MagicMock

import yaml

from src.services.channel_service.slack_service import SlackSettings
from src.services.task_sweep_service.sweep import BackgroundSweepService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_channel_yaml(
    tmp_path: Path,
    *,
    enabled: bool = True,
    bot_token: str = "",
    signing_secret: str = "",
) -> Path:
    p = tmp_path / "channel.yml"
    p.write_text(
        yaml.dump(
            {
                "slack": {
                    "enabled": enabled,
                    "bot_token": bot_token,
                    "signing_secret": signing_secret,
                }
            }
        )
    )
    return p


def _write_sweep_yaml(tmp_path: Path, *, interval: int = 30, ttl: int = 120) -> Path:
    p = tmp_path / "sweep.yml"
    p.write_text(
        yaml.dump(
            {
                "sweep_config": {
                    "sweep_interval_seconds": interval,
                    "task_ttl_seconds": ttl,
                }
            }
        )
    )
    return p


# ---------------------------------------------------------------------------
# initialize_channel_service tests
# ---------------------------------------------------------------------------


class TestInitializeChannelService:
    def test_returns_slack_settings_with_yaml_values(self, tmp_path):
        """initialize_channel_service reads slack config from YAML and returns SlackSettings."""
        config_path = _write_channel_yaml(
            tmp_path, enabled=True, bot_token="xoxb-test", signing_secret="sec"
        )

        from src.services.service_manager import initialize_channel_service

        settings = initialize_channel_service(config_path=config_path)

        assert isinstance(settings, SlackSettings)
        assert settings.bot_token == "xoxb-test"
        assert settings.signing_secret == "sec"
        assert settings.enabled is True

    def test_returns_default_slack_settings_when_no_config_path(self, tmp_path):
        """initialize_channel_service with no config_path falls back to defaults."""
        default_yaml = tmp_path / "channel.yml"
        default_yaml.write_text(yaml.dump({"slack": {"enabled": False}}))

        from src.services.service_manager import initialize_channel_service

        # Patch _BASE_YAML to point to tmp directory that mirrors expected structure
        services_dir = tmp_path / "services" / "channel_service"
        services_dir.mkdir(parents=True)
        (services_dir / "channel.yml").write_text(
            yaml.dump({"slack": {"enabled": False}})
        )

        import src.services.service_manager as sm

        original = sm._BASE_YAML
        sm._BASE_YAML = tmp_path
        try:
            settings = initialize_channel_service()
            assert isinstance(settings, SlackSettings)
            assert settings.enabled is False
        finally:
            sm._BASE_YAML = original

    def test_env_var_fallback_for_bot_token(self, tmp_path, monkeypatch):
        """When bot_token is empty in YAML, env var SLACK_BOT_TOKEN is used."""
        config_path = _write_channel_yaml(
            tmp_path, enabled=True, bot_token="", signing_secret=""
        )
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-from-env")
        monkeypatch.setenv("SLACK_SIGNING_SECRET", "secret-from-env")

        from src.services.service_manager import initialize_channel_service

        settings = initialize_channel_service(config_path=config_path)

        assert settings.bot_token == "xoxb-from-env"
        assert settings.signing_secret == "secret-from-env"

    def test_yaml_token_takes_precedence_over_env(self, tmp_path, monkeypatch):
        """When bot_token is set in YAML, env var is NOT used."""
        config_path = _write_channel_yaml(
            tmp_path, enabled=True, bot_token="xoxb-yaml", signing_secret="yaml-secret"
        )
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-env-should-not-be-used")
        monkeypatch.setenv("SLACK_SIGNING_SECRET", "env-secret-should-not-be-used")

        from src.services.service_manager import initialize_channel_service

        settings = initialize_channel_service(config_path=config_path)

        assert settings.bot_token == "xoxb-yaml"
        assert settings.signing_secret == "yaml-secret"

    def test_missing_yaml_file_returns_defaults(self, tmp_path, monkeypatch):
        """Missing config file returns SlackSettings with env var fallbacks and logs warning."""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-fallback")
        monkeypatch.setenv("SLACK_SIGNING_SECRET", "secret-fallback")

        from src.services.service_manager import initialize_channel_service

        settings = initialize_channel_service(config_path=tmp_path / "nonexistent.yml")

        assert isinstance(settings, SlackSettings)
        assert settings.bot_token == "xoxb-fallback"
        assert settings.signing_secret == "secret-fallback"

    def test_empty_yaml_returns_default_settings(self, tmp_path):
        """An empty YAML file yields default SlackSettings (disabled)."""
        config_path = tmp_path / "channel.yml"
        config_path.write_text("")

        from src.services.service_manager import initialize_channel_service

        settings = initialize_channel_service(config_path=config_path)
        assert isinstance(settings, SlackSettings)
        assert settings.enabled is False

    def test_yaml_slack_key_with_none_value(self, tmp_path, monkeypatch):
        """YAML with 'slack:' key but no value should not crash (None coalescence)."""
        config_path = tmp_path / "channel.yml"
        config_path.write_text("slack:\n")
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-none-safe")
        monkeypatch.setenv("SLACK_SIGNING_SECRET", "secret-none-safe")

        from src.services.service_manager import initialize_channel_service

        settings = initialize_channel_service(config_path=config_path)

        assert isinstance(settings, SlackSettings)
        assert settings.bot_token == "xoxb-none-safe"
        assert settings.signing_secret == "secret-none-safe"


# ---------------------------------------------------------------------------
# initialize_sweep_service tests
# ---------------------------------------------------------------------------


class TestInitializeSweepService:
    def _make_deps(self):
        agent_svc = MagicMock()
        registry = MagicMock()
        return agent_svc, registry

    def test_returns_sweep_service_with_yaml_config(self, tmp_path):
        """initialize_sweep_service creates BackgroundSweepService with YAML values."""
        config_path = _write_sweep_yaml(tmp_path, interval=45, ttl=180)
        agent_svc, registry = self._make_deps()

        from src.services.service_manager import initialize_sweep_service

        svc = initialize_sweep_service(
            agent_service=agent_svc,
            session_registry=registry,
            config_path=config_path,
        )

        assert isinstance(svc, BackgroundSweepService)
        assert svc.config.sweep_interval_seconds == 45
        assert svc.config.task_ttl_seconds == 180

    def test_uses_defaults_when_no_config_path(self, tmp_path):
        """initialize_sweep_service uses SweepConfig defaults when no YAML is given."""
        agent_svc, registry = self._make_deps()

        # Patch _BASE_YAML to avoid loading real file
        services_dir = tmp_path / "services" / "task_sweep_service"
        services_dir.mkdir(parents=True)
        (services_dir / "sweep.yml").write_text(yaml.dump({"sweep_config": {}}))

        import src.services.service_manager as sm

        original = sm._BASE_YAML
        sm._BASE_YAML = tmp_path
        try:
            from src.services.service_manager import initialize_sweep_service

            svc = initialize_sweep_service(
                agent_service=agent_svc, session_registry=registry
            )
            assert isinstance(svc, BackgroundSweepService)
            assert svc.config.sweep_interval_seconds == 60
            assert svc.config.task_ttl_seconds == 300
        finally:
            sm._BASE_YAML = original

    def test_yaml_sweep_config_key_with_none_value(self, tmp_path):
        """YAML with 'sweep_config:' key but no value should not crash (None coalescence)."""
        config_path = tmp_path / "sweep.yml"
        config_path.write_text("sweep_config:\n")
        agent_svc, registry = self._make_deps()

        from src.services.service_manager import initialize_sweep_service

        svc = initialize_sweep_service(
            agent_service=agent_svc,
            session_registry=registry,
            config_path=config_path,
        )

        assert isinstance(svc, BackgroundSweepService)
        assert svc.config.sweep_interval_seconds == 60
        assert svc.config.task_ttl_seconds == 300

    def test_slack_service_fn_is_passed_through(self, tmp_path):
        """initialize_sweep_service wires slack_service_fn onto the service."""
        config_path = _write_sweep_yaml(tmp_path)
        agent_svc, registry = self._make_deps()
        slack_fn = MagicMock(return_value=None)

        from src.services.service_manager import initialize_sweep_service

        svc = initialize_sweep_service(
            agent_service=agent_svc,
            session_registry=registry,
            config_path=config_path,
            slack_service_fn=slack_fn,
        )

        assert svc._slack_service_fn is slack_fn

    def test_missing_yaml_file_returns_defaults(self, tmp_path):
        """Missing sweep config file returns BackgroundSweepService with SweepConfig defaults and logs warning."""
        agent_svc, registry = self._make_deps()

        from src.services.service_manager import initialize_sweep_service

        svc = initialize_sweep_service(
            agent_service=agent_svc,
            session_registry=registry,
            config_path=tmp_path / "nonexistent.yml",
        )

        assert isinstance(svc, BackgroundSweepService)
        assert svc.config.sweep_interval_seconds == 60
        assert svc.config.task_ttl_seconds == 300

    def test_empty_yaml_uses_default_sweep_config(self, tmp_path):
        """Empty YAML yields default SweepConfig values."""
        config_path = tmp_path / "sweep.yml"
        config_path.write_text("")
        agent_svc, registry = self._make_deps()

        from src.services.service_manager import initialize_sweep_service

        svc = initialize_sweep_service(
            agent_service=agent_svc,
            session_registry=registry,
            config_path=config_path,
        )

        assert svc.config.sweep_interval_seconds == 60
        assert svc.config.task_ttl_seconds == 300
