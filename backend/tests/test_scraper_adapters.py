"""Tests for the site adapter system (generic + YAML loader)."""

from __future__ import annotations

from pathlib import Path

import pytest

from alejandria.services.scraper.adapters.generic import GenericAdapter
from alejandria.services.scraper.adapters.loader import (
    YamlAdapter,
    compile_yaml_adapters,
    load_yaml_adapters,
)


def test_generic_matches_everything():
    g = GenericAdapter()
    assert g.matches("https://example.com/foo")
    assert g.matches("http://localhost/")


def test_yaml_adapter_compile_and_match(tmp_path: Path):
    yaml_file = tmp_path / "adapters.yaml"
    yaml_file.write_text(
        """
adapters:
  - name: foo
    url_regex: '^https?://foo\\.example/series/'
    image_selector: "div.reader img"
    next_selector: "a.next"
    pagination_style: click
    delay_ms_between_requests: 600
"""
    )
    raw = load_yaml_adapters(yaml_file)
    assert len(raw) == 1
    assert raw[0].name == "foo"
    assert raw[0].delay_ms_between_requests == 600

    compiled = compile_yaml_adapters(raw)
    assert len(compiled) == 1
    a = compiled[0]
    assert a.name == "yaml:foo"
    assert a.matches("https://foo.example/series/abc/1")
    assert not a.matches("https://other.example/series/abc/1")


def test_missing_file_returns_empty(tmp_path: Path):
    out = load_yaml_adapters(tmp_path / "does-not-exist.yaml")
    assert out == []


def test_invalid_yaml_raises(tmp_path: Path):
    yaml_file = tmp_path / "adapters.yaml"
    yaml_file.write_text("not: [valid: yaml")
    with pytest.raises(ValueError):
        load_yaml_adapters(yaml_file)


def test_missing_required_key_raises(tmp_path: Path):
    yaml_file = tmp_path / "adapters.yaml"
    yaml_file.write_text("adapters:\n  - image_selector: img\n")
    with pytest.raises(ValueError):
        load_yaml_adapters(yaml_file)


def test_yaml_adapter_match_logic():
    raw = YamlAdapter(
        name="x", url_regex=r"^https://x\.example/\d+/$", pagination_style="url_increment"
    )
    rt = compile_yaml_adapters([raw])[0]
    assert rt.matches("https://x.example/42/")
    assert not rt.matches("https://y.example/42/")
