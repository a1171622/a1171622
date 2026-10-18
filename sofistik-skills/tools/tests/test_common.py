import json

from _util import TOOLS, dump, tmpdir  # noqa: F401
import _common as K


def test_unwrap_shapes():
    core = {"lc": 1, "rows": [{"node": 1}]}
    assert K.unwrap(core) == core
    assert K.unwrap({"result": core}) == core
    assert K.unwrap({"structuredContent": core, "isError": False}) == core
    assert K.unwrap([{"type": "text", "text": json.dumps(core)}]) == core
    assert K.unwrap({"content": [{"type": "text", "text": json.dumps(core)}], "isError": False}) == core


def test_load_json_tolerates_bom_and_fence():
    d = tmpdir()
    p = d + "/x.json"
    with open(p, "w", encoding="utf-8") as f:
        f.write("﻿```json\n{\n  \"rows\": [ {\"lc\": 2} ]\n}\n```\n")
    assert K.rows_of(K.load_json(p), p) == [{"lc": 2}]


def test_need_never_defaults():
    for d in ({}, {"a": None}):
        try:
            K.need(d, "a", "x")
            raise AssertionError("need() must raise")
        except K.MissingField:
            pass


def test_parse_ids():
    assert K.parse_ids("1-3, 7") == [1, 2, 3, 7]
    assert K.parse_ids("(101 105 2)") == [101, 103, 105]
    assert K.parse_ids([5, "8-9"]) == [5, 8, 9]


def test_rows_of_raises_on_tool_error():
    try:
        K.rows_of({"error": "No beam results"}, "x")
        raise AssertionError("must raise")
    except K.MissingField as e:
        assert "No beam results" in str(e)
