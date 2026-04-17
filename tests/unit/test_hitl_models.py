"""Unit tests for HitL message models and turn status."""

import pytest
from pydantic import ValidationError

from src.models.websocket import (
    ClientMessage,
    HitLRequestMessage,
    HitLResponseMessage,
    MessageType,
    ServerMessage,
    ToolCategory,
)
from src.services.websocket_service.message_processor.models import TurnStatus


class TestHitLMessageTypes:
    """Test HitL message type enum values."""

    def test_hitl_request_type_exists(self):
        assert MessageType.HITL_REQUEST == "hitl_request"

    def test_hitl_response_type_exists(self):
        assert MessageType.HITL_RESPONSE == "hitl_response"


class TestHitLRequestMessage:
    """Test HitLRequestMessage serialization."""

    def test_serialization(self):
        msg = HitLRequestMessage(
            request_id="req-123",
            tool_name="dangerous_tool",
            tool_args={"query": "hello"},
            session_id="session-456",
            category=ToolCategory.DANGEROUS,
        )
        assert msg.type == MessageType.HITL_REQUEST
        assert msg.request_id == "req-123"
        assert msg.tool_name == "dangerous_tool"
        assert msg.tool_args == {"query": "hello"}
        assert msg.session_id == "session-456"

    def test_json_roundtrip(self):
        msg = HitLRequestMessage(
            request_id="req-123",
            tool_name="test_tool",
            tool_args={"key": "value"},
            session_id="sess-1",
            category=ToolCategory.DANGEROUS,
        )
        data = msg.model_dump()
        assert data["type"] == "hitl_request"
        assert data["request_id"] == "req-123"

    def test_in_server_message_union(self):
        """HitLRequestMessage should be part of ServerMessage union."""
        msg = HitLRequestMessage(
            request_id="r1",
            tool_name="t1",
            tool_args={},
            session_id="s1",
            category=ToolCategory.DANGEROUS,
        )
        # Should be assignable to ServerMessage type
        server_msg: ServerMessage = msg
        assert isinstance(server_msg, HitLRequestMessage)


class TestToolCategoryEnum:
    def test_enum_values_use_snake_case_names(self):
        """All values follow the snake-cased version of the member name."""
        for member in ToolCategory:
            assert member.value == member.name.lower()

    def test_enum_is_usable_as_str(self):
        """Wire format is string — direct comparison must work without .value."""
        assert ToolCategory.READ_ONLY == "read_only"
        assert ToolCategory.DANGEROUS == "dangerous"


class TestHitLRequestMessageCategory:
    def test_category_field_required(self):
        with pytest.raises(ValidationError):
            HitLRequestMessage(
                request_id="r1",
                tool_name="write_file",
                tool_args={},
                session_id="s1",
            )

    def test_category_accepts_enum(self):
        msg = HitLRequestMessage(
            request_id="r1",
            tool_name="write_file",
            tool_args={},
            session_id="s1",
            category=ToolCategory.STATE_MUTATING,
        )
        assert msg.type == MessageType.HITL_REQUEST
        assert msg.category == ToolCategory.STATE_MUTATING

    def test_category_coerces_from_string(self):
        msg = HitLRequestMessage(
            request_id="r1",
            tool_name="terminal",
            tool_args={},
            session_id="s1",
            category="dangerous",
        )
        assert msg.category == ToolCategory.DANGEROUS


class TestHitLResponseMessage:
    """Test HitLResponseMessage serialization."""

    def test_approve_serialization(self):
        msg = HitLResponseMessage(
            request_id="req-123",
            approved=True,
        )
        assert msg.type == MessageType.HITL_RESPONSE
        assert msg.request_id == "req-123"
        assert msg.approved is True

    def test_deny_serialization(self):
        msg = HitLResponseMessage(
            request_id="req-123",
            approved=False,
        )
        assert msg.approved is False

    def test_in_client_message_union(self):
        """HitLResponseMessage should be part of ClientMessage union."""
        msg = HitLResponseMessage(
            request_id="r1",
            approved=True,
        )
        client_msg: ClientMessage = msg
        assert isinstance(client_msg, HitLResponseMessage)


class TestAwaitingApprovalStatus:
    """Test AWAITING_APPROVAL turn status."""

    def test_status_exists(self):
        assert TurnStatus.AWAITING_APPROVAL.value == "awaiting_approval"

    def test_not_terminal(self):
        """AWAITING_APPROVAL should NOT be in the terminal status set."""
        terminal_statuses = {
            TurnStatus.COMPLETED,
            TurnStatus.INTERRUPTED,
            TurnStatus.FAILED,
        }
        assert TurnStatus.AWAITING_APPROVAL not in terminal_statuses
