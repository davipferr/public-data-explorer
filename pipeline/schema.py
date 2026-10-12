"""Fail fast, and clearly, when a source changes the shape of its files.

CGU and the Câmara rename CSV columns without notice. Without a check, a rename
surfaces as a ``ColumnNotFoundError`` deep inside a loader — or, worse, as a
silently all-null column after a relaxed concat. ``require_columns`` runs right
after a raw file is parsed and names the source, the missing columns and the
closest columns that do exist.
"""

from __future__ import annotations

import difflib
from collections.abc import Iterable

import polars as pl


class SchemaError(Exception):
    """A raw input no longer has the columns the pipeline expects."""


def require_columns(
    df: pl.DataFrame,
    expected: Iterable[str],
    source: str,
    *,
    aliases: dict[str, str] | None = None,
    min_rows: int = 1,
) -> pl.DataFrame:
    """Return ``df`` if it has every ``expected`` column and at least ``min_rows`` rows.

    ``aliases`` maps known alternative spellings to the expected name (e.g. a typo
    the source may fix someday); a present alias is renamed to the expected name.
    """
    renames = {alt: name for alt, name in (aliases or {}).items() if alt in df.columns and name not in df.columns}
    if renames:
        df = df.rename(renames)

    missing = [c for c in expected if c not in df.columns]
    if missing:
        hints = []
        for col in missing:
            close = difflib.get_close_matches(col, df.columns, n=1, cutoff=0.6)
            hints.append(f"  - {col!r}" + (f" (did you mean {close[0]!r}?)" if close else ""))
        raise SchemaError(
            f"{source}: {len(missing)} expected column(s) missing — the source format probably changed.\n"
            + "\n".join(hints)
            + f"\nColumns found: {', '.join(map(repr, df.columns))}"
        )
    if df.height < min_rows:
        raise SchemaError(f"{source}: expected at least {min_rows} row(s), got {df.height}")
    return df
