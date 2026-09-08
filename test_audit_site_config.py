from __future__ import annotations

import json

import pytest

from shawei.config.sites import load_sites


def test_load_sites_requires_the_requested_json_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        load_sites(tmp_path / "missing.json")


def test_load_sites_rejects_malformed_json(tmp_path) -> None:
    path = tmp_path / "sites.json"
    path.write_text("not json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        load_sites(path)


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        [{"name": "", "url": "https://example.test", "pick": "top"}],
        [{"name": "站点", "url": "", "pick": "top"}],
        [{"name": "站点", "url": "https://example.test"}],
        [{"name": "站点", "url": "https://example.test", "pick": "middle"}],
        [{"name": "站点", "url": "https://example.test", "pick": "buttom"}],
        [
            {
                "name": "站点",
                "url": "https://example.test",
                "pick": "top",
                "archived": "false",
            }
        ],
    ],
)
def test_load_sites_rejects_empty_or_invalid_formal_configuration(tmp_path, payload) -> None:
    path = tmp_path / "sites.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError):
        load_sites(path)


def test_load_sites_keeps_valid_active_rows_and_skips_archived_rows(tmp_path) -> None:
    path = tmp_path / "sites.json"
    path.write_text(
        json.dumps(
            [
                {"name": "活动站", "url": "https://active.test/topic/1.html", "pick": "bottom"},
                {
                    "name": "封存站",
                    "url": "https://archived.test/topic/2.html",
                    "pick": "top",
                    "archived": True,
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    sites = load_sites(path)

    assert [(site.name, site.url, site.pick) for site in sites] == [
        ("活动站", "https://active.test/topic/1.html", "bottom")
    ]
