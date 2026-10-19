import anthropic
from pydantic import BaseModel, ValidationError

from app.config import get_settings

# On a safety-classifier decline the API re-runs the request on a fallback model
# chosen by refusal category, inside the same call.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AIError(RuntimeError):
    pass


_client: anthropic.AsyncAnthropic | None = None


def client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)
    return _client


async def structured_call[T: BaseModel](
    *, system: str, content: list[dict], output: type[T], effort: str
) -> T:
    """One Claude request whose answer is validated into `output`."""
    settings = get_settings()
    try:
        response = await client().beta.messages.parse(
            model=settings.claude_model,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": content}],
            output_format=output,
            output_config={"effort": effort},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
    except anthropic.APIConnectionError as exc:
        raise AIError("Could not reach the Claude API") from exc
    except anthropic.RateLimitError as exc:
        raise AIError("Claude API rate limit reached, try again shortly") from exc
    except anthropic.APIStatusError as exc:
        raise AIError(f"Claude API error {exc.status_code}: {exc.message}") from exc

    if response.stop_reason == "refusal":
        raise AIError("The model declined to process this board")
    if response.stop_reason == "max_tokens":
        raise AIError("The board was too dense to reconstruct in one pass")
    if response.parsed_output is None:
        raise AIError("The model returned no structured output")
    return response.parsed_output


async def tool_call[T: BaseModel](
    *,
    system: str,
    content: list[dict],
    output: type[T],
    effort: str,
    tool_name: str,
    tool_description: str,
    max_tokens: int = 64000,
) -> T:
    """One Claude request answered through a single tool whose input is validated into `output`.

    For schemas too large for structured outputs (the API rejects their compiled grammar): the
    schema is given as a regular, non-strict tool and the answer is validated with Pydantic
    here instead. Streams, so large answers don't hit request timeouts.
    """
    settings = get_settings()
    tool = {
        "name": tool_name,
        "description": tool_description,
        "input_schema": output.model_json_schema(),
    }
    try:
        async with client().beta.messages.stream(
            model=settings.claude_model,
            max_tokens=max_tokens,
            system=system,
            messages=[
                {
                    "role": "user",
                    "content": [
                        *content,
                        {"type": "text", "text": f"Answer only by calling `{tool_name}` once."},
                    ],
                }
            ],
            tools=[tool],
            tool_choice={"type": "auto"},  # forced tool choice is not available on this model
            output_config={"effort": effort},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        ) as stream:
            response = await stream.get_final_message()
    except anthropic.APIConnectionError as exc:
        raise AIError("Could not reach the Claude API") from exc
    except anthropic.RateLimitError as exc:
        raise AIError("Claude API rate limit reached, try again shortly") from exc
    except anthropic.APIStatusError as exc:
        raise AIError(f"Claude API error {exc.status_code}: {exc.message}") from exc

    if response.stop_reason == "refusal":
        raise AIError("The model declined to process this board")
    if response.stop_reason == "max_tokens":
        raise AIError("The board was too dense to reconstruct in one pass")
    call = next((b for b in response.content if b.type == "tool_use" and b.name == tool_name), None)
    if call is None:
        raise AIError("The model answered without the expected structure")
    try:
        return output.model_validate(call.input)
    except ValidationError as exc:
        raise AIError(f"The model's answer did not match the scene format: {exc}") from exc
