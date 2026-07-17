"""Tests for `slimtest.model_parser`."""

from __future__ import annotations

import pytest

from slimtest.model_parser import (
    InvalidModelYmlError,
    find_model_ymls,
    find_slimtest_tests,
    parse_model_yml,
)

# A reusable model.yml snippet -- the standard happy-path shape we expect.
HAPPY_PATH_YML = """
version: 2
models:
  - name: my_model
    description: a model
    meta:
      slimtest:
        unit_tests:
          - name: test_one
            description: first
            given:
              upstream_a:
                - factory: row_a
            expect:
              - {col: 1}
          - name: test_two
            given:
              upstream_a:
                - {col: literal}
            expect:
              - {col: 2}
"""


class TestParseModelYml:
    def test_happy_path_collects_all_tests(self, tmp_path, write_yaml):
        path = write_yaml("models/x.yml", HAPPY_PATH_YML)
        parsed = parse_model_yml(path, tmp_path)
        assert [p.spec.name for p in parsed] == ["test_one", "test_two"]
        assert all(p.model_name == "my_model" for p in parsed)
        assert all(p.source_path == path.relative_to(tmp_path) for p in parsed)

    def test_line_numbers_are_recovered(self, tmp_path, write_yaml):
        # We point at the YAML lines explicitly so this stays robust to edits.
        path = write_yaml(
            "models/x.yml",
            """\
version: 2
models:
  - name: my_model
    meta:
      slimtest:
        unit_tests:
          - name: alpha
            given: {u: []}
            expect: []
          - name: beta
            given: {u: []}
            expect: []
""",
        )
        parsed = parse_model_yml(path, tmp_path)
        alpha = next(p for p in parsed if p.spec.name == "alpha")
        beta = next(p for p in parsed if p.spec.name == "beta")
        # "- name: alpha" line is the 7th line (1-indexed).
        assert alpha.source_line == 7
        # "- name: beta" is line 10.
        assert beta.source_line == 10

    def test_empty_yml_returns_empty(self, tmp_path, write_yaml):
        path = write_yaml("models/empty.yml", "")
        assert parse_model_yml(path, tmp_path) == []

    def test_yml_without_models_returns_empty(self, tmp_path, write_yaml):
        path = write_yaml("models/x.yml", "version: 2\n")
        assert parse_model_yml(path, tmp_path) == []

    def test_yml_with_models_but_no_meta_returns_empty(self, tmp_path, write_yaml):
        path = write_yaml(
            "models/x.yml",
            """
            version: 2
            models:
              - name: a
                description: no slimtest here
            """,
        )
        assert parse_model_yml(path, tmp_path) == []

    def test_empty_meta_slimtest_returns_empty(self, tmp_path, write_yaml):
        path = write_yaml(
            "models/x.yml",
            """
            models:
              - name: a
                meta:
                  slimtest: {}
            """,
        )
        assert parse_model_yml(path, tmp_path) == []

    def test_multiple_models_in_one_file(self, tmp_path, write_yaml):
        path = write_yaml(
            "models/x.yml",
            """
            models:
              - name: a
                meta:
                  slimtest:
                    unit_tests:
                      - {name: t_a, given: {u: []}, expect: []}
              - name: b
                meta:
                  slimtest:
                    unit_tests:
                      - {name: t_b, given: {u: []}, expect: []}
            """,
        )
        parsed = parse_model_yml(path, tmp_path)
        by_test = {p.spec.name: p.model_name for p in parsed}
        assert by_test == {"t_a": "a", "t_b": "b"}

    def test_malformed_yaml_raises(self, tmp_path, write_yaml):
        path = write_yaml("models/bad.yml", "models: [oops: :")
        with pytest.raises(InvalidModelYmlError):
            parse_model_yml(path, tmp_path)

    def test_invalid_slimtest_block_raises(self, tmp_path, write_yaml):
        path = write_yaml(
            "models/x.yml",
            """
            models:
              - name: a
                meta:
                  slimtest:
                    unit_tests:
                      - {wrong_key: 1}
            """,
        )
        with pytest.raises(InvalidModelYmlError):
            parse_model_yml(path, tmp_path)

    def test_models_entry_without_name_is_skipped(self, tmp_path, write_yaml):
        path = write_yaml(
            "models/x.yml",
            """
            models:
              - description: nameless
                meta:
                  slimtest:
                    unit_tests:
                      - {name: t, given: {u: []}, expect: []}
              - name: real
                meta:
                  slimtest:
                    unit_tests:
                      - {name: t2, given: {u: []}, expect: []}
            """,
        )
        parsed = parse_model_yml(path, tmp_path)
        # Only `real`'s test should be picked up.
        assert [p.model_name for p in parsed] == ["real"]

    def test_duplicate_keys_are_tolerated(self, tmp_path, write_yaml):
        # dbt's loader tolerates duplicate keys; slimtest should too rather
        # than aborting with DuplicateKeyError (issue #2).
        path = write_yaml(
            "models/x.yml",
            """
            models:
              - name: a
                columns:
                  - name: user_id
                    meta:
                      dimension:
                        type: number
                        type: count_distinct
                meta:
                  slimtest:
                    unit_tests:
                      - {name: t, given: {u: []}, expect: []}
            """,
        )
        parsed = parse_model_yml(path, tmp_path)
        assert [p.spec.name for p in parsed] == ["t"]


class TestFindModelYmls:
    def test_missing_dir_returns_empty(self, tmp_path):
        assert find_model_ymls(tmp_path / "nope") == []

    def test_finds_yml_and_yaml(self, tmp_path, write_yaml):
        write_yaml("models/a.yml", "version: 2\n")
        write_yaml("models/b.yaml", "version: 2\n")
        result = find_model_ymls(tmp_path)
        assert {p.name for p in result} == {"a.yml", "b.yaml"}

    def test_recurses_subdirectories(self, tmp_path, write_yaml):
        write_yaml("models/sub/deep/x.yml", "version: 2\n")
        result = find_model_ymls(tmp_path)
        assert any(p.name == "x.yml" for p in result)

    def test_respects_model_paths_arg(self, tmp_path, write_yaml):
        write_yaml("models/x.yml", "")  # default location
        write_yaml("custom/y.yml", "")
        result = find_model_ymls(tmp_path, model_paths=["custom"])
        assert [p.name for p in result] == ["y.yml"]


class TestFindSlimtestTests:
    def test_integration_across_files(self, tmp_path, write_yaml):
        write_yaml(
            "models/a.yml",
            """
            models:
              - name: model_a
                meta:
                  slimtest:
                    unit_tests:
                      - {name: t1, given: {u: []}, expect: []}
            """,
        )
        write_yaml(
            "models/sub/b.yml",
            """
            models:
              - name: model_b
                meta:
                  slimtest:
                    unit_tests:
                      - {name: t2, given: {u: []}, expect: []}
            """,
        )
        tests = find_slimtest_tests(tmp_path)
        names = sorted((t.model_name, t.spec.name) for t in tests)
        assert names == [("model_a", "t1"), ("model_b", "t2")]

    def test_unparseable_unrelated_file_is_skipped(self, tmp_path, write_yaml):
        # A file with no slimtest tests but a scanner-level error (trailing
        # tab, issue #1) must not abort discovery of a valid sibling.
        (tmp_path / "models").mkdir(parents=True, exist_ok=True)
        (tmp_path / "models" / "bad.yml").write_text(
            'version: 2\nmodels:\n  - name: unrelated\n    description: "x"\t\n',
            encoding="utf-8",
        )
        write_yaml(
            "models/good.yml",
            """
            models:
              - name: model_a
                meta:
                  slimtest:
                    unit_tests:
                      - {name: t1, given: {u: []}, expect: []}
            """,
        )
        skipped: list = []
        tests = find_slimtest_tests(tmp_path, skipped_files=skipped)
        assert [t.spec.name for t in tests] == ["t1"]
        assert [p.name for p in skipped] == ["bad.yml"]

    def test_unparseable_slimtest_file_still_raises(self, tmp_path):
        # If the broken file actually declares slimtest tests, we must not
        # silently skip it -- the user needs to fix it.
        (tmp_path / "models").mkdir(parents=True, exist_ok=True)
        (tmp_path / "models" / "bad.yml").write_text(
            "models:\n  - name: a\n    meta:\n      slimtest:\n"
            '        unit_tests: "x"\t\n',
            encoding="utf-8",
        )
        with pytest.raises(InvalidModelYmlError):
            find_slimtest_tests(tmp_path, skipped_files=[])
