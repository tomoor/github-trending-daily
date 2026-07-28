from src.digest import Analysis
from src.fetch_trending import TrendingRepo
from src.state import from_item, load_state, save_state, to_item

REPO = TrendingRepo(owner="foo", name="bar", url="https://github.com/foo/bar",
                    stars=100, description="demo")
AN = Analysis(one_liner="一句话", detail_md="详情", degraded=True)


def test_load_state_missing_file_returns_empty(tmp_path):
    assert load_state(tmp_path / "2026-07-28.json") == []


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "2026-07-28.json"
    items = [to_item(REPO, AN)]
    save_state(path, items)
    assert load_state(path) == items


def test_item_roundtrip():
    repo, analysis = from_item(to_item(REPO, AN))
    assert repo == REPO
    assert analysis == AN


def test_item_id_is_full_name():
    assert to_item(REPO, AN)["id"] == "foo/bar"
