"""Data manifest: what each build was made from, and how it compares to the last one.

``build()`` records the code version, when each raw source was downloaded and
row counts / totals of every cleaned frame. The site publishes it at a stable
URL (``/manifest.json``), so CI can fetch the live copy before deploying and
report what changed:

    python -m pipeline.manifest publish                     # dist/_file/... -> dist/manifest.json
    python -m pipeline.manifest compare previous.json dist/manifest.json

``compare`` warns on any metric that dropped by more than ``--threshold``
(default 10 %) and on output columns that disappeared — the usual signature of
a source that changed format or a join that broke. It never fails the build
unless ``--strict`` is given.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import polars as pl

from . import camara, frames, ibge, portal
from .http import ROOT, cached_path


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")


def _source(nome: str, url: str, params: dict | None = None, suffix: str = ".bin") -> dict:
    """A raw download and when it entered the cache. Never includes request
    headers, which is where API keys live."""
    path = cached_path(url, params, suffix)
    return {
        "nome": nome,
        "url": url + (f"?{urlencode(params)}" if params else ""),
        "baixado_em": _iso(path.stat().st_mtime) if path else None,
    }


def _table(df: pl.DataFrame, *, by_year: str | None = None, value: str | None = None) -> dict:
    out: dict = {"linhas": df.height, "colunas": df.columns}
    if value:
        out["total"] = round(float(df[value].sum()), 2)
    if by_year:
        agg = [pl.len().alias("linhas")] + ([pl.col(value).sum().alias("total")] if value else [])
        per_year = df.group_by(by_year).agg(agg).drop_nulls(by_year).sort(by_year)
        out["linhas_por_ano"] = {str(r[by_year]): r["linhas"] for r in per_year.iter_rows(named=True)}
        if value:
            out["total_por_ano"] = {str(r[by_year]): round(r["total"], 2) for r in per_year.iter_rows(named=True)}
    return out


def build() -> dict:
    mun = frames.municipios()
    dep = frames.deputados()
    ceap = frames.ceap()
    em = frames.emendas()
    fav = frames.emendas_favorecidos()
    ceis = frames.ceis()
    snapshot = ceis["snapshot"][0]

    fontes = [
        _source("IBGE — lista de municípios", ibge.MUNICIPIOS_URL, suffix=".json"),
        _source("IBGE — malha de UFs", *ibge.malha_request("UF"), suffix=".topojson"),
        _source("IBGE — malha de municípios", *ibge.malha_request("municipio"), suffix=".topojson"),
        _source("Câmara — cadastro de deputados", camara.BULK_DEPUTADOS, suffix=".csv"),
        *[_source(f"Câmara — CEAP {y}", camara.BULK_CEAP.format(year=y), suffix=".zip") for y in camara.ceap_years()],
        _source("Portal — emendas parlamentares", portal.EMENDAS_URL, suffix=".zip"),
        _source(f"Portal — CEIS {snapshot}", portal.ceis_url(snapshot.replace("-", "")), suffix=".zip"),
    ]
    # Years not published yet were never downloaded; they aren't sources of this build.
    fontes = [f for f in fontes if f["baixado_em"] or not f["nome"].startswith("Câmara — CEAP")]

    com_municipio = fav.filter(pl.col("municipio_code").is_not_null())["valor"].sum()
    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": os.environ.get("GITHUB_SHA"),
        "codigo_pipeline": frames.CODE_VERSION,
        "fontes": fontes,
        "tabelas": {
            "municipios": _table(mun),
            "deputados": _table(dep) | {"em_exercicio": int(dep["em_exercicio"].sum())},
            "ceap": _table(ceap, by_year="ano", value="valor"),
            "emendas": _table(em, by_year="ano", value="pago_total")
            | {"autores_vinculados": em.filter(pl.col("deputado_id").is_not_null())["autor"].n_unique()},
            "emendas_favorecidos": _table(fav, by_year="ano", value="valor")
            | {"parcela_valor_com_municipio": round(com_municipio / fav["valor"].sum(), 4)},
            "ceis": _table(ceis) | {"snapshot": snapshot},
        },
    }


# ------------------------------------------------------------------- compare


def _numbers(d: dict, prefix: str = "") -> dict[str, float]:
    """Flatten numeric leaves: {"ceap": {"linhas": 3}} -> {"ceap.linhas": 3}."""
    out: dict[str, float] = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out |= _numbers(v, f"{key}.")
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            out[key] = v
    return out


def _fmt(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:,.0f}" if abs(v) >= 100 or float(v).is_integer() else f"{v:,.4g}"


def compare(old: dict, new: dict, threshold: float = 0.10) -> tuple[str, list[str]]:
    """Markdown report of changed metrics, and the list of warnings."""
    warnings: list[str] = []
    rows: list[str] = []
    a, b = _numbers(old.get("tabelas", {})), _numbers(new.get("tabelas", {}))
    unchanged = 0
    for key in sorted(a.keys() | b.keys()):
        va, vb = a.get(key), b.get(key)
        if va == vb:
            unchanged += 1
            continue
        change = (vb - va) / abs(va) if va not in (None, 0) and vb is not None else None
        flag = ""
        if vb is None:
            flag = "⚠"
            warnings.append(f"{key} disappeared (was {_fmt(va)})")
        elif change is not None and change < -threshold:
            flag = "⚠"
            warnings.append(f"{key} dropped {-change:.0%}: {_fmt(va)} → {_fmt(vb)}")
        rows.append(f"| {f'{flag} ' if flag else ''}`{key}` | {_fmt(va)} | {_fmt(vb)} | {'—' if change is None else f'{change:+.1%}'} |")

    for name, table in new.get("tabelas", {}).items():
        before = set(old.get("tabelas", {}).get(name, {}).get("colunas", []))
        after = set(table.get("colunas", []))
        if before and (gone := before - after):
            warnings.append(f"{name}: columns removed: {', '.join(sorted(gone))}")
        if before and (added := after - before):
            rows.append(f"| `{name}.colunas` | | +{', '.join(sorted(added))} | |")

    lines = [
        "## Data manifest vs. live site",
        "",
        f"Previous build: {old.get('gerado_em', '?')} (code `{old.get('codigo_pipeline', '?')}`) · "
        f"this build: {new.get('gerado_em', '?')} (code `{new.get('codigo_pipeline', '?')}`)",
        "",
    ]
    if warnings:
        lines += [f"### ⚠ {len(warnings)} warning(s)", "", *[f"- {w}" for w in warnings], ""]
    if rows:
        lines += ["| Metric | Previous | Current | Change |", "|---|--:|--:|--:|", *rows, ""]
    lines.append(f"{unchanged} metric(s) unchanged.")
    lines += ["", "### Sources", "", "| Source | Downloaded |", "|---|---|"]
    lines += [f"| [{f['nome']}]({f['url']}) | {f['baixado_em'] or '—'} |" for f in new.get("fontes", [])]
    return "\n".join(lines) + "\n", warnings


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _publish(dist: Path) -> Path:
    """Copy Framework's content-hashed copy of the manifest to a stable URL."""
    candidates = [p for p in dist.glob("_file/**/manifest*.json") if re.fullmatch(r"manifest(\.[0-9a-f]+)?\.json", p.name)]
    if len(candidates) != 1:
        raise SystemExit(f"expected one built manifest under {dist}/_file, found {len(candidates)}: {candidates}")
    target = dist / "manifest.json"
    shutil.copyfile(candidates[0], target)
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pipeline.manifest")
    sub = parser.add_subparsers(dest="cmd", required=True)
    pub = sub.add_parser("publish", help="copy the built manifest to dist/manifest.json")
    pub.add_argument("--dist", type=Path, default=ROOT / "dist")
    cmp_ = sub.add_parser("compare", help="report changes between two manifests")
    cmp_.add_argument("previous", type=Path)
    cmp_.add_argument("current", type=Path)
    cmp_.add_argument("--threshold", type=float, default=0.10, help="warn on drops larger than this fraction")
    cmp_.add_argument("--strict", action="store_true", help="exit 1 when there are warnings")
    args = parser.parse_args(argv)

    if args.cmd == "publish":
        print(f"manifest published at {_publish(args.dist)}")
        return 0

    new = _load(args.current)
    if new is None:
        print(f"::error::cannot read {args.current}")
        return 1
    old = _load(args.previous)
    if old is None:
        report, warnings = "## Data manifest\n\nNo previous manifest to compare with (first deploy?).\n", []
    else:
        report, warnings = compare(old, new, args.threshold)

    in_ci = os.environ.get("GITHUB_ACTIONS") == "true"
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(report)
    else:
        sys.stdout.write(report)
    if in_ci:
        for w in warnings:
            print(f"::warning title=Data regression::{w}")
    return 1 if args.strict and warnings else 0


if __name__ == "__main__":
    raise SystemExit(main())
