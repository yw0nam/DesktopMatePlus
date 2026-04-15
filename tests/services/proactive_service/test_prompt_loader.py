"""Tests for proactive prompt template loader."""

import pytest

from src.services.proactive_service.prompt_loader import PromptLoader


@pytest.fixture
def loader(tmp_path):
    prompts_file = tmp_path / "proactive_prompts.yml"
    prompts_file.write_text(
        "idle: |\n"
        "  유저가 {idle_seconds}초 동안 조용합니다.\n"
        "  현재 시각은 {current_time}입니다.\n"
        "webhook: |\n"
        "  컨텍스트: {context}\n"
    )
    return PromptLoader(prompts_file)


class TestPromptLoader:
    def test_render_idle_prompt(self, loader):
        """Idle prompt rendered with valid kwargs must contain interpolated values."""
        result = loader.render("idle", idle_seconds=300, current_time="09:00:00")
        assert "300" in result
        assert "09:00:00" in result

    def test_render_webhook_prompt(self, loader):
        """Webhook prompt rendered with context kwarg must contain interpolated value."""
        result = loader.render("webhook", context="서버 점검")
        assert "서버 점검" in result

    def test_missing_key_returns_fallback(self, loader):
        """Rendering an unknown trigger type must return a fallback string containing the type name."""
        result = loader.render("nonexistent")
        assert "nonexistent" in result

    def test_missing_variable_left_as_placeholder(self, loader):
        """Rendering with a missing variable must leave the placeholder intact."""
        # Render idle without current_time → {current_time} should stay
        result = loader.render("idle", idle_seconds=300)
        assert "{current_time}" in result

    def test_reload(self, loader, tmp_path):
        """After overwriting the YAML file and calling reload(), new templates are used."""
        new_file = tmp_path / "proactive_prompts.yml"
        new_file.write_text("custom: |\n  안녕 {name}!\n")
        loader._path = new_file
        loader.reload()

        result = loader.render("custom", name="유리")
        assert "유리" in result
        # Old key should now be missing
        fallback = loader.render("idle")
        assert "idle" in fallback

    def test_missing_file_results_in_empty_templates(self, tmp_path):
        """PromptLoader with a non-existent file path must gracefully produce fallback renders."""
        missing = tmp_path / "does_not_exist.yml"
        loader = PromptLoader(missing)
        result = loader.render("idle")
        assert "idle" in result

    def test_empty_yaml_results_in_fallback(self, tmp_path):
        """An empty YAML file must result in fallback renders for all trigger types."""
        empty_file = tmp_path / "empty.yml"
        empty_file.write_text("")
        loader = PromptLoader(empty_file)
        result = loader.render("morning")
        assert "morning" in result
