"""Data manifest: code version, source download times, row counts and totals per frame.

Copied to /manifest.json after the build (``npm run build`` -> postbuild) so CI
can compare each build with the live site. See ``pipeline/manifest.py``.
"""

from pipeline import manifest
from pipeline.io import emit_json

emit_json(manifest.build())
