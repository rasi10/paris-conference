"""Assign exactly one classification to a run (constitution: Run Classification & Outcomes)."""

from __future__ import annotations

from dataclasses import dataclass

from healer.models import Change, Classification, TestResult

CONNECTION_MARKERS = ("ConnectError", "ConnectTimeout", "Connection refused", "ReadTimeout")


@dataclass(frozen=True)
class Verdict:
    classification: Classification
    reason: str


def is_connection_failure(result: TestResult) -> bool:
    return any(marker in result.message for marker in CONNECTION_MARKERS)


def touches(change: Change, endpoints: set[tuple[str, str]]) -> bool:
    return any(
        path == change.path and (change.method is None or method == change.method)
        for method, path in endpoints
    )


def classify(
    *,
    spec_error: str | None,
    exit_code: int | None,
    results: list[TestResult],
    changes: list[Change],
    endpoints_by_test: dict[str, set[tuple[str, str]]],
) -> Verdict:
    """Classify a run from the spec fetch outcome, the first suite run and the spec diff.

    ``endpoints_by_test`` maps a test's nodeid to the ``(METHOD, path template)`` pairs it calls.
    """
    if spec_error is not None:
        return Verdict(
            Classification.ENVIRONMENT_FAILURE, f"Specification unavailable: {spec_error}"
        )
    if exit_code not in (0, 1) or not results:
        return Verdict(
            Classification.UNKNOWN,
            f"The test run did not complete normally (pytest exit code {exit_code}, "
            f"{len(results)} results)",
        )
    failing = [r for r in results if not r.ok]
    if not failing:
        return Verdict(Classification.PASS, "All tests passed")
    if all(is_connection_failure(r) for r in failing):
        return Verdict(
            Classification.ENVIRONMENT_FAILURE,
            f"{len(failing)} test(s) could not reach the API",
        )
    if not changes:
        return Verdict(
            Classification.REGRESSION,
            f"{len(failing)} test(s) fail and the specification has not changed: "
            "the API no longer matches its own specification",
        )
    unrelated = [
        r.nodeid
        for r in failing
        if not any(touches(c, endpoints_by_test.get(r.nodeid, set())) for c in changes)
    ]
    if unrelated:
        return Verdict(
            Classification.REGRESSION,
            "Failing test(s) not explained by any specification change: " + ", ".join(unrelated),
        )
    return Verdict(
        Classification.SPEC_CHANGE,
        f"{len(failing)} failing test(s), all calling endpoints touched by "
        f"{len(changes)} detected specification change(s)",
    )
