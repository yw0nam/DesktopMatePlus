# Guidelines for CHANGELOG.md

## 1. General Principles
* **User-Centric:** Focus on what changed and why it matters to the user, not just raw commit hashes.
* **Grouping:** Always group changes into standardized categories.
* **Clarity:** Use the imperative mood (e.g., "Add feature" instead of "Added feature" or "Adds feature").
* **No Spoilers/Internal Noise:** Exclude internal refactors or documentation typos unless they impact the public API.

## 2. Format Convention
Each release entry must follow this structure:

```markdown
# [Version] - YYYY-MM-DD

## Added
- New features that were introduced.

## Changed
- Changes in existing functionality.

## Deprecated
- Soon-to-be removed features.

## Removed
- Features that have been removed in this version.

## Fixed
- Any bug fixes.

## Security
- Vulnerability patches.
```

---

## Versioning Criteria (SemVer 2.0.0)

Version numbers follow the $MAJOR.MINOR.PATCH$ format. Use the following logic to determine which number to increment:

### 🔴 MAJOR Version
**When to increment:** When you make **incompatible API changes**.
* Breaking changes that require users to update their code.
* Removal of previously deprecated features.
* A complete rewrite of the core logic that changes fundamental behavior.

### 🟡 MINOR Version
**When to increment:** When you add **functionality in a backwards compatible manner**.
* New features or API endpoints added without breaking existing ones.
* Marking specific features as `Deprecated`.
* Substantial internal improvements that don't change the interface.

### 🟢 PATCH Version
**When to increment:** When you make **backwards compatible bug fixes**.
* Security patches or vulnerability fixes.
* Small UI/UX tweaks.
* Performance optimizations that do not change functionality.
