import polars as pl

from pipeline import frames


def test_memo_rebuilds_when_code_version_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(frames, "FRAMES", tmp_path)
    calls = []

    def build():
        calls.append(1)
        return pl.DataFrame({"x": [len(calls)]})

    monkeypatch.setattr(frames, "CODE_VERSION", "aaa")
    assert frames.memo("t", build)["x"].to_list() == [1]
    assert frames.memo("t", build)["x"].to_list() == [1]  # fresh cache hit
    assert len(calls) == 1

    # Same age, different pipeline code: must rebuild and drop the stale copy.
    monkeypatch.setattr(frames, "CODE_VERSION", "bbb")
    assert frames.memo("t", build)["x"].to_list() == [2]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["t-bbb.parquet"]


def test_memo_cleanup_leaves_frames_with_a_shared_prefix(tmp_path, monkeypatch):
    monkeypatch.setattr(frames, "FRAMES", tmp_path)
    monkeypatch.setattr(frames, "CODE_VERSION", "aaa")
    frames.memo("emendas_favorecidos", lambda: pl.DataFrame({"x": [1]}))
    frames.memo("emendas", lambda: pl.DataFrame({"x": [1]}))
    assert sorted(p.name for p in tmp_path.iterdir()) == ["emendas-aaa.parquet", "emendas_favorecidos-aaa.parquet"]


def test_code_version_is_stable():
    assert frames._code_version() == frames.CODE_VERSION
    assert len(frames.CODE_VERSION) == 12
