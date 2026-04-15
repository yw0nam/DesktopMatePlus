"""Tests for ProactiveConfig and ScheduleEntry models."""

import pytest
from pydantic import ValidationError

from src.services.proactive_service.config import ProactiveConfig, ScheduleEntry

# ---------------------------------------------------------------------------
# ScheduleEntry tests
# ---------------------------------------------------------------------------


class TestScheduleEntry:
    def test_valid_schedule(self):
        """A valid ScheduleEntry with all required fields should construct without error."""
        entry = ScheduleEntry(
            id="morning_greeting",
            cron="0 9 * * *",
            prompt_key="morning",
        )
        assert entry.id == "morning_greeting"
        assert entry.cron == "0 9 * * *"
        assert entry.prompt_key == "morning"

    def test_enabled_true_by_default(self):
        """ScheduleEntry.enabled must default to True."""
        entry = ScheduleEntry(id="test", cron="* * * * *", prompt_key="idle")
        assert entry.enabled is True

    def test_enabled_can_be_set_false(self):
        """ScheduleEntry.enabled can be explicitly set to False."""
        entry = ScheduleEntry(
            id="test", cron="* * * * *", prompt_key="idle", enabled=False
        )
        assert entry.enabled is False

    def test_missing_required_field_raises(self):
        """Missing required fields (id, cron, prompt_key) must raise ValidationError."""
        with pytest.raises(ValidationError):
            ScheduleEntry(cron="* * * * *", prompt_key="idle")  # missing id


# ---------------------------------------------------------------------------
# ProactiveConfig tests
# ---------------------------------------------------------------------------


class TestProactiveConfig:
    def test_defaults_are_reasonable(self):
        """Default values must be positive and within expected ranges."""
        cfg = ProactiveConfig()
        assert cfg.idle_timeout_seconds == 300
        assert cfg.cooldown_seconds == 600
        assert cfg.watcher_interval_seconds == 30
        assert cfg.schedules == []

    def test_custom_values(self):
        """Custom values must be stored correctly."""
        cfg = ProactiveConfig(
            idle_timeout_seconds=180,
            cooldown_seconds=120,
            watcher_interval_seconds=10,
            schedules=[
                ScheduleEntry(id="morning", cron="0 9 * * *", prompt_key="morning")
            ],
        )
        assert cfg.idle_timeout_seconds == 180
        assert cfg.cooldown_seconds == 120
        assert cfg.watcher_interval_seconds == 10
        assert len(cfg.schedules) == 1
        assert cfg.schedules[0].id == "morning"

    def test_minimum_values_enforced_idle_timeout(self):
        """idle_timeout_seconds must be >= 1; value of 0 must raise ValidationError."""
        with pytest.raises(ValidationError):
            ProactiveConfig(idle_timeout_seconds=0)

    def test_minimum_values_enforced_watcher_interval(self):
        """watcher_interval_seconds must be >= 1; value of 0 must raise ValidationError."""
        with pytest.raises(ValidationError):
            ProactiveConfig(watcher_interval_seconds=0)

    def test_cooldown_seconds_can_be_zero(self):
        """cooldown_seconds is >= 0, so 0 is a valid value."""
        cfg = ProactiveConfig(cooldown_seconds=0)
        assert cfg.cooldown_seconds == 0

    def test_cooldown_seconds_negative_raises(self):
        """cooldown_seconds must be >= 0; negative value must raise ValidationError."""
        with pytest.raises(ValidationError):
            ProactiveConfig(cooldown_seconds=-1)

    def test_schedules_default_is_empty_list(self):
        """schedules must default to an empty list (not None or shared mutable)."""
        cfg1 = ProactiveConfig()
        cfg2 = ProactiveConfig()
        assert cfg1.schedules == []
        cfg1.schedules.append(
            ScheduleEntry(id="x", cron="* * * * *", prompt_key="idle")
        )
        assert cfg2.schedules == [], "default_factory must produce independent lists"

    def test_multiple_schedules(self):
        """Multiple ScheduleEntry items must all be stored correctly."""
        entries = [
            ScheduleEntry(id="morning", cron="0 9 * * *", prompt_key="morning"),
            ScheduleEntry(
                id="evening", cron="0 18 * * *", prompt_key="idle", enabled=False
            ),
        ]
        cfg = ProactiveConfig(schedules=entries)
        assert len(cfg.schedules) == 2
        assert cfg.schedules[1].enabled is False
