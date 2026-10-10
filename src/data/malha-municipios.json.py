"""TopoJSON of all municipalities (IBGE malhas v3, lowest resolution: ~1.4 MB).

Feature property ``codarea`` = 7-digit municipality code. The mesh can lag behind
the official list (e.g. Boa Esperança do Norte-MT, created in 2025).
"""

from pipeline import ibge
from pipeline.io import emit_bytes

emit_bytes(ibge.malha("municipio"))
