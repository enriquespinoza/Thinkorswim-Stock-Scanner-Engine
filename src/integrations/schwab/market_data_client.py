from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping, Sequence


def _response_json(response, context: str):
    status_code = getattr(response, "status_code", None)
    if status_code is None:
        raise RuntimeError(f"{context} response has no status_code.")

    try:
        status = int(status_code)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{context} returned an invalid status code.") from exc

    if not 200 <= status < 300:
        raise RuntimeError(f"{context} failed with HTTP {status}.")

    try:
        return response.json()
    except Exception as exc:
        raise RuntimeError(f"{context} returned invalid JSON.") from exc


class SchwabMarketDataClient:
    """Narrow read-only wrapper around Schwab market-data endpoints.

    No account or order methods are exposed by this class.
    """

    def __init__(self, client) -> None:
        if client is None:
            raise ValueError("client cannot be None.")
        self._client = client

    def get_daily_price_history_payload(
        self,
        symbol: str,
        *,
        start_datetime: datetime | None = None,
        end_datetime: datetime | None = None,
    ) -> dict[str, Any]:
        symbol = str(symbol).strip().upper()
        if not symbol:
            raise ValueError("symbol cannot be empty.")

        response = self._client.get_price_history_every_day(
            symbol,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            need_extended_hours_data=False,
            need_previous_close=True,
        )
        payload = _response_json(response, f"Schwab price-history request for {symbol}")
        if not isinstance(payload, Mapping):
            raise RuntimeError("Schwab price-history payload must be a mapping.")
        return dict(payload)

    def get_quotes_payload(self, symbols: Sequence[str]) -> dict[str, Any]:
        normalized = [str(symbol).strip().upper() for symbol in symbols]
        if not normalized or any(not symbol for symbol in normalized):
            raise ValueError("symbols must contain at least one non-empty symbol.")
        if len(normalized) != len(set(normalized)):
            raise ValueError("symbols cannot contain duplicates.")

        response = self._client.get_quotes(normalized)
        payload = _response_json(response, "Schwab quotes request")
        if not isinstance(payload, Mapping):
            raise RuntimeError("Schwab quote payload must be a mapping.")
        return dict(payload)

    def get_market_hours_payload(
        self,
        markets,
        *,
        session_date: date | None = None,
    ) -> dict[str, Any]:
        response = self._client.get_market_hours(markets, date=session_date)
        payload = _response_json(response, "Schwab market-hours request")
        if not isinstance(payload, Mapping):
            raise RuntimeError("Schwab market-hours payload must be a mapping.")
        return dict(payload)
