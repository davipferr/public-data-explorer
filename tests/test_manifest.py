import json

import polars as pl

from pipeline import manifest


def _manifest(**tabelas):
    return {"gerado_em": "2026-10-01T00:00:00+00:00", "codigo_pipeline": "abc", "fontes": [], "tabelas": tabelas}


def test_table_stats_by_year():
    df = pl.DataFrame({"ano": [2023, 2023, 2024, None], "valor": [1.0, 2.0, 5.0, 1.0]})
    t = manifest._table(df, by_year="ano", value="valor")
    assert t == {
        "linhas": 4,
        "colunas": ["ano", "valor"],
        "total": 9.0,
        "linhas_por_ano": {"2023": 2, "2024": 1},
        "total_por_ano": {"2023": 3.0, "2024": 5.0},
    }


def test_compare_flags_drops_missing_metrics_and_removed_columns():
    old = _manifest(
        ceap={"linhas": 1000, "colunas": ["a", "b"], "linhas_por_ano": {"2025": 600, "2026": 400}},
        ceis={"linhas": 50, "colunas": ["doc"], "snapshot": "2026-10-01"},
    )
    new = _manifest(
        ceap={"linhas": 1100, "colunas": ["a", "c"], "linhas_por_ano": {"2026": 1100}},  # 2025 vanished
        ceis={"linhas": 40, "colunas": ["doc"], "snapshot": "2026-10-08"},  # -20 %
    )
    report, warnings = manifest.compare(old, new, threshold=0.10)
    assert warnings == [
        "ceap.linhas_por_ano.2025 disappeared (was 600)",
        "ceis.linhas dropped 20%: 50 → 40",
        "ceap: columns removed: b",
    ]
    assert "| `ceap.linhas` | 1,000 | 1,100 | +10.0% |" in report  # growth is reported, not flagged
    assert "+c" in report


def test_compare_identical_manifests_is_quiet():
    m = _manifest(ceap={"linhas": 10, "colunas": ["a"]})
    report, warnings = manifest.compare(m, m)
    assert warnings == []
    assert "2 metric(s) unchanged" not in report  # colunas aren't metrics
    assert "1 metric(s) unchanged." in report


def test_cli_compare_without_previous_manifest(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    current = tmp_path / "manifest.json"
    current.write_text(json.dumps(_manifest(ceap={"linhas": 1})), encoding="utf-8")
    assert manifest.main(["compare", str(tmp_path / "missing.json"), str(current)]) == 0
    assert "No previous manifest" in capsys.readouterr().out


def test_cli_strict_fails_on_warnings(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    old, new = tmp_path / "old.json", tmp_path / "new.json"
    old.write_text(json.dumps(_manifest(ceap={"linhas": 100})), encoding="utf-8")
    new.write_text(json.dumps(_manifest(ceap={"linhas": 10})), encoding="utf-8")
    assert manifest.main(["compare", str(old), str(new)]) == 0
    assert manifest.main(["compare", str(old), str(new), "--strict"]) == 1


def test_publish_copies_hashed_manifest_to_stable_path(tmp_path):
    built = tmp_path / "_file" / "data" / "manifest.1a2b3c4d.json"
    built.parent.mkdir(parents=True)
    built.write_text('{"ok": true}', encoding="utf-8")
    assert manifest.main(["publish", "--dist", str(tmp_path)]) == 0
    assert json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8")) == {"ok": True}
