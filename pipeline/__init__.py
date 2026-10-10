"""Build-time data pipeline for the public data explorer.

Each module wraps one source (IBGE, Câmara, Portal da Transparência) and returns
clean Polars frames. The Observable Framework data loaders in ``src/data`` are
thin scripts that call into this package and write the result to stdout.
"""
