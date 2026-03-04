# NanoClaw Tasks Index

Updated: 2026-03-03

## 1. Synopsis
- **Purpose**: Split NanoClaw engine work into implementable modules.
- **I/O**: FastAPI run requests -> SSE stream -> tool calls to Backend.

## 2. Core Logic
- **N1**: SSE server and protocol -> [N1_sse_server.md](N1_sse_server.md)
- **N2**: PersonaAgent skill and Unity group -> [N2_persona_skill.md](N2_persona_skill.md)
- **N3**: MCP tools for Backend services -> [N3_mcp_tools.md](N3_mcp_tools.md)
- **N4**: Interrupt handling -> [N4_interrupt.md](N4_interrupt.md)
- **N5**: Multi-agent Slack routing -> [N5_multi_agent.md](N5_multi_agent.md)
- **N6**: Health and monitoring -> [N6_health_monitoring.md](N6_health_monitoring.md)

## 3. Usage
- Build the streaming path first: N1 -> N2 -> N3.
- Add control: N4.
- Expand channels: N5.
- Harden: N6.

---

## Appendix (Reference & Extensions)
### A. Related Documents
- [NANOCLAW_INTEGRATION_PRD.md](../NANOCLAW_INTEGRATION_PRD.md)
- [task_fastapi/INDEX.md](../task_fastapi/INDEX.md)
- [task_unity/INDEX.md](../task_unity/INDEX.md)
