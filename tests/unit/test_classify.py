from healer.classify import classify
from healer.models import Change, Classification, TestResult

OK = TestResult("t.py::test_ok", "t.py", "test_ok", "passed")
FAIL_USERS = TestResult("t.py::test_users", "t.py", "test_users", "failed", "assert 404 == 200")
FAIL_OTHER = TestResult("t.py::test_other", "t.py", "test_other", "failed", "KeyError")
CONN = TestResult("t.py::test_users", "t.py", "test_users", "failed", "httpx.ConnectError: nope")
ENDPOINTS = {"t.py::test_users": {("GET", "/users")}, "t.py::test_other": {("GET", "/other")}}
USERS_CHANGE = Change("C1", "status_changed", "GET", "/users", old=200, new=201)


def verdict(**overrides: object) -> Classification:
    args: dict[str, object] = {
        "spec_error": None,
        "exit_code": 1,
        "results": [OK, FAIL_USERS],
        "changes": [USERS_CHANGE],
        "endpoints_by_test": ENDPOINTS,
    }
    args.update(overrides)
    return classify(**args).classification  # type: ignore[arg-type]


def test_spec_change() -> None:
    assert verdict() is Classification.SPEC_CHANGE


def test_path_level_change_matches_any_method() -> None:
    rename = Change("C1", "path_renamed", None, "/users", None, "/users", "/people")
    assert verdict(changes=[rename]) is Classification.SPEC_CHANGE


def test_pass_even_with_changes() -> None:
    assert verdict(exit_code=0, results=[OK]) is Classification.PASS


def test_regression_without_changes() -> None:
    assert verdict(changes=[]) is Classification.REGRESSION


def test_regression_when_a_failure_is_unrelated() -> None:
    assert verdict(results=[FAIL_USERS, FAIL_OTHER]) is Classification.REGRESSION


def test_environment_failures() -> None:
    assert verdict(spec_error="down") is Classification.ENVIRONMENT_FAILURE
    assert verdict(results=[CONN]) is Classification.ENVIRONMENT_FAILURE


def test_unknown_when_pytest_crashes_or_reports_nothing() -> None:
    assert verdict(exit_code=2) is Classification.UNKNOWN
    assert verdict(exit_code=0, results=[]) is Classification.UNKNOWN
