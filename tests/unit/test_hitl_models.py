"""Tests for HITL WebSocket Pydantic models (built-in shape)."""

import pytest
from pydantic import ValidationError

from src.models.websocket import (
    HitLActionRequest,
    HitLDecision,
    HitLEditedAction,
    HitLRequestMessage,
    HitLResponseMessage,
    HitLReviewConfig,
    MessageType,
)


def test_hitl_action_request_valid():
    ar = HitLActionRequest(
        name="write_file",
        args={"file_path": "a.txt", "text": "hi"},
        description="desc",
    )
    assert ar.name == "write_file"


def test_hitl_review_config_rejects_unknown_decision():
    with pytest.raises(ValidationError):
        HitLReviewConfig(action_name="write_file", allowed_decisions=["bogus"])


def test_hitl_request_message_shape():
    msg = HitLRequestMessage(
        session_id="s1",
        action_requests=[
            HitLActionRequest(name="write_file", args={}, description="d"),
        ],
        review_configs=[
            HitLReviewConfig(
                action_name="write_file", allowed_decisions=["approve", "reject"]
            ),
        ],
    )
    assert msg.type == MessageType.HITL_REQUEST


def test_hitl_decision_approve_allows_bare():
    d = HitLDecision(type="approve")
    assert d.edited_action is None and d.message is None


def test_hitl_decision_edit_requires_edited_action():
    with pytest.raises(ValidationError):
        HitLDecision(type="edit")


def test_hitl_decision_edit_with_edited_action():
    d = HitLDecision(
        type="edit",
        edited_action=HitLEditedAction(
            name="write_file", args={"file_path": "b.txt", "text": "hi"}
        ),
    )
    assert d.edited_action.name == "write_file"


def test_hitl_decision_approve_rejects_message_or_edited_action():
    with pytest.raises(ValidationError):
        HitLDecision(type="approve", message="no")
    with pytest.raises(ValidationError):
        HitLDecision(
            type="approve",
            edited_action=HitLEditedAction(name="x", args={}),
        )


def test_hitl_decision_reject_allows_optional_message():
    d = HitLDecision(type="reject", message="unsafe path")
    assert d.message == "unsafe path"


def test_hitl_response_message_list_shape():
    msg = HitLResponseMessage(decisions=[HitLDecision(type="approve")])
    assert msg.type == MessageType.HITL_RESPONSE
    assert len(msg.decisions) == 1
