def test_core_imports() -> None:
    import numpy  # noqa: F401
    import pandas  # noqa: F401
    import requests  # noqa: F401


def test_scanner_modules_import_without_live_provider_dependency() -> None:
    import src.data.market_data  # noqa: F401
    import src.universe.builder  # noqa: F401
