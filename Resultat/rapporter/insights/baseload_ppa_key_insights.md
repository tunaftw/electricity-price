# Key Insights: Baseload PPA with Solar + Wind + BESS

**Last updated:** 2024-12-09
**Based on:** SE3 2024 analysis (optimerad sol/vind-ratio)

---

## Insight 1: Non-Linear Battery Scaling

Battery requirements scale **exponentially** with baseload percentage:

| Baseload % | Battery (MWh) | Cost Estimate |
|------------|---------------|---------------|
| 50% | 1 MWh | ~€100k |
| 80% | 8 MWh | ~€800k |
| 100% | 109 MWh | ~€10M+ |

**Implication:** Targeting 100% baseload is economically impractical. The **80% level** offers the best balance between delivery guarantee and capital cost.

---

## Insight 2: Summer Nights Are the Bottleneck

Counter-intuitively, the most challenging periods are **summer nights** (July-August), not winter darkness.

**Why:**
- Summer has weaker wind (reduced pressure gradients)
- Anticyclones (high pressure) can persist for days
- Solar contributes nothing at night regardless of season

**Pass hour distribution (10% worst hours):**
- July: 27%
- August: 20%
- June: 17%
- January: <1%

**Implication:** PPA design should allow for summer night non-delivery rather than winter "force majeure" clauses.

---

## Insight 3: 10% Pass Reduces Battery by 50-100%

Allowing **10% non-delivery** (878 hours/year) dramatically reduces battery requirements:

| Baseload | Full Delivery | 90% Delivery | Reduction |
|----------|---------------|--------------|-----------|
| 50% | 1 MWh | 0 MWh | -100% |
| 80% | 8 MWh | 3 MWh | -60% |
| 100% | 109 MWh | 57 MWh | -48% |

**Implication:** Negotiate for "pass" hours in PPA contracts. Even small allowances yield outsized battery savings.

---

## Insight 4: Optimal Solar/Wind Ratio Depends on Battery Constraint

The optimal ratio between solar and wind depends on your **battery duration constraint**.

*Alla beräkningar inkluderar 90% round-trip battery efficiency.*

| Battery Duration | Optimal Ratio | Max Baseload | Battery |
|------------------|---------------|--------------|---------|
| Ingen constraint | 50% Sol / 50% Vind | - | - |
| 1-2h (praktisk Li-ion) | **20% Sol / 80% Vind** | 44% av medelproduktion | 0.46 MWh |
| 1-10h (större BESS) | 40% Sol / 60% Vind | 46% av medelproduktion | ~0.65 MWh |

**Varför mer vind med striktare battericonstraint?**
- Vind producerar på natten (täcker baseload utan buffring)
- Sol kräver nattlagring (driver upp batteriduration)
- 80% vind ger tillräcklig nattproduktion för att minimera batteribehov

**Kapacitetsfaktorer (SE3):**
- Solar: 11.5%
- Wind: 30%
- 20%/80% kombination: 26.3%

---

## Insight 5: Capacity Factor Determines Maximum Baseload

**Combined CF = Maximum baseload as fraction of installed capacity**

With 2 MW installed (1 sol + 1 vind) and 20.8% CF:
- Max baseload = 0.415 MW (20.8% of 2 MW)
- Any higher baseload is **mathematically impossible** (deficit > surplus annually)

**Formula:**
```
Max Baseload (MW) = Installed Capacity (MW) × Combined Capacity Factor
```

---

## Insight 6: Battery Duration vs Power

Two separate requirements:
1. **Energy (MWh):** Covers extended low-production periods
2. **Power (MW):** Covers instantaneous deficit

For 80% baseload:
- Energy: 8 MWh
- Power: ~0.33 MW (matches baseload)
- **Duration:** 8 MWh / 0.33 MW = **24 hours**

Typical Li-ion batteries have 2-4h duration. **8 MWh / 0.33 MW = 24h requires flow batteries or oversized Li-ion.**

---

## Insight 7: Economic Break-Even Analysis (TBD)

**Open questions:**
- At what spot price level is battery cheaper than buying missing power?
- What's the value of the baseload premium over pay-as-produced?
- Can stacked revenues (FCR, aFRR, arbitrage) offset battery cost?

---

## Application: PPA Structure Recommendations

| PPA Type | Battery Need | Risk | Premium |
|----------|--------------|------|---------|
| Pay-as-produced | 0 MWh | Buyer takes volume risk | Low |
| 80% baseload + 10% pass | ~3 MWh | Balanced | Medium |
| 100% baseload | 109 MWh | Seller takes all risk | Very high |

**Recommended structure:** 80% baseload with 10% pass allowance + spot settlement for remaining production.

---

## Data Sources

- Solar profile: PVsyst simulation (south_lundby.csv)
- Wind profile: ENTSO-E actual generation SE3 2024
- Analysis code: `elpris/baseload_analysis.py`
- **Battery efficiency: 90% round-trip** (applied to charging losses)

---

*Generated from baseload PPA analysis, December 2024*
*Updated 2024-12-09: Added battery efficiency (90%) to all calculations*
