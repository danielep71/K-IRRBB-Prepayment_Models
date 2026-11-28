"""Independent reference for two regulatory overlays (MODEL_CONTRACTS.md, Regulatory overlay).

Written from the contract, not from toolkit source. Rates and CPRs use binary floating point.

- Post-shock floor (REG-3 Art. 3(7), Art. 4(1)): floored = max(shocked, floor(m)) with
  floor(m) = min(observed, min(0, -150bp + 3bp x m)) at maturity m years. The floor is a lower
  bound and never replaces a shocked rate above it.
- Standardised prepayment multipliers (REG-1 SRP31.119, Table 5; REG-4 Art. 9(3)):
  CPR_s = min(1, gamma_s x CPR_BASE), gamma_s = 0.8 for PAR_UP, STEEPENER and SHORT_UP and 1.2
  for PAR_DOWN, FLATTENER and SHORT_DOWN; BASE keeps CPR_BASE in both layers (decision M15).

Where the floor is applied (each series tenor before interpolation, or the interpolated rate)
and the multiplier of user-defined scenarios are not stated by the contract; this module
evaluates the floor at a given maturity and refuses any other scenario.
"""
from __future__ import annotations

import csv
from pathlib import Path

BASIS_POINT = 0.0001
FLOOR_START_BP = -150    # floor at maturity 0
FLOOR_STEP_BP = 3    # per year of maturity
GAMMA = {'PAR_UP': 0.8, 'STEEPENER': 0.8, 'SHORT_UP': 0.8,
         'PAR_DOWN': 1.2, 'FLATTENER': 1.2, 'SHORT_DOWN': 1.2}


def read_table(path: Path, fields: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != fields:
            raise ValueError(f'{path}: header must be {",".join(fields)}')
        return list(reader)


def post_shock_floor(maturity_years: float, observed: float) -> float:
    """floor(m) = min(observed, min(0, -150bp + 3bp x m))."""
    if maturity_years < 0:
        raise ValueError(f'negative maturity {maturity_years}')
    line = (FLOOR_START_BP + FLOOR_STEP_BP * maturity_years) * BASIS_POINT
    return min(observed, min(0.0, line))


def floored_rate(maturity_years: float, observed: float, shocked: float) -> float:
    """max(shocked, floor(m)): a lower bound only."""
    return max(shocked, post_shock_floor(maturity_years, observed))


def standardised_cpr(scenario: str, cpr_base: float) -> float:
    """CPR_s = min(1, gamma_s x CPR_BASE); BASE gives CPR_BASE."""
    if not 0.0 <= cpr_base <= 1.0:
        raise ValueError(f'CPR outside [0, 1]: {cpr_base!r}')
    if scenario == 'BASE':
        return cpr_base
    if scenario not in GAMMA:
        raise ValueError(f'no standardised multiplier for scenario {scenario!r}')
    return min(1.0, GAMMA[scenario] * cpr_base)
