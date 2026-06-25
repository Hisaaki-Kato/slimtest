# lighttest

Factory + trait DSL on top of dbt unit tests. Removes column-level
repetition from `unit_tests` YAML by letting you write factories and
overrides instead of full row dicts.

See `design.md` for the design and `examples/sample_dbt_project/` for a
runnable example of the pain `lighttest` aims to fix.

## Status

Pre-alpha. CLI surface (`lighttest compile`, `lighttest unittest`) is
stubbed; the factory registry, schema and deep-merge core are
implemented and tested.

## Development

```bash
uv sync                  # install runtime + dev deps
uv run pytest            # run tests
uv run ruff check .      # lint
uv run ruff format .     # format
uv run mypy src tests    # type check
```
