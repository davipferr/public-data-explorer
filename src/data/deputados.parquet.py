"""Deputies of the current legislature: party, UF, photo, civil data, in office or not."""

from pipeline import frames
from pipeline.io import emit_parquet

emit_parquet(frames.deputados().drop("nome_norm"))
