def test_save_turn_not_imported_in_event_handlers():
    """Checkpointer handles saves — save_turn must not be called from event_handlers."""
    import src.services.websocket_service.message_processor.event_handlers as eh

    assert not hasattr(
        eh, "save_turn"
    ), "save_turn found in event_handlers — checkpointer should handle persistence"
