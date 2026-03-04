# N2: PersonaAgent Skill

Updated: 2026-03-03

## 1. Synopsis
- **Purpose**: Define the main Unity-facing agent behavior.
- **I/O**: User messages -> natural language response with emotion tags.

## 2. Core Logic
- **Step 1**: Create `container/skills/persona-agent/SKILL.md` with rules.
- **Step 2**: Migrate persona prompt and emotion keywords from backend.
- **Step 3**: Add `groups/unity/` with Unity-specific context.
- **Constraints**:
  - No markdown in responses (TTS output).
  - Keep responses 1-3 sentences for casual chat.

## 3. Usage
- Run agent in `group=unity` for all Unity requests.

---

## Appendix (Reference & Extensions)
### A. Related Documents
- [N3_mcp_tools.md](N3_mcp_tools.md)

### B. Test Scenarios
- Responses contain no markdown syntax or code blocks.
- Emotion tags appear when the input implies emotion.
- Language adapts to user preference (Korean/English).
