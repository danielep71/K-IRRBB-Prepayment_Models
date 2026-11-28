"""Independent reference for the prepayment-rate conventions (MODEL_CONTRACTS.md, CPR and SMM).

Written from the contract, not from toolkit source. Conversions use binary floating point
through log1p and expm1, as the case register states for RATE-CONV-01; pool sums use exact
decimals. Inputs are loan-months of the risk set, one row each, as the data contract defines
them; the import rules that produce them are covered by the DATA-* cases and data_reader.py.
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

# Outcomes that enter the SMM under the defaults of data decisions D4 and D5.
PREPAYMENT_EVENTS = frozenset({'NONE', 'PARTIAL', 'FULL'})
LOAN_MONTH_FIELDS = ('loan_id', 'segment', 'currency', 'as_of_date', 'opening_balance', 'scheduled_principal',
                     'other_change', 'prepaid_principal', 'event')


def check_rate(value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f'rate outside [0, 1]: {value!r}')


def cpr_from_smm(smm: float) -> float:
    """CPR = 1 - (1 - SMM)^12, as -expm1(12 log1p(-SMM)); SMM = 1 gives CPR = 1."""
    check_rate(smm)
    if smm == 1.0:
        return 1.0
    return -math.expm1(12.0 * math.log1p(-smm))


def smm_from_cpr(cpr: float) -> float:
    """SMM = 1 - (1 - CPR)^(1/12), as -expm1(log1p(-CPR) / 12); CPR = 1 gives SMM = 1."""
    check_rate(cpr)
    if cpr == 1.0:
        return 1.0
    return -math.expm1(math.log1p(-cpr) / 12.0)


def realised_cpr(smms: list[float]) -> float:
    """CPR over n months: 1 - (prod (1 - SMM(t)))^(12/n), never an average of monthly CPRs."""
    if not smms:
        raise ValueError('a realised CPR needs at least one month')
    for smm in smms:
        check_rate(smm)
    if any(smm == 1.0 for smm in smms):
        return 1.0
    return -math.expm1(12.0 / len(smms) * math.fsum(math.log1p(-smm) for smm in smms))


@dataclass(frozen=True)
class LoanMonth:
    loan_id: str
    segment: str
    currency: str
    as_of_date: str    # month end t; the loan-month runs from t-1 to t
    opening_balance: Decimal    # balance(i, t-1)
    scheduled_principal: Decimal
    other_change: Decimal
    prepaid_principal: Decimal
    event: str

    @property
    def available(self) -> Decimal:
        """A(i,t) = balance(t-1) - scheduled_principal(t) + max(other_change(t), 0)."""
        return self.opening_balance - self.scheduled_principal + max(self.other_change, Decimal(0))


def read_loan_months(path: Path) -> list[LoanMonth]:
    with path.open(encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != LOAN_MONTH_FIELDS:
            raise ValueError(f'{path}: header must be {",".join(LOAN_MONTH_FIELDS)}')
        return [LoanMonth(row['loan_id'], row['segment'], row['currency'], row['as_of_date'],
                          Decimal(row['opening_balance']), Decimal(row['scheduled_principal']),
                          Decimal(row['other_change']), Decimal(row['prepaid_principal']), row['event'])
                for row in reader]


@dataclass
class Pool:
    """Sums of one segment, currency and month end."""
    available: Decimal = Decimal(0)
    partial: Decimal = Decimal(0)
    full: Decimal = Decimal(0)
    reneg: Decimal = Decimal(0)
    loan_months: int = 0

    @property
    def prepaid(self) -> Decimal:
        return self.partial + self.full + self.reneg

    @property
    def smm(self) -> Decimal:
        return self.prepaid / self.available

    @property
    def smm_partial(self) -> Decimal:
        return self.partial / self.available

    @property
    def smm_full(self) -> Decimal:
        return self.full / self.available

    @property
    def smm_reneg(self) -> Decimal:
        return self.reneg / self.available


def pool_rates(months: list[LoanMonth], include_reneg: bool = False) -> dict[tuple[str, str, str], Pool]:
    """Balance-weighted pool SMM per (segment, currency, month end): sum P / sum A.

    DEFAULT and SALE are competing exits (D5) and MATURITY is a final scheduled repayment:
    none of them enters either sum. RENEG enters only when the run setting includes it (D4),
    with P = -other_change, the principal transferred to its successor. A loan-month with
    A <= 0 is excluded.
    """
    pools: dict[tuple[str, str, str], Pool] = {}
    for month in months:
        if month.event not in PREPAYMENT_EVENTS and not (include_reneg and month.event == 'RENEG'):
            continue
        available = month.available
        if available <= 0:
            continue
        pool = pools.setdefault((month.segment, month.currency, month.as_of_date), Pool())
        pool.available += available
        pool.loan_months += 1
        if month.event == 'PARTIAL':
            pool.partial += month.prepaid_principal
        elif month.event == 'FULL':
            pool.full += month.prepaid_principal
        elif month.event == 'RENEG':
            pool.reneg += -month.other_change
    return pools
