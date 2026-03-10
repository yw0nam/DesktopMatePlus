# Changelog

All notable changes to DesktopMatePlus Backend will be documented in this file.

## [2.2.0] - 2026-03-10

### Added
- Background sweep service for expired delegated task cleanup
- `STMService.list_all_sessions()` for cross-user session scanning
- vLLM Omni TTS support
- E2E tests for real service integration
- LTM consolidation tests
- TTS synthesis pipeline tests

### Changed
- LTM turn counter now counts only HumanMessages (previously incorrectly used `len(history)//2`)
- Improved turn counter slice logic for accurate consolidation

### Deprecated
- VLM service — Agent now natively supports image+text input

### Fixed
- LTM turn counter accuracy with mixed message types
- Turn slice calculation for LTM consolidation

## [2.1.0] - 2025-11-28

### Added
- Avatar configuration management via WebSocket
- Background image management via WebSocket
- Live2D model configuration support
- Updated documentation structure

### Changed
- Improved WebSocket API organization

## [2.0.0] - 2025-11-20

### Added
- Complete WebSocket streaming with real-time TTS chunks
- MongoDB-based STM for session management
- mem0 integration for long-term memory
- Customizable agent personas per message
- Non-blocking async memory save (no TTS blocking)
- Production-ready error handling and reconnection
- Full test coverage for all services

### Changed
- Major architectural improvements
- Enhanced memory system

## [1.0.0] - 2025-10-15

### Added
- Initial release with basic HTTP APIs
- WebSocket streaming foundation
- VLM and TTS service integration
- Core service architecture

---

For detailed technical changes and patch notes, see [docs/patch/](docs/patch/).
