"""Unit tests for WebSocket message models."""

import pytest
from pydantic import ValidationError

from src.models.websocket import ChatMessage, MessageType, TtsChunkMessage


class TestChatMessageDefaults:
    def test_tts_enabled_default_is_true(self):
        msg = ChatMessage(content="hello", agent_id="a1", user_id="u1")
        assert msg.tts_enabled is True

    def test_reference_id_default_is_none(self):
        msg = ChatMessage(content="hello", agent_id="a1", user_id="u1")
        assert msg.reference_id is None

    def test_tts_enabled_can_be_set_false(self):
        msg = ChatMessage(
            content="hello", agent_id="a1", user_id="u1", tts_enabled=False
        )
        assert msg.tts_enabled is False

    def test_reference_id_can_be_set(self):
        msg = ChatMessage(
            content="hello", agent_id="a1", user_id="u1", reference_id="voice-x"
        )
        assert msg.reference_id == "voice-x"

    def test_existing_fields_still_work(self):
        msg = ChatMessage(
            content="hello", agent_id="agent-001", user_id="user-001", limit=5
        )
        assert msg.content == "hello"
        assert msg.type == MessageType.CHAT_MESSAGE

    def test_serialization_includes_new_fields(self):
        msg = ChatMessage(
            content="hello",
            agent_id="a1",
            user_id="u1",
            tts_enabled=True,
            reference_id="voice-x",
        )
        data = msg.model_dump()
        assert data["tts_enabled"] is True
        assert data["reference_id"] == "voice-x"


class TestTtsChunkMessage:
    def test_required_fields(self):
        msg = TtsChunkMessage(
            sequence=0, text="Hello!", motion_name="idle", blendshape_name="aa"
        )
        assert msg.sequence == 0
        assert msg.type == MessageType.TTS_CHUNK

    def test_audio_base64_optional_none(self):
        msg = TtsChunkMessage(
            sequence=0, text="Hi", motion_name="idle", blendshape_name="aa"
        )
        assert msg.audio_base64 is None

    def test_audio_base64_can_be_set(self):
        msg = TtsChunkMessage(
            sequence=1,
            text="Hi",
            audio_base64="SGVsbG8=",
            motion_name="talking",
            blendshape_name="oh",
        )
        assert msg.audio_base64 == "SGVsbG8="

    def test_emotion_optional_none(self):
        msg = TtsChunkMessage(
            sequence=0, text="Hi", motion_name="idle", blendshape_name="aa"
        )
        assert msg.emotion is None

    def test_sequence_is_required(self):
        with pytest.raises(ValidationError):
            TtsChunkMessage(text="Hi", motion_name="idle", blendshape_name="aa")

    def test_type_is_tts_chunk(self):
        msg = TtsChunkMessage(
            sequence=0, text="Hi", motion_name="idle", blendshape_name="aa"
        )
        assert msg.type == MessageType.TTS_CHUNK

    def test_serialization(self):
        msg = TtsChunkMessage(
            sequence=2, text="Hello.", motion_name="idle", blendshape_name="aa"
        )
        data = msg.model_dump()
        assert data["type"] == "tts_chunk"
        assert data["audio_base64"] is None
