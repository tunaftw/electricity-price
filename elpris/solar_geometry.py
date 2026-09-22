"""Solhöjd för en plats och tidpunkt (NOAA:s approximation).

Används för att skilja natt från dag i parkdatan: en solpark kan inte
producera när solen är under horisonten, så "produktion" då är en fastnad
eller felaktig signal. Noggrannheten (±0,5°) räcker gott för det syftet.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone


def solar_elevation_deg(ts_utc: datetime, latitude: float, longitude: float) -> float:
    """Solens höjd över horisonten i grader.

    ``ts_utc`` måste vara tidszonsmedveten. Positiv = sol uppe.
    """
    ts = ts_utc.astimezone(timezone.utc)
    day_of_year = ts.timetuple().tm_yday
    hour = ts.hour + ts.minute / 60.0 + ts.second / 3600.0

    gamma = 2.0 * math.pi / 365.0 * (day_of_year - 1 + (hour - 12.0) / 24.0)
    decl = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
        - 0.002697 * math.cos(3 * gamma)
        + 0.00148 * math.sin(3 * gamma)
    )
    eq_time_min = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )
    true_solar_min = hour * 60.0 + eq_time_min + 4.0 * longitude
    hour_angle = math.radians(true_solar_min / 4.0 - 180.0)
    lat = math.radians(latitude)
    cos_zenith = (
        math.sin(lat) * math.sin(decl)
        + math.cos(lat) * math.cos(decl) * math.cos(hour_angle)
    )
    cos_zenith = max(-1.0, min(1.0, cos_zenith))
    return math.degrees(math.asin(cos_zenith))
