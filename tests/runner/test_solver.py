from pathlib import Path

from inspect_ai import eval as inspect_eval

from examiner.runner.solver import transcript_text
from examiner.runner.task import examiner_task
from tests.conftest import free_port


def run(url: str, tmp_path: Path, **kw):
    [log] = inspect_eval(
        examiner_task(pack="smoke", target=url, use_judge=False),
        model="none",
        display="none",
        log_dir=str(tmp_path),
        fail_on_error=False,
        **kw,
    )
    return log


def test_solver_multi_turn_order(bot, tmp_path: Path):
    url, srv = bot
    log = run(url, tmp_path, sample_id="rege-provisional-credit")
    [sample] = log.samples or []
    assert [m.role for m in sample.messages] == ["user", "assistant", "user", "assistant"]
    assert len(srv.calls[1]) == 3
    assert srv.calls[1][1]["role"] == "assistant"


def test_fact_check_scores_end_to_end(bot, tmp_path: Path):
    url, _ = bot
    log = run(url, tmp_path)
    scores = {s.id: s.scores["fact_check"].value for s in log.samples or [] if s.scores}
    assert scores["fees-overdraft-amount"] == "C"
    assert scores["rege-investigation-time"] == "I"
    by_id = {s.id: s for s in log.samples or []}
    meta = by_id["rege-investigation-time"].scores["fact_check"].metadata  # type: ignore[index]
    assert meta == {
        "missing": ["forty-five-days"],
        "forbidden": [],
        "citation": "12 CFR 1005.11(c)(2); 12 CFR 1005.11(c)(3)(ii)",
    }


def test_solver_http_error_marks_sample(tmp_path: Path):
    log = run(f"http://127.0.0.1:{free_port()}", tmp_path, sample_id="fees-nsf")
    [sample] = log.samples or []
    assert sample.error is not None
    assert "target error" in sample.error.message


def test_transcript_text_labels_roles():
    from inspect_ai.model import ChatMessageAssistant, ChatMessageUser

    text = transcript_text([ChatMessageUser(content="hi"), ChatMessageAssistant(content="yo")])
    assert text == "USER: hi\nBOT: yo"


def test_empty_reply_is_target_error(bot, tmp_path: Path):
    url, srv = bot
    srv.reply = lambda msgs: "   "
    log = run(url, tmp_path, sample_id="fees-nsf")
    [sample] = log.samples or []
    assert sample.error is not None and "empty reply" in sample.error.message
