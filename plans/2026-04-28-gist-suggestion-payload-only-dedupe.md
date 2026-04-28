# Plan: Gist Suggestion Payload-only Parse + Dedupe Append

- state: completed
- date: 2026-04-28

## Goal
Only parse JSON suggestion payload from issue body and append only inner section items (`plugins`, `datapacks`, `mods`) to the gist file without duplicates.

## Steps
1. Locate gist suggestion apply workflow script and current parser behavior.
2. Update parsing to target the `Suggestion payload:` section before JSON extraction.
3. Keep append behavior limited to section array items and preserve duplicate skipping by `id`.
4. Run syntax validation.

## Validation
- `python -m py_compile src/gist_suggestions/apply_gist_suggestions.py`

## Result
Completed. Issue parser now prioritizes the payload section and appends only list contents into section arrays.
