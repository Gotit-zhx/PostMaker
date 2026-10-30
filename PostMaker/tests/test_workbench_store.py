"""本地审核工作台存储测试。"""

from postmaker.workbench.store import WorkbenchStore


def test_workbench_store_keeps_revisions(tmp_path):
    store = WorkbenchStore(str(tmp_path / "workbench.sqlite3"))
    draft = store.create_draft(
        {"id": 7, "title": "素材", "source_url": "https://example.com"},
        "tech", "科技评论家", "初稿标题", "初稿正文", "test-model",
    )
    assert draft["status"] == "pending_review"

    updated = store.update_draft(draft["id"], "修改标题", "修改正文", "approved")
    assert updated["status"] == "approved"
    revisions = store.list_revisions(draft["id"])
    assert len(revisions) == 2

    restored = store.restore_revision(draft["id"], revisions[-1]["id"])
    assert restored["title"] == "初稿标题"
    assert len(store.list_revisions(draft["id"])) == 3
