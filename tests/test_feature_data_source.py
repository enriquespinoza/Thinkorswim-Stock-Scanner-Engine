from config.data_sources import SCHWAB_NORMALIZED_DIR, SCHWAB_REFERENCE_NORMALIZED_DIR
from config.settings import RAW_DATA_DIR
from src.features.data_source import get_feature_data_source


def test_yahoo_feature_source_uses_frozen_phase1_paths() -> None:
    source = get_feature_data_source("yahoo")
    assert source.bars_dir == RAW_DATA_DIR
    assert source.reference_dir == RAW_DATA_DIR / "references"
    assert source.name == "yahoo"


def test_schwab_feature_source_uses_versioned_v2_paths() -> None:
    source = get_feature_data_source("schwab")
    assert source.bars_dir == SCHWAB_NORMALIZED_DIR
    assert source.reference_dir == SCHWAB_REFERENCE_NORMALIZED_DIR
    assert source.name == "schwab"


def test_unknown_feature_source_is_rejected() -> None:
    try:
        get_feature_data_source("unknown")
    except ValueError as exc:
        assert "Unsupported feature data source" in str(exc)
    else:
        raise AssertionError("unknown provider should have raised")


def test_schwab_research_source_isolated_from_production() -> None:
    production = get_feature_data_source("schwab")
    research = get_feature_data_source("schwab-research")

    assert research.name == "schwab-research"
    assert research.bars_dir != production.bars_dir
    assert research.reference_dir != production.reference_dir
    assert research.feature_dir != production.feature_dir
    assert research.manifest_path != production.manifest_path
