from living_vault.core.graph import extract_wikilinks


def test_extract_wikilinks_single():
    body = "see [[wiki/concepts/foo]] and [[wiki/concepts/bar]]."
    links = extract_wikilinks(body)
    assert ("wiki/concepts/foo", None) in links
    assert ("wiki/concepts/bar", None) in links


def test_extract_wikilinks_with_alias():
    body = "see [[wiki/synthesis/abc|the synthesis]]"
    links = extract_wikilinks(body)
    assert ("wiki/synthesis/abc", "the synthesis") in links


def test_extract_wikilinks_ignores_non_wiki():
    body = "[[foo]] is not a wiki link, but [[wiki/x]] is."
    links = extract_wikilinks(body)
    targets = [t for t, _ in links]
    assert "wiki/x" in targets
    assert "foo" not in targets


def test_extract_wikilinks_dedup():
    body = "[[wiki/a]] and again [[wiki/a]]."
    links = extract_wikilinks(body)
    assert links.count(("wiki/a", None)) == 2  # not deduped at this level


from living_vault.core.graph import resolve_target


def test_resolve_target_strips_wiki_prefix():
    assert resolve_target("wiki/concepts/note-a") == "concepts/note-a.md"


def test_resolve_target_passes_md_extension_through():
    assert resolve_target("wiki/concepts/note-a.md") == "concepts/note-a.md"


def test_resolve_target_returns_none_for_non_wiki():
    assert resolve_target("concepts/note-a") is None
