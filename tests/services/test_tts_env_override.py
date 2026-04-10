"""Tests for TTS env override hook in initialize_tts_service."""

from unittest.mock import MagicMock, patch


class TestTTSEnvOverride:
    def _make_yaml_config(self, base_url: str = "http://original:8000") -> dict:
        return {
            "tts_config": {
                "type": "irodori",
                "configs": {"base_url": base_url},
            }
        }

    def _make_mock_service(self) -> MagicMock:
        mock_svc = MagicMock()
        mock_svc.is_healthy.return_value = (True, "ok")
        return mock_svc

    def test_env_var_set_overrides_base_url(self, monkeypatch):
        monkeypatch.setenv("IRODORI_TTS_BASE_URL", "http://override:9999")

        mock_svc = self._make_mock_service()
        yaml_cfg = self._make_yaml_config()

        with (
            patch(
                "src.services.service_manager._load_yaml_config",
                return_value=yaml_cfg,
            ),
            patch(
                "src.services.service_manager.TTSFactory.get_tts_engine",
                return_value=mock_svc,
            ) as mock_factory,
            patch(
                "src.services.service_manager._tts_service_instance",
                None,
            ),
        ):
            import src.services.service_manager as sm

            sm._tts_service_instance = None
            sm.initialize_tts_service(force_reinit=True)

            _, kwargs = mock_factory.call_args
            assert kwargs["base_url"] == "http://override:9999"

        sm._tts_service_instance = None

    def test_env_var_absent_leaves_base_url_unchanged(self, monkeypatch):
        monkeypatch.delenv("IRODORI_TTS_BASE_URL", raising=False)

        mock_svc = self._make_mock_service()
        yaml_cfg = self._make_yaml_config(base_url="http://original:8000")

        with (
            patch(
                "src.services.service_manager._load_yaml_config",
                return_value=yaml_cfg,
            ),
            patch(
                "src.services.service_manager.TTSFactory.get_tts_engine",
                return_value=mock_svc,
            ) as mock_factory,
        ):
            import src.services.service_manager as sm

            sm._tts_service_instance = None
            sm.initialize_tts_service(force_reinit=True)

            _, kwargs = mock_factory.call_args
            assert kwargs["base_url"] == "http://original:8000"

        sm._tts_service_instance = None

    def test_env_var_skipped_for_non_irodori_engine(self, monkeypatch):
        monkeypatch.setenv("IRODORI_TTS_BASE_URL", "http://override:9999")
        mock_svc = self._make_mock_service()
        yaml_cfg = {
            "tts_config": {
                "type": "vllm_omni",
                "configs": {"model": "test-model"},
            }
        }

        with (
            patch(
                "src.services.service_manager._load_yaml_config",
                return_value=yaml_cfg,
            ),
            patch(
                "src.services.service_manager.TTSFactory.get_tts_engine",
                return_value=mock_svc,
            ) as mock_factory,
        ):
            import src.services.service_manager as sm

            sm._tts_service_instance = None
            sm.initialize_tts_service(force_reinit=True)

            _, kwargs = mock_factory.call_args
            assert "base_url" not in kwargs

        sm._tts_service_instance = None
