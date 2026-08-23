"""Körningscache för Insikt-generatorn — datainsamling EN gång.

Problemet: ``performance_report_data.generate_report`` anropar
``park_revenue.calculate_park_revenue_capture`` (som i sin tur läser ALLA
parkers 15-min-CSV:er) vid varje anrop. Insikt bygger 13 månader × 8
parker = 104 rapporter, plus obalans- och BESS-modulerna som läser samma
CSV:er igen — utan cache tar genereringen 15+ minuter i stället för ett
par.

Lösningen: :func:`install_insikt_cache` memoiserar de tunga, rena
loaderna under processens livstid och binder om namnen i de moduler som
importerat dem på modulnivå. Inga källmoduler utanför ``elpris/insikt``
ändras — patchningen sker i runtime och gäller bara processer som
uttryckligen kallar ``install_insikt_cache()`` (generate_insikt.py).

Memoiserade funktioner (alla är rena filsystemsläsare/beräkningar):

* ``operations_dashboard_data.load_park_15min`` (per park)
* ``operations_dashboard_data.load_spot_prices_15min`` (per zon)
* ``dashboard_v2_data.load_spot_prices`` (per zon)
* ``park_revenue.calculate_park_revenue_capture`` (en gång)

VIKTIGT: de cachade returvärdena delas mellan anropare — de får inte
muteras. Samtliga kända konsumenter i repot itererar utan att mutera.
"""

from __future__ import annotations

import functools
from typing import Any, Callable, Dict

_INSTALLED = False


def _memoize(fn: Callable) -> Callable:
    """Enkel obegränsad memoisering på positionella argument.

    ``functools.lru_cache`` undviks medvetet: loadernas argument är få
    strängar och cachen ska leva hela processen (maxsize=None hade gått,
    men en egen wrapper ger oss ``__wrapped__``-fri patchbarhet och en
    tydlig ``cache``-dict för test/inspektion).
    """
    cache: Dict[tuple, Any] = {}

    @functools.wraps(fn)
    def wrapper(*args):
        if args not in cache:
            cache[args] = fn(*args)
        return cache[args]

    wrapper.cache = cache  # type: ignore[attr-defined]
    wrapper._insikt_cached = True  # type: ignore[attr-defined]
    return wrapper


def install_insikt_cache() -> None:
    """Memoisera de tunga loaderna och bind om alla modulnivå-referenser.

    Idempotent — andra anropet är en no-op.
    """
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    from .. import (
        dashboard_v2_data,
        operations_dashboard_data,
        park_revenue,
        performance_report_data,
        rework_portfolio,
    )
    from . import bess_stack, obalans

    load_park = _memoize(operations_dashboard_data.load_park_15min)
    load_spot_15 = _memoize(operations_dashboard_data.load_spot_prices_15min)
    load_spot = _memoize(dashboard_v2_data.load_spot_prices)
    calc_revenue = _memoize(park_revenue.calculate_park_revenue_capture)

    # Källmodulerna (interna anrop går via modulattributet).
    operations_dashboard_data.load_park_15min = load_park
    operations_dashboard_data.load_spot_prices_15min = load_spot_15
    dashboard_v2_data.load_spot_prices = load_spot
    park_revenue.calculate_park_revenue_capture = calc_revenue

    # Moduler som band namnen vid import (from X import y) — bind om.
    park_revenue.load_park_15min = load_park
    park_revenue.load_spot_prices_15min = load_spot_15
    performance_report_data.load_park_15min = load_park
    rework_portfolio.load_park_15min = load_park
    bess_stack.load_park_15min = load_park
    bess_stack.load_spot_prices = load_spot
    obalans.load_park_15min = load_park
    # (puls.py och marknad.py importerar lokalt vid anrop och träffar
    #  därmed de ompatchade modulattributen automatiskt.)
