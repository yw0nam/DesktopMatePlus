# Quality Score

Last updated: 2026-04-09

| Domain | Arch | Test | Obs | Docs | Overall |
|--------|------|------|-----|------|---------|
| backend | A | B | A | A | B |

## Grade Definitions

A: All GP checks pass, no known debt
B: 1-2 minor violations or known debt
C: Major violations present, tracked
D: Critical violations or no coverage
UNCHECKED: Not evaluated by garden.sh — manual review required

## Auto-update

Run `scripts/clean/garden.sh` to refresh grades based on GP results.

## Violations Summary

_Last updated by quality-agent run._

- GP-3 (backend): 0 violations
- GP-8 (backend): 1 violation (lint failed — black target-version)
