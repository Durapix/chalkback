import anthropic
from pydantic import BaseModel

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
