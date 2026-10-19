"""tool_call against a fake client: no network, no cost."""

import asyncio
from types import SimpleNamespace

import pytest

from app.ai import claude
from app.ai.claude import AIError, tool_call
from app.ai.vision import VisionScene

GOOD = {
    "title": "Arrays",
    "transcript": "1 2",
    "elements": [
        {"kind": "note", "id": "n", "x": 1, "y": 2, "side": 30, "text": "1", "color": "yellow"}
    ],
}


class FakeStream:
    def __init__(self, message):
        self.message = message

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get_final_message(self):
        return self.message


def fake_client(monkeypatch, message, seen=None):
    def stream(**kwargs):
        if seen is not None:
            seen.update(kwargs)
        return FakeStream(message)

    fake = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=stream)))
    monkeypatch.setattr(claude, "client", lambda: fake)


def run(**overrides):
    kwargs = dict(
        system="s",
        content=[{"type": "text", "text": "x"}],
        output=VisionScene,
        effort="high",
        tool_name="record_board",
        tool_description="d",
    )
    return asyncio.run(tool_call(**(kwargs | overrides)))


def message(stop_reason="tool_use", tool_input=GOOD, name="record_board"):
    block = SimpleNamespace(type="tool_use", name=name, input=tool_input)
    return SimpleNamespace(stop_reason=stop_reason, content=[block])


def test_validates_tool_input(monkeypatch):
    seen = {}
    fake_client(monkeypatch, message(), seen)
    scene = run()
    assert scene.elements[0].text == "1"
    assert seen["tools"][0]["name"] == "record_board"
    assert seen["tool_choice"] == {"type": "auto"}
    assert seen["max_tokens"] == 64000


@pytest.mark.parametrize(
    ("msg", "error"),
    [
        (message(stop_reason="refusal"), "declined"),
        (message(stop_reason="max_tokens"), "too dense"),
        (message(name="other"), "expected structure"),
        (message(tool_input={"title": "x"}), "did not match"),
    ],
)
def test_reports_failures(monkeypatch, msg, error):
    fake_client(monkeypatch, msg)
    with pytest.raises(AIError, match=error):
        run()
