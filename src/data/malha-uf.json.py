"""TopoJSON of Brazilian states (IBGE malhas v3). Feature property ``codarea`` = UF code."""

from pipeline import ibge
from pipeline.io import emit_bytes

emit_bytes(ibge.malha("UF"))
