"""Regression tests for tracker.classify_comment() and member_names().

classify_comment was narrowed in the next-fixes round: the structural
parent-author signal is trusted first, and the username-mention fallback only
fires when the parent comment's author is unknown (blank). A top-level comment
that merely mentions the tracked username must not count as a reply.
"""

from tracker import classify_comment, member_names

NAMES = ["codebysherwan", "codesherwan"]


def _c(parent_author=None, content=""):
    return {"parent_author": parent_author, "content": content}


def test_reply_when_parent_author_is_member():
    assert classify_comment(_c(parent_author="CodeBySherwan", content="x"), NAMES) == "reply"


def test_reply_when_parent_author_is_member_id():
    assert classify_comment(_c(parent_author="codesherwan"), NAMES) == "reply"


def test_top_level_mention_is_not_a_reply():
    # Parent author present but not a member: a mention in the text is just a
    # shout-out, not a reply (this was the over-broad behavior being fixed).
    assert classify_comment(_c(parent_author="AnotherUser", content="thanks CodeBySherwan!"), NAMES) == "comment"


def test_blank_parent_author_still_uses_demoted_fallback():
    assert classify_comment(_c(parent_author=None, content="thanks codesherwan"), NAMES) == "reply"


def test_plain_comments_are_comments():
    assert classify_comment(_c(parent_author="AnotherUser", content="hello"), NAMES) == "comment"
    assert classify_comment(_c(parent_author=None, content="hello"), NAMES) == "comment"
    assert classify_comment(_c(parent_author=None, content=""), NAMES) == "comment"


def test_member_names_normalises_whitespace_and_case(db):
    db.meta_set("member_name", "  CodeBySherwan  ")
    db.meta_set("member_name_id", "codesherwan")
    assert member_names(db) == ["codebysherwan", "codesherwan"]
