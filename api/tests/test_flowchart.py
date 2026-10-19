"""Flowcharts read as algorithms (fictional charts, built directly as scenes)."""

from app.ai.summarize import language_instruction, mock_summary
from app.flowchart import analyze, board_reading
from app.models import Board, Lesson
from app.scene import Scene


def geo(id, geo, label, x, y, w=100, h=40):
    return {"kind": "geo", "id": id, "geo": geo, "label": label, "x": x, "y": y, "w": w, "h": h}


def text(id, t, x, y, w=60, h=20):
    return {"kind": "text", "id": id, "text": t, "x": x, "y": y, "w": w, "h": h}


def arrow(a, b, label=""):
    return {"kind": "connector", "id": f"{a}>{b}", "from_id": a, "to_id": b, "label": label,
            "x1": 0, "y1": 0, "x2": 0, "y2": 0}  # fmt: skip


def scene(*elements):
    return Scene.model_validate({"elements": list(elements)})


COUNT_UP = scene(
    text("title", "Add by counting", 0, 0, 200),
    geo("s", "ellipse", "Start", 0, 40),
    geo("in", "trapezoid", "A, B", 0, 120),
    geo("init", "rectangle", "result = A", 0, 200),
    geo("d", "diamond", "repeat B times", 0, 280, 100, 60),
    text("t", "T", 60, 345, 20),  # label drawn next to the arrow, not on it
    geo("inc", "rectangle", "result + 1", 0, 380),
    geo("out", "trapezoid", "result", 200, 380),
    geo("e", "ellipse", "End", 200, 460),
    arrow("s", "in"), arrow("in", "init"), arrow("init", "d"),
    arrow("d", "inc"), arrow("inc", "d"), arrow("d", "out"), arrow("out", "e"),
)  # fmt: skip


def test_loop_is_structured_with_title_and_side_label():
    (chart,) = analyze(COUNT_UP)
    assert chart.title == "Add by counting"
    assert chart.lines == [
        "  START",
        "  INPUT A, B",
        "  result = A",
        "  REPEAT while “repeat B times” (on T):",
        "    result + 1",
        "  OUTPUT result",
        "  END",
    ]
    assert chart.describe() == (
        "“Add by counting”: takes A, B, starts with result = A, repeats result + 1 while "
        "“repeat B times”, gives result."
    )


def test_branches_meet_again_at_a_merge_point():
    s = scene(
        geo("s", "ellipse", "Почетак", 100, 0),
        geo("d", "diamond", "x > 0", 100, 80),
        geo("a", "rectangle", "positive", 0, 180),
        geo("b", "rectangle", "not positive", 200, 180),
        geo("m", "ellipse", "", 130, 260, 20, 20),
        geo("e", "ellipse", "Крај", 100, 320),
        arrow("s", "d"), arrow("d", "a", "Да"), arrow("d", "b", "Не"),
        arrow("a", "m"), arrow("b", "m"), arrow("m", "e"),
    )  # fmt: skip
    (chart,) = analyze(s)
    assert chart.lines == [
        "  START",
        "  IF “x > 0”:",
        "    [Да]:",
        "      positive",
        "    [Не]:",
        "      not positive",
        "  END",
    ]


def test_joined_shapes_are_one_unit_and_unfinished_charts_are_flagged():
    s = scene(
        geo("s", "ellipse", "Start", 0, 0),
        geo("in", "trapezoid", "number", 0, 100),
        geo("u1", "rectangle", "last digit", 0, 140),  # touching: one unit, read top-down
        geo("u2", "rectangle", "drop last digit", 0, 180),
        arrow("s", "u1"),
    )
    (chart,) = analyze(s)
    assert "UNIT (shapes joined together on the board, read in order):" in chart.text()
    assert chart.inputs == ["number"]
    assert not chart.complete


def test_boxes_called_and_returning_are_recursive_calls():
    s = scene(
        geo("s", "ellipse", "Start", 0, 0),
        geo("r3", "rectangle", "f (2)", 0, 100),
        geo("e", "ellipse", "End", 0, 400),
        geo("box2", "rectangle", "", 200, 50, 160, 200),
        geo("b1", "rectangle", "work", 210, 60),
        geo("r2", "rectangle", "f (1)", 210, 120),
        geo("box1", "rectangle", "", 400, 50, 160, 200),
        geo("b2", "rectangle", "work", 410, 60),
        geo("b3", "rectangle", "base case", 410, 120),
        arrow("s", "r3"), arrow("r3", "box2"), arrow("box2", "r3"), arrow("r3", "e"),
        arrow("r2", "box1"), arrow("b3", "r2"),
    )  # fmt: skip
    (chart,) = analyze(s)
    assert chart.calls == ["f (2)", "f (1)"]
    assert "calls “f” recursively" in chart.describe()


def test_graphs_are_not_mistaken_for_algorithms():
    s = scene(
        geo("1", "ellipse", "1", 0, 0, 30, 30),
        geo("2", "ellipse", "2", 100, 0, 30, 30),
        geo("3", "ellipse", "3", 50, 80, 30, 30),
        arrow("1", "2"), arrow("2", "3"), arrow("1", "3"),
    )  # fmt: skip
    assert analyze(s) == []
    assert "1 -> 2" in board_reading(s)


def test_offline_recap_describes_algorithms_not_labels():
    lesson = Lesson(title="Counting", subject="Programming", notes="")
    lesson.boards = [Board(scene=COUNT_UP.model_dump())]
    summary = mock_summary(lesson, "Ana")
    assert summary.key_points[0].startswith("“Add by counting”: takes A, B")
    assert "algorithm" in summary.recap_message
    assert "A, B" in summary.review_suggestions[0]


def test_entity_relationship_diagrams_are_not_algorithms():
    from app.flowchart import analyze_er

    s = scene(
        geo("room", "rectangle", "Room", 0, 0),
        geo("rel", "diamond", "is of type", 200, 0, 80, 80),
        geo("type", "rectangle", "Room types", 400, 0),
        geo("place", "rectangle", "Accommodation", 0, 200),
        arrow("room", "rel"), arrow("rel", "type"), arrow("room", "place"),
    )  # fmt: skip
    assert analyze(s) == []
    (er,) = analyze_er(s)
    assert er.relations == ["Room —[is of type]→ Room types", "Room → Accommodation"]
    assert "Entity-relationship diagram" in board_reading(s)


def test_serbian_recaps_are_written_in_cyrillic():
    assert "Cyrillic" in language_instruction("Serbian")
    assert "Cyrillic" in language_instruction(" serbian ")
    assert language_instruction("English") == "English"
