# Document Authoring Guide

All documents focus on **Actionability** and **Modularity**.

---

## 1. Core Principles

| Principle | Description |
|-----------|-------------|
| **Zero-Latency Start** | Readers should be able to write code or perform tasks immediately after reading—no additional exploration needed. |
| **Hard Limit 200** | Core content must not exceed 200 lines. This is a physical limit considering agent context windows and human attention span. |
| **Lazy Loading (Appendix)** | Edge cases, references, and detailed configurations that aren't immediately needed should be separated into an Appendix for on-demand reference. |
| **Reflect src code structure** | Document structure should mirror the source code organization to facilitate easy navigation and maintenance. |

---

## 2. Standard Document Structure

All documents follow this markdown structure:

```markdown
# [Document Title: Feature/Module Name]

Updated: YYYY-MM-DD

## 1. Synopsis
- **Purpose**: One-line summary of the module's core function
- **I/O**: Input (parameters) -> Output (results)

## 2. Core Logic
> **Rule**: This section must be under 200 lines and immediately implementable.

- [Step 1]: Specific execution/implementation method
- [Step 2]: Essential code snippets or logic flow
- [Constraints]: Rules that must be followed (security, performance, etc.)

## 3. Usage
- Most frequently used Happy Path example code (keep it brief)

---

## Appendix (Reference & Extensions)
> Refer only when exceptions occur or deeper information is needed.

### A. Troubleshooting
- Solution for Error X: [link/filename]

### B. Detailed References
- Full API Specification: [URL]
- Legacy Code History: [document filename]

### C. Related Documents
- Other module guides connected to this module: [filename]
```

---

## 3. Detailed Writing Rules

### Rule 1: The 200-Line Rule

The main body (`## 1. Synopsis` through `## 3. Usage`) must **never exceed 200 lines**.

| Guideline | Action |
|-----------|--------|
| **Remove Background** | Delete historical context like "why we chose this technology" or replace with separate wiki links. |
| **Optimize Code Snippets** | Show only core logic—don't paste entire code blocks. |
| **Use Directive Language** | Write "Do X" instead of "It's recommended to do X". |

### Rule 2: Splitting Strategy

When a document shows signs of exceeding 200 lines, **immediately split by functional units**.

**Splitting Criteria:**

- **By Role**: If `Auth_Guide.md` grows too long → split into `Auth_Login.md`, `Auth_Refresh_Token.md`
- **By Phase**: If `Deploy_Guide.md` grows too long → split into `Deploy_Setup.md`, `Deploy_Execution.md`
- **Main Document**: Manage split documents as a list in a thin "index document"

### Rule 3: Delegation via Appendix

The Appendix serves as both "insurance" and "expansion pack". Move all heavy information here to keep the main body lightweight.

| Strategy | Implementation |
|----------|----------------|
| **Use External Links** | Keep library docs, team Figma, full DB schema specs as URLs only. |
| **Error Handling** | Don't list all edge cases in the main body. Only include "Top 3 Common Errors"—put everything else in a separate troubleshooting document or Appendix. |
| **Reference Triggers** | Include explicit trigger sentences like *"For situation X, refer to Appendix A"* to prevent agents from getting lost. |

---

## 4. Quality Checklist

Before saving a document, verify the following:

- [ ] **Length**: Is the main body under 200 lines? (Can it be grasped in one or two scrolls?)
- [ ] **Immediacy**: Can someone write code just by reading this document? (No unnecessary introductions?)
- [ ] **Extensibility**: Are edge cases and extensive data linked to Appendix or external sources?
- [ ] **Clarity**: Is the writing directive and unambiguous?
