from __future__ import annotations

from shawei.services.duplicate_check import Site, find_existing_site


EXISTING = [
    Site(
        "动态文章",
        "https://example.test:29444/article/admin/6a2d8e27d164c1deb62446cd?url=gsw",
        "bottom",
    ),
    Site("主题文章", "https://forum.test:16677/topic/273012.html", "top"),
]


def test_same_dynamic_article_id_cannot_reenter_through_manager_route() -> None:
    existing = find_existing_site(
        "换名文章",
        "https://example.test:29444/article/manager/6a2d8e27d164c1deb62446cd?url=other",
        EXISTING,
    )

    assert existing == EXISTING[0]


def test_same_topic_id_ignores_non_identity_query_and_fragment() -> None:
    existing = find_existing_site(
        "换名主题",
        "https://forum.test:16677/topic/273012.html?from=list#reply",
        EXISTING,
    )

    assert existing == EXISTING[1]


def test_same_numeric_id_on_another_host_is_not_the_same_site() -> None:
    assert (
        find_existing_site(
            "另一来源",
            "https://mirror.test:16677/topic/273012.html",
            EXISTING,
        )
        is None
    )


def test_different_article_id_on_same_host_is_not_the_same_site() -> None:
    assert (
        find_existing_site(
            "另一文章",
            "https://example.test:29444/article/admin/another-id?url=gsw",
            EXISTING,
        )
        is None
    )


def test_same_static_article_id_ignores_tracking_query() -> None:
    sites = [
        Site(
            "静态文章",
            "https://static.test:1888/Article/ar_content/id/1556/tid/82.html",
            "top",
        )
    ]

    assert (
        find_existing_site(
            "换名静态文章",
            "https://static.test:1888/Article/ar_content/id/1556/tid/99.html?from=list",
            sites,
        )
        == sites[0]
    )


def test_same_query_record_id_requires_the_same_endpoint() -> None:
    sites = [Site("论坛文章", "https://forum.test/read.php?tid=528", "bottom")]

    assert (
        find_existing_site(
            "换名论坛文章",
            "https://forum.test/read.php?from=list&tid=528",
            sites,
        )
        == sites[0]
    )
    assert (
        find_existing_site(
            "另一端点",
            "https://forum.test/view.php?id=528",
            sites,
        )
        is None
    )


def test_root_url_trailing_slash_cannot_bypass_duplicate_identity() -> None:
    sites = [Site("根站", "https://root.test/", "top")]

    assert find_existing_site("换名根站", "https://ROOT.test", sites) == sites[0]


def test_same_spa_user_or_forum_identity_cannot_reenter_with_route_variants() -> None:
    sites = [
        Site("用户页", "https://spa.test/#/users/1203", "top"),
        Site("论坛页", "https://spa.test/#/forums/15340352", "bottom"),
        Site(
            "引用页",
            "https://spa.test/#/users/4606/references/15339511",
            "top",
        ),
    ]

    assert (
        find_existing_site("换名用户", "https://spa.test#/users/1203/", sites)
        == sites[0]
    )
    assert (
        find_existing_site("换名论坛", "https://spa.test/#/forums/15340352/", sites)
        == sites[1]
    )
    assert (
        find_existing_site(
            "换名引用",
            "https://spa.test/#/users/4606/references/15339511/",
            sites,
        )
        == sites[2]
    )
