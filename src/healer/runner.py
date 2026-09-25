"""Run the API test suite in a subprocess and collect per-test results."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from healer.models import TestResult


@dataclass
class SuiteRun:
    exit_code: int
    results: list[TestResult]
    output: str

    @property
    def passed(self) -> bool:
        return self.exit_code == 0 and all(result.ok for result in self.results)


def run_suite(tests_dir: Path, base_url: str, timeout: float = 600.0) -> SuiteRun:
    """Run pytest on ``tests_dir`` against ``base_url``."""
    with tempfile.TemporaryDirectory(prefix="healer-junit-") as tmp:
        junit = Path(tmp) / "junit.xml"
        ini = Path(tmp) / "pytest.ini"
        ini.write_text("[pytest]\n", encoding="utf-8")
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(tests_dir),
            "-q",
            "-p",
            "no:cacheprovider",
            "-c",
            str(ini),
            "--rootdir",
            str(tests_dir),
            f"--junitxml={junit}",
            "-o",
            "junit_family=xunit1",
        ]
        env = {**os.environ, "API_BASE_URL": base_url, "PYTHONDONTWRITEBYTECODE": "1"}
        proc = subprocess.run(
            cmd, capture_output=True, text=True, env=env, timeout=timeout, check=False
        )
        results = parse_junit(junit.read_text(encoding="utf-8")) if junit.exists() else []
    return SuiteRun(proc.returncode, results, proc.stdout + proc.stderr)


def parse_junit(xml_text: str) -> list[TestResult]:
    root = ET.fromstring(xml_text)
    results: list[TestResult] = []
    for case in root.iter("testcase"):
        file = case.get("file") or (case.get("classname", "").replace(".", "/") + ".py")
        name = case.get("name", "")
        outcome, message = "passed", ""
        for tag in ("failure", "error", "skipped"):
            node = case.find(tag)
            if node is not None:
                outcome = {"failure": "failed", "error": "error", "skipped": "skipped"}[tag]
                message = (node.get("message") or node.text or "").strip()
                break
        results.append(TestResult(f"{file}::{name}", file, name, outcome, message[:2000]))
    return sorted(results, key=lambda r: r.nodeid)
