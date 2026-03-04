# N5: Multi-Agent Slack Routing

Updated: 2026-03-03

## 1. Synopsis
- **Purpose**: Run specialized agents in Slack only and keep Unity output clean.
- **I/O**: Slack mentions -> specialized agent output in Slack threads.

## 2. Core Logic
- **Step 1**: Create skills for ReadDev/Review/PM agents (Slack-only output rules).
- **Step 2**: Add Slack channel adapter and routing rules.
- **Step 3**: Return completion status to PersonaAgent for Unity summary.
- **Constraints**:
  - Specialized agents must never emit Unity streaming output.

## 3. Usage
- PersonaAgent delegates by `@ReadDevAgent` and posts a Unity summary only.

---

## Appendix (Reference & Extensions)
### A. Related Documents
- [N2_persona_skill.md](N2_persona_skill.md)

### B. Test Scenarios
- Specialized agents post results only in Slack threads.
- Unity receives only a short summary from PersonaAgent.
- Slack routing handles @mention for each specialized agent.
