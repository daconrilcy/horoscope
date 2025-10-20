# Issue 9bis — Realign LLM Guard after prior merge

## Context
Issue #9 (LLM I/O guard) was partially implemented earlier and merged in a previous version. The Phase-4 taskpack specifies additional requirements (env-driven limits, FR denylist, enable flag, docs). This issue 9bis tracks the rebase/realignment work to conform to Phase-4 spec without breaking existing behavior.

## Observed differences vs spec
- Input length: hardcoded 1000 instead of env-driven `LLM_GUARD_MAX_INPUT_LEN`.
- Denylist: EN-only; missing French phrases (e.g., "ignore les instructions précédentes").
- Enable flag: missing `LLM_GUARD_ENABLE` to bypass guard when disabled.
- Env/Docs: no `.env.example` entries and no README mention.
- Metrics: optional in spec; not implemented (acceptable for now).

## Changes applied in this repo
- Added `LLM_GUARD_ENABLE` (default true) and `LLM_GUARD_MAX_INPUT_LEN` (default 1000) to settings.
- Updated guard to honor the enable flag and use env-driven max length.
- Expanded denylist with FR variants (case-insensitive).
- Added `.env.example` with guard entries; updated README with a brief section.

## Validation
- Existing tests keep passing (`tests/test_llm_guard.py` for injection + PII masking).
- Follow-up recommended: add tests for empty/whitespace-only input, over-length input, and FR denylist coverage per acceptance criteria.

## Rebase/realignment plan
1. Confirm no downstream code depends on the previous hardcoded max length.
2. Communicate new env flags to teams; update deployment envs using `.env.example`.
3. (Optional) Add metrics later (`llm_guard_blocks_total{reason}`, `llm_guard_pii_redactions_total{type}`) as a separate PR.
4. Add missing tests and finalize documentation references.

## PR Template
- Title: `fix(security): realign LLM guard with Phase-4 spec (Refs #9, Closes #9bis)`
- Labels: `security`, `phase4`, `backport`
