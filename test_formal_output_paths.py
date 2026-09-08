from __future__ import annotations

from pathlib import Path

from shawei.config import paths
from shawei.persistence import txt_writer
from shawei.services import consecutive_duplicates, multi_period


PROJECT_ROOT = Path(__file__).resolve().parent


def test_formal_output_paths_resolve_under_crawler_collection() -> None:
    output_root = PROJECT_ROOT.parent

    assert paths.ROOT_DIR == PROJECT_ROOT
    assert paths.OUTPUT_DIR == output_root / "七类数据统一归纳"
    assert paths.FAIL_OUTPUT_DIR == output_root / "七类数据统一归纳失败"


def test_output_consumers_share_paths_without_formal_writes(tmp_path, monkeypatch) -> None:
    assert txt_writer.OUTPUT_DIR == paths.OUTPUT_DIR
    assert txt_writer.FAIL_OUTPUT_DIR == paths.FAIL_OUTPUT_DIR
    assert multi_period.FAIL_OUTPUT_DIR == paths.FAIL_OUTPUT_DIR
    assert consecutive_duplicates.OUTPUT_DIR == paths.OUTPUT_DIR

    test_success_dir = tmp_path / "success"
    test_failure_dir = tmp_path / "failure"
    monkeypatch.setattr(txt_writer, "OUTPUT_DIR", test_success_dir)
    monkeypatch.setattr(txt_writer, "FAIL_OUTPUT_DIR", test_failure_dir)

    assert txt_writer.resolve_success_path("227期-尾.txt") == test_success_dir / "227期-尾.txt"
    assert txt_writer.resolve_failure_path("227期-尾-失败.txt") == test_failure_dir / "227期-尾-失败.txt"
    assert list(test_success_dir.iterdir()) == []
    assert list(test_failure_dir.iterdir()) == []
