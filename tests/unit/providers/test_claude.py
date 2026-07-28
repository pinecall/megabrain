"""The Claude Agent SDK backend.

Everything here is offline and needs no `claude-agent-sdk` installed: the SDK is
a constructor-injected seam, the same shape as `OpenAICompatible`'s transport.
A test that needed the real package would be testing Anthropic's shipping, not
this adapter.
"""

from __future__ import annotations

import sys

import pytest

from megabrain._provider_errors import ProviderError
from megabrain.providers.chat import ChatProvider, resolve
from megabrain.providers.chat.claude import ClaudeProvider
from tests.unit.providers.fake_claude import (
    AssistantMessage,
    FakeSDK,
    HangingSDK,
    ResultMessage,
    TextBlock,
    capped,
    delta,
    ping,
)


@pytest.fixture
def opted_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEGABRAIN_CHAT_PROVIDER", "claude")


def _body(*messages: dict[str, object], model: str = "") -> dict[str, object]:
    return {"model": model, "max_tokens": 2400, "temperature": 0,
            "messages": list(messages) or [{"role": "user", "content": "hi"}]}


# ---- streaming --------------------------------------------------------------


def test_the_deltas_concatenate_in_order() -> None:
    sdk = FakeSDK([delta("re"), delta("trie"), delta("val")])
    answer = ClaudeProvider(sdk=sdk).stream_chat(_body())
    assert answer.text == "retrieval"


def test_every_delta_is_delivered_SEPARATELY_as_it_lands() -> None:
    """The Splicer reads deltas to emit live narration. A provider that joined
    them and called back once would stream in name only — and the walkthrough
    would appear all at once, at the end."""
    seen: list[str] = []
    sdk = FakeSDK([delta("a"), delta("b"), delta("c")])
    ClaudeProvider(sdk=sdk).stream_chat(_body(), on_delta=seen.append)
    assert seen == ["a", "b", "c"]


def test_an_event_that_is_not_text_is_ignored_rather_than_parsed() -> None:
    sdk = FakeSDK([ping(), delta("only this"), ping()])
    assert ClaudeProvider(sdk=sdk).stream_chat(_body()).text == "only this"


def test_a_capped_answer_reports_the_openai_finish_reason() -> None:
    """`converse` and `filled` switch on OpenAI's vocabulary. A backend that
    reported the SDK's own word would silently never look truncated."""
    sdk = FakeSDK([delta("cut off here"), capped()])
    assert ClaudeProvider(sdk=sdk).stream_chat(_body()).finish_reason == "length"


def test_a_normal_end_leaves_the_finish_reason_empty() -> None:
    sdk = FakeSDK([delta("complete")])
    assert ClaudeProvider(sdk=sdk).stream_chat(_body()).finish_reason == ""


# ---- the whole-block fallback ----------------------------------------------


def test_a_build_without_partial_messages_still_answers() -> None:
    """Older SDK builds emit no StreamEvent at all. Without this fallback the
    answer would be the empty string and nothing would say why."""
    sdk = FakeSDK([AssistantMessage([TextBlock("whole block")])])
    answer = ClaudeProvider(sdk=sdk).stream_chat(_body())
    assert answer.text == "whole block"


def test_the_fallback_does_NOT_double_count_what_already_streamed() -> None:
    """Both shapes arrive on a modern build: the deltas, then the assembled
    message. Counting both returns every answer twice."""
    sdk = FakeSDK([delta("said once"),
                   AssistantMessage([TextBlock("said once")])])
    assert ClaudeProvider(sdk=sdk).stream_chat(_body()).text == "said once"


# ---- the tool loop ----------------------------------------------------------


def test_this_backend_never_returns_tool_calls() -> None:
    """The documented fail-open in `converse`: a backend with no tool support
    returns its text on the first pass and the loop stops.

    The SDK runs its OWN tool loop, so there is no pending call to hand back —
    reporting one would promise a round trip the narrator cannot complete.
    """
    sdk = FakeSDK([delta("narrated from the material given")])
    assert ClaudeProvider(sdk=sdk).stream_chat(_body()).tool_calls == []


def test_the_builtin_agent_tools_are_denied() -> None:
    """The bundled binary is an AGENT runtime. Left enabled it goes and greps
    the repository instead of narrating — burning the turn, and reaching code
    through something other than megabrain's own retrieval."""
    sdk = FakeSDK([delta("x")])
    ClaudeProvider(sdk=sdk).stream_chat(_body())
    options = sdk.options[0].kwargs
    assert options["allowed_tools"] == []
    for builtin in ("Read", "Grep", "Bash", "WebSearch", "Task"):
        assert builtin in options["disallowed_tools"]


def test_the_prompt_says_no_tools_are_available() -> None:
    """Belt and braces: denying the tools at the transport still let the model
    spend its turn TRYING. Saying so in the prompt is the half that stops it."""
    sdk = FakeSDK([delta("x")])
    ClaudeProvider(sdk=sdk).stream_chat(_body())
    assert "NO tools are available" in sdk.prompts[0]


# ---- translating the transcript --------------------------------------------


def test_the_whole_transcript_reaches_the_prompt() -> None:
    """The narrator re-feeds its full history every round, and `filled` appends
    two plain turns. Dropping any role loses the material the answer needs."""
    sdk = FakeSDK([delta("x")])
    ClaudeProvider(sdk=sdk).stream_chat(_body(
        {"role": "user", "content": "how does indexing work?"},
        {"role": "assistant", "content": "let me look"},
        {"role": "tool", "tool_call_id": "1", "content": "indexer.py L1-20"}))
    prompt = sdk.prompts[0]
    for fragment in ("how does indexing work?", "let me look", "indexer.py L1-20"):
        assert fragment in prompt


def test_an_assistant_turn_with_no_content_does_not_become_the_word_none() -> None:
    """`assistant_turn` sets content to None when the model only called tools.
    Rendered naively that reaches the model as the literal "None"."""
    sdk = FakeSDK([delta("x")])
    ClaudeProvider(sdk=sdk).stream_chat(_body(
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": None, "tool_calls": []}))
    assert "None" not in sdk.prompts[0]


# ---- the model ---------------------------------------------------------------


def test_a_namespaced_openrouter_model_is_not_sent_to_the_cli() -> None:
    """The project default narrator is `google/gemini-3.1-flash-lite`, read from
    `megabrain.json` and meaningless here. Passed through, every narration would
    fail on a model the CLI cannot resolve."""
    sdk = FakeSDK([delta("x")])
    ClaudeProvider(sdk=sdk, model="google/gemini-3.1-flash-lite").stream_chat(_body())
    assert sdk.options[0].kwargs["model"] == "haiku"


def test_an_anthropic_model_passes_through_untouched() -> None:
    sdk = FakeSDK([delta("x")])
    ClaudeProvider(sdk=sdk, model="sonnet").stream_chat(_body())
    assert sdk.options[0].kwargs["model"] == "sonnet"


def test_the_body_model_wins_over_the_constructor() -> None:
    sdk = FakeSDK([delta("x")])
    ClaudeProvider(sdk=sdk, model="haiku").stream_chat(_body(model="opus"))
    assert sdk.options[0].kwargs["model"] == "opus"


# ---- selection ---------------------------------------------------------------


def test_the_sdk_being_installed_is_NOT_enough_to_switch_backends(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Opt-in, deliberately unlike v2's auto-preference.

    A backend that took over because a package happened to be importable would
    move the golden numbers on the machine that installed it, and the developer
    would have no idea which lane produced them.
    """
    monkeypatch.delenv("MEGABRAIN_CHAT_PROVIDER", raising=False)
    assert ClaudeProvider(sdk=FakeSDK()).available() is False


@pytest.mark.usefixtures("opted_in")
def test_opting_in_with_the_sdk_present_makes_it_available() -> None:
    assert ClaudeProvider(sdk=FakeSDK()).available() is True


@pytest.mark.usefixtures("opted_in")
def test_opting_in_without_the_sdk_installed_stays_unavailable(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """`available()` must not lie: the router would pick a backend that cannot
    run, and the failure would arrive at the first ask instead of here."""
    monkeypatch.setattr("megabrain.providers.chat.claude.find_spec",
                        lambda _name: None)
    assert ClaudeProvider().available() is False


@pytest.mark.usefixtures("opted_in")
def test_the_router_prefers_the_sdk_when_it_is_opted_into(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "a-real-key")
    monkeypatch.setattr("megabrain.providers.chat.claude.find_spec",
                        lambda _name: object())
    chosen = resolve()
    assert chosen is not None and chosen.name == "claude"


def test_the_router_falls_back_to_the_endpoint_when_nobody_opted_in(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "a-real-key")
    chosen = resolve()
    assert chosen is not None and chosen.name == "openai-compatible"


@pytest.mark.usefixtures("opted_in")
def test_every_model_lane_follows_the_provider_switch(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """ONE switch, ALL lanes. The judge used to construct its endpoint by name,
    so MEGABRAIN_CHAT_PROVIDER=claude moved the narrator and left rerank,
    expand and the map labels billing OpenRouter — silently, because each was
    fail-open and just kept working."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "a-real-key")
    monkeypatch.setattr("megabrain.providers.chat.claude.find_spec",
                        lambda _name: object())
    from megabrain.enrich.rerank import judge_provider

    chosen = judge_provider()
    assert chosen is not None and chosen.name == "claude"


def test_the_judge_lane_keeps_its_own_timeout(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The judge's timeout is the lane's business — three batches through the
    narrator's settings took 16s for a JSON array of integers. Routing through
    the shared registry must not cost the lane its tuning."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "a-real-key")
    from megabrain.enrich._batches import RERANK_TIMEOUT
    from megabrain.enrich.rerank import RERANK_MODEL, judge_provider

    chosen = judge_provider()
    assert chosen is not None and chosen.name == "openai-compatible"
    assert chosen.model == RERANK_MODEL
    assert chosen.config.timeout == RERANK_TIMEOUT       # type: ignore[attr-defined]


def test_a_lane_timeout_reaches_the_endpoint_but_not_the_subprocess() -> None:
    """A lane timeout is measured on HTTP and means nothing to a backend that
    spawns a CLI: the judge's 30 s is generous for a request and DEAD for a
    subprocess whose start alone eats 14 — observed live, judge=None on every
    call, silently, because the lane fails open. The endpoint takes the lane's
    tuning; the SDK backend keeps its own bound."""
    from megabrain.providers.chat import default_providers
    from megabrain.providers.chat.claude import TIMEOUT as CLAUDE_TIMEOUT

    sdk_lane, endpoint = default_providers(model=None, timeout=7.0)
    assert endpoint.config.timeout == 7.0        # type: ignore[attr-defined]
    assert sdk_lane.timeout == CLAUDE_TIMEOUT    # type: ignore[attr-defined]


def test_the_judge_wall_follows_the_backend() -> None:
    """`verdict_of` bounds each batch with `future.result(timeout=…)`. A wall
    fixed at the HTTP number starves the subprocess backend even after its own
    timeout was set right — the failure observed live."""
    from megabrain.enrich._batches import RERANK_TIMEOUT, wall_for

    assert wall_for(ClaudeProvider(sdk=FakeSDK())) == ClaudeProvider(
        sdk=FakeSDK()).timeout
    class NoTimeout:
        pass
    assert wall_for(NoTimeout()) == RERANK_TIMEOUT   # type: ignore[arg-type]


def test_the_router_carries_the_project_model_to_the_backend() -> None:
    """`resolve()` took no arguments, so routing the narrator through it would
    have silently dropped whatever `megabrain.json` chose."""
    from megabrain.providers.chat import default_providers

    assert default_providers(model="anthropic/x")[-1].model == "anthropic/x"


def test_it_satisfies_the_protocol_structurally() -> None:
    """No base class to inherit: the right shape IS a provider."""
    assert isinstance(ClaudeProvider(sdk=FakeSDK()), ChatProvider)


# ---- failure -----------------------------------------------------------------


def test_an_sdk_failure_surfaces_as_a_provider_error() -> None:
    """Returned as text it becomes part of the walkthrough — which is how an
    outage ends up quoted back to the reader as if the model had said it."""
    sdk = FakeSDK(error=RuntimeError("the CLI exited with 1"))
    with pytest.raises(ProviderError, match="the CLI exited with 1"):
        ClaudeProvider(sdk=sdk).stream_chat(_body())


def test_a_refused_run_reports_the_reason_the_cli_gave() -> None:
    """MEASURED against claude-agent-sdk 0.2.128, and the reason this is here.

    A run the CLI refuses arrives as `ResultMessage(subtype='success',
    is_error=True, result='Credit balance is too low')` — and the SDK then
    raises `Claude Code returned an error result: success`, quoting the
    SUBTYPE. Passed through, the one thing the user can act on ("your credit
    balance") is replaced by the word "success" in an error message.
    """
    sdk = FakeSDK([AssistantMessage([TextBlock("Credit balance is too low")]),
                   ResultMessage(subtype="success", is_error=True,
                                 result="Credit balance is too low")])
    with pytest.raises(ProviderError, match="Credit balance is too low"):
        ClaudeProvider(sdk=sdk).stream_chat(_body())


def test_a_normal_result_message_is_not_mistaken_for_a_failure() -> None:
    """`is_error` is the flag, not `subtype`: every healthy run also ends in a
    `ResultMessage(subtype='success')`, so switching on the subtype would fail
    every call that worked."""
    sdk = FakeSDK([delta("the real answer"), ResultMessage(subtype="success")])
    assert ClaudeProvider(sdk=sdk).stream_chat(_body()).text == "the real answer"


def test_a_refusal_is_not_returned_as_the_walkthrough() -> None:
    """The refusal also arrives as ordinary assistant text. Returned, it becomes
    the answer — which is how an outage gets quoted back to the reader as if the
    model had narrated it."""
    sdk = FakeSDK([AssistantMessage([TextBlock("Credit balance is too low")]),
                   ResultMessage(is_error=True, result="Credit balance is too low")])
    with pytest.raises(ProviderError):
        ClaudeProvider(sdk=sdk).stream_chat(_body())


def test_a_stalled_cli_is_bounded_instead_of_waited_on() -> None:
    """Every call spawns the bundled binary, and it can stall. Unbounded, one
    narration hangs the caller's process with no way back."""
    with pytest.raises(ProviderError, match="timed out"):
        ClaudeProvider(sdk=HangingSDK(), timeout=0.2).stream_chat(_body())


def test_the_missing_package_names_how_to_install_it(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The one error a user can act on themselves.

    The absence is FORCED, never assumed. Written to rely on the extra simply
    not being installed, this test passed on every clean machine and failed the
    moment anyone ran `pip install 'megabrain[claude]'` — a result that depends
    on whose environment ran it, which is exactly what `hermetic_env` exists to
    prevent. A `None` in `sys.modules` is the documented way to fail an import.
    """
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", None)
    with pytest.raises(ProviderError, match=r"megabrain\[claude\]"):
        ClaudeProvider().stream_chat(_body())


# ---- the buffered helper -----------------------------------------------------


def test_chat_text_returns_just_the_answer() -> None:
    sdk = FakeSDK([delta("4"), delta("2")])
    assert ClaudeProvider(sdk=sdk).chat_text("haiku", "six times seven?") == "42"
