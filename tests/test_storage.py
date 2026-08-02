"""Regression tests for storage.totals_per_mod()'s reply split.

The replies/thread_replies distinction was fixed in Phase 2: ``replies``
counts comments whose parent comment was authored by the tracked member,
while ``thread_replies`` keeps the raw nested count.
"""


def _seed_basic(db):
    mid = db.upsert_mod("my-mod", "https://www.moddb.com/mods/my-mod", "My Mod")
    db.add_snapshot(mid, downloads_total=1000, downloads_today=10)
    return mid


def test_reply_split_with_tracked_member(db):
    mid = _seed_basic(db)
    db.meta_set("member_name", "CodeBySherwan")
    db.meta_set("member_name_id", "codesherwan")

    db.add_comment(1, mid, "CodeBySherwan", "hello", "2025-01-01T10:00:00", 0, None)
    # direct reply to the tracked member -> counted
    db.add_comment(2, mid, "Fan", "nice work", "2025-01-01T10:01:00", 0, 1)
    # nested reply to a fan, not to the member -> thread_replies only
    db.add_comment(3, mid, "Fan2", "agreed", "2025-01-01T10:02:00", 0, 2)
    # top-level comment that merely mentions the member -> not a reply
    db.add_comment(4, mid, "Fan3", "thanks CodeBySherwan, great mod", "2025-01-01T10:03:00", 0, None)

    t = {r["id"]: r for r in db.totals_per_mod()}[mid]
    assert t["comments"] == 4
    assert t["replies"] == 1
    assert t["thread_replies"] == 2


def test_reply_matching_uses_member_id_alias(db):
    mid = _seed_basic(db)
    db.meta_set("member_name_id", "codesherwan")
    db.add_comment(1, mid, "codesherwan", "op", "2025-01-01T10:00:00", 0, None)
    db.add_comment(2, mid, "Fan", "to you", "2025-01-01T10:01:00", 0, 1)
    t = {r["id"]: r for r in db.totals_per_mod()}[mid]
    assert t["replies"] == 1


def test_no_member_names_replies_zero(db):
    mid = _seed_basic(db)
    db.add_comment(1, mid, "Fan", "hi", "2025-01-01T10:00:00", 0, None)
    db.add_comment(2, mid, "Fan2", "yo", "2025-01-01T10:01:00", 0, 1)
    t = db.totals_per_mod()[0]
    assert t["replies"] == 0
    assert t["thread_replies"] == 1
