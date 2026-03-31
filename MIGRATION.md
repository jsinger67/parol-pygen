# Migration Notes

## Semantic callback naming

`on_production(lhs_nt, prod_idx, rhs_values)` is the preferred algorithm-neutral low-level callback.

`on_reduce(lhs_nt, prod_idx, rhs_values)` remains supported as a backward-compatible alias.

Recommended update for user code:

- keep existing `on_<non_terminal>` typed callbacks unchanged
- keep `on_non_terminal(name, node)` generic callback unchanged
- migrate low-level callback implementations from `on_reduce` to `on_production`

## Extraction readiness

The `tools/parol-pygen` subtree is split-ready:

- bundled schema package data under `src/parol_pygen/schemas`
- local test fixtures under `tests/fixtures`
- standalone project scaffold command via `parol-pygen init`
