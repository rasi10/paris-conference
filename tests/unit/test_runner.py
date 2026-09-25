from healer.runner import parse_junit

JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="3">
  <testcase classname="test_users" name="test_b" file="test_users.py" line="3" />
  <testcase classname="test_users" name="test_a" file="test_users.py" line="1">
    <failure message="assert 404 == 200">long trace</failure>
  </testcase>
  <testcase classname="test_x" name="test_c" file="test_x.py" line="1">
    <error message="fixture failed" />
  </testcase>
</testsuite></testsuites>"""


def test_parse_junit_outcomes_sorted_by_nodeid() -> None:
    results = parse_junit(JUNIT)
    assert [r.nodeid for r in results] == [
        "test_users.py::test_a",
        "test_users.py::test_b",
        "test_x.py::test_c",
    ]
    assert [r.outcome for r in results] == ["failed", "passed", "error"]
    assert results[0].message == "assert 404 == 200"
    assert not results[0].ok
    assert results[1].ok
