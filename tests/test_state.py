from src.digest import Analysis
from src.fetch_trending import TrendingRepo
from src.state import from_item, load_state, save_state, to_item

REPO = TrendingRepo(owner="foo", name="bar", url="https://github.com/foo/bar",
                    stars=100, description="demo")
AN = Analysis(one_liner="一句话", detail_md="详情", degraded=True)

EMPTY = {"doc_token": None, "doc_url": None, "items": []}


def test_load_state_missing_file_returns_empty(tmp_path):
    assert load_state(tmp_path / "2026-07-28.json") == EMPTY


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "2026-07-28.json"
    state = {"doc_token": "doxcn123", "doc_url": "https://x.feishu.cn/docx/doxcn123",
             "items": [to_item(REPO, AN)]}
    save_state(path, state)
    assert load_state(path) == state


def test_load_state_legacy_list_format(tmp_path):
    # 旧格式为纯 list, 需兼容
    path = tmp_path / "2026-07-28.json"
    path.write_text('[{"id": "foo/bar"}]', encoding="utf-8")
    state = load_state(path)
    assert state["items"] == [{"id": "foo/bar"}]
    assert state["doc_token"] is None and state["doc_url"] is None


def test_item_roundtrip():
    repo, analysis = from_item(to_item(REPO, AN))
    assert repo == REPO
    assert analysis == AN


def test_item_id_is_full_name():
    assert to_item(REPO, AN)["id"] == "foo/bar"
