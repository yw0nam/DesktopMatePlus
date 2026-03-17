"""Unit tests for WebSocket message models."""

import base64

import pytest
from pydantic import ValidationError

from src.models.websocket import (
    _MAX_IMAGE_BASE64_BYTES,
    ChatMessage,
    ImageContent,
    ImageUrl,
    MessageType,
    TtsChunkMessage,
)


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
        assert msg.agent_id == "agent-001"
        assert msg.user_id == "user-001"
        assert msg.limit == 5

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

    def test_persona_id_default_is_yuri(self):
        msg = ChatMessage(content="hello", agent_id="a1", user_id="u1")
        assert msg.persona_id == "yuri"

    def test_persona_id_can_be_set(self):
        msg = ChatMessage(content="hello", agent_id="a1", user_id="u1", persona_id="kael")
        assert msg.persona_id == "kael"

    def test_persona_field_no_longer_exists(self):
        msg = ChatMessage(content="hello", agent_id="a1", user_id="u1")
        assert not hasattr(msg, "persona")


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


class TestImageContentValidation:
    def _make_data_url(self, size_bytes: int) -> str:
        b64 = base64.b64encode(b"x" * size_bytes).decode()
        return f"data:image/jpeg;base64,{b64}"

    def test_small_image_passes(self):
        url = self._make_data_url(100)
        content = ImageContent(image_url=ImageUrl(url=url))
        assert content.image_url.url == url

    def test_oversized_image_raises(self):
        url = self._make_data_url(_MAX_IMAGE_BASE64_BYTES + 1)
        with pytest.raises(ValidationError, match="too large"):
            ImageContent(image_url=ImageUrl(url=url))

    def test_http_url_skips_size_check(self):
        content = ImageContent(image_url=ImageUrl(url="https://example.com/img.jpg"))
        assert content.image_url.url == "https://example.com/img.jpg"
