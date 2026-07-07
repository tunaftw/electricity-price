from datetime import date

import pytest

from elpris import entsoe


class DummyResponse:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text
        self.reason = ""

    def raise_for_status(self):
        import requests

        raise requests.HTTPError(f"{self.status_code} Error", response=self)


def test_entsoe_authentication_failure_is_not_retried(monkeypatch):
    calls = []

    def fake_get(*args, **kwargs):
        calls.append((args, kwargs))
        return DummyResponse(
            401,
            """
            <Acknowledgement_MarketDocument>
              <Reason>
                <code>999</code>
                <text>Authentication failed.</text>
              </Reason>
            </Acknowledgement_MarketDocument>
            """,
        )

    monkeypatch.setattr(entsoe.requests, "get", fake_get)

    with pytest.raises(Exception) as exc_info:
        entsoe.fetch_entsoe_data(
            "actual_generation",
            "SE1",
            date(2026, 7, 1),
            date(2026, 7, 4),
            psr_type="solar",
            token="invalid-token",
        )

    assert len(calls) == 1
    assert "Authentication failed" in str(exc_info.value)
    assert "failed.." not in str(exc_info.value)
    assert "ENTSOE_TOKEN" in str(exc_info.value)
