import json

from ensemblitz import news as N


def _write(tmp_path, items):
    p = tmp_path / "w.json"
    p.write_text(json.dumps(items))
    return p


def test_hostile_urls_are_dropped(tmp_path):
    base = {"team": "HOU", "player": "A B", "status": "out"}
    bad = [
        "javascript:alert(1)",
        "data:text/html,x",
        "http://x.com/a",
        "https://evil.example/x",
        "https://x.com.evil.example/a",
        "https://user@x.com/a",
        5,
        None,
    ]
    items = N.load_news(_write(tmp_path, [{**base, "source_url": u} for u in bad]))
    assert all(i["source_url"] is None for i in items)
    ok = N.load_news(
        _write(tmp_path, [{**base, "source_url": "https://x.com/AdamSchefter/status/1"}])
    )
    assert ok[0]["source_url"].startswith("https://x.com/")


def test_malformed_items_do_not_crash(tmp_path):
    base = {"team": "HOU", "player": "A B", "status": "out"}
    items = N.load_news(
        _write(
            tmp_path,
            [
                {**base, "posted_at": "2026-11-17 18:00"},
                {**base, "posted_at": 12},
                {**base, "player": ["x"]},
                base,
            ],
        )
    )
    assert len(items) == 1
    (tmp_path / "bad.json").write_text("{not json")
    assert N.load_news(tmp_path / "bad.json") == []
