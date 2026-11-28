"""Independent reference for the behavioural cash-flow projection (MODEL_CONTRACTS.md).

Written from the contract, not from toolkit source. Each loan is projected monthly from the
as-of date: interest at client_rate / 12 on the opening balance; scheduled principal on payment
months, from the amortisation type and the balance after earlier prepayments; prepayment
SMM x (opening - scheduled); the final repayment at maturity; for RESET and FLOAT loans the
balance at the next reset leaves as a repricing cash flow. An annuity is re-amortised over its
remaining term after a prepayment, so it keeps its maturity and its instalment falls (M6).
Amounts are binary floating point and never rounded.

Where the contract leaves a treatment open, the reference refuses the input with
ContractQuestion instead of choosing one: the periodic rate of an annuity paid every 3, 6 or 12
months; payment months when anchoring at origination and at maturity disagree; a reset month
that is also an amortising payment month, carries a positive SMM or is the maturity month.
"""
from __future__ import annotations

import csv
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import rates

LOAN_FIELDS = ('loan_id', 'segment', 'currency', 'origination_date', 'maturity_date', 'original_balance',
               'rate_type', 'fixed_until', 'reset_months', 'amortisation', 'payment_months', 'penalty_type',
               'penalty_value', 'predecessor_id')
POSITION_FIELDS = ('as_of_date', 'loan_id', 'balance', 'client_rate')
CPR_FIELDS = ('loan_id', 'as_of_date', 'cpr')
MEASURES = ('opening', 'interest', 'scheduled', 'prepaid', 'repricing', 'closing')


class ContractQuestion(ValueError):
    """The contract does not fix the treatment this input needs, so the reference refuses it."""


@dataclass(frozen=True)
class Loan:
    loan_id: str
    segment: str
    currency: str
    origination_date: date
    maturity_date: date
    rate_type: str    # FIXED, RESET or FLOAT
    fixed_until: date | None
    reset_months: int | None
    amortisation: str    # ANNUITY, LINEAR or BULLET
    payment_months: int
    penalty_type: str


@dataclass(frozen=True)
class Position:
    """A loan at the as-of date: its outstanding balance and the client rate in force."""
    loan: Loan
    as_of_date: date
    balance: float
    client_rate: float


@dataclass(frozen=True)
class Month:
    """One projected month k, ending at as_of_date."""
    k: int
    as_of_date: date
    opening: float
    interest: float
    scheduled: float
    prepaid: float
    repricing: float
    closing: float
    cpr: float
    smm: float


def month_end(day: date) -> date:
    following = date(day.year + day.month // 12, day.month % 12 + 1, 1)
    return following - timedelta(days=1)


def add_months(end: date, months: int) -> date:
    """The month end ``months`` months after (or before) the month of ``end``."""
    index = end.year * 12 + end.month - 1 + months
    return month_end(date(index // 12, index % 12 + 1, 1))


def months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + end.month - start.month


def next_reset(loan: Loan, as_of: date) -> date | None:
    """Month end of the first reset after the as-of date; None for a FIXED loan.

    A RESET loan first resets at fixed_until, then every reset_months; a FLOAT loan resets
    every reset_months from origination. A reset dated in the as-of month has already happened.
    """
    if loan.rate_type == 'FIXED':
        return None
    if loan.reset_months is None or loan.reset_months <= 0:
        raise ValueError(f'{loan.loan_id}: a {loan.rate_type} loan needs reset_months')
    if loan.rate_type == 'RESET':
        if loan.fixed_until is None:
            raise ValueError(f'{loan.loan_id}: a RESET loan needs fixed_until')
        reset = month_end(loan.fixed_until)
        if reset > as_of:
            return reset
    elif loan.rate_type == 'FLOAT':
        reset = month_end(loan.origination_date)
    else:
        raise ValueError(f'{loan.loan_id}: unknown rate type {loan.rate_type}')
    while reset <= as_of:
        reset = add_months(reset, loan.reset_months)
    return reset


def projection_months(loan: Loan, as_of: date) -> list[date]:
    """Month ends projected: up to maturity, or up to the next reset when it comes first."""
    maturity = month_end(loan.maturity_date)
    if maturity <= as_of:
        raise ValueError(f'{loan.loan_id}: matures on or before the as-of date')
    reset = next_reset(loan, as_of)
    if reset == maturity:
        raise ContractQuestion(f'{loan.loan_id}: reset in the maturity month (final repayment or repricing)')
    end = reset if reset is not None and reset < maturity else maturity
    return [add_months(as_of, k) for k in range(1, months_between(as_of, end) + 1)]


def payment_months(loan: Loan, as_of: date) -> list[date]:
    """Scheduled principal payment month ends after the as-of date, up to maturity."""
    maturity = month_end(loan.maturity_date)
    if loan.amortisation == 'BULLET':
        return [maturity]
    if loan.amortisation not in ('ANNUITY', 'LINEAR'):
        raise ValueError(f'{loan.loan_id}: unknown amortisation {loan.amortisation}')
    step = loan.payment_months
    if step not in (1, 3, 6, 12):
        raise ValueError(f'{loan.loan_id}: payment_months must be 1, 3, 6 or 12')
    if months_between(month_end(loan.origination_date), maturity) % step:
        raise ContractQuestion(f'{loan.loan_id}: payment months counted from origination and from maturity differ')
    return [add_months(maturity, -step * j) for j in range(months_between(as_of, maturity) // step, -1, -1)
            if add_months(maturity, -step * j) > as_of]


def annuity_principal(balance: float, monthly_rate: float, payments: int) -> float:
    """Principal part of the level instalment repaying ``balance`` in ``payments`` monthly payments.

    instalment - rate x balance = balance x rate / ((1 + rate)^n - 1), with (1 + rate)^n - 1
    as expm1(n log1p(rate)) so that a rate near zero keeps full precision; balance / n at zero.
    """
    if payments < 1:
        raise ValueError('an annuity needs at least one remaining payment')
    if payments == 1:
        return balance
    if monthly_rate == 0.0:
        return balance / payments
    return balance * monthly_rate / math.expm1(payments * math.log1p(monthly_rate))


def project(position: Position, cprs: Sequence[float]) -> list[Month]:
    """Project one loan monthly from its as-of date, with the CPR of each projected month."""
    loan, as_of = position.loan, position.as_of_date
    if loan.amortisation == 'ANNUITY' and loan.payment_months != 1:
        raise ContractQuestion(f'{loan.loan_id}: periodic rate of an annuity paid every {loan.payment_months} months')
    months = projection_months(loan, as_of)
    if len(cprs) != len(months):
        raise ValueError(f'{loan.loan_id}: {len(cprs)} CPRs for {len(months)} projected months')
    payments = payment_months(loan, as_of)
    reset = next_reset(loan, as_of)
    balance, rate = position.balance, position.client_rate
    result: list[Month] = []
    for k, (when, cpr) in enumerate(zip(months, cprs), start=1):
        opening = balance
        interest = rate / 12.0 * opening
        smm = rates.smm_from_cpr(cpr)
        repricing = 0.0
        if when == reset:
            if smm != 0.0 or (when in payments and loan.amortisation != 'BULLET'):
                raise ContractQuestion(f'{loan.loan_id}: scheduled principal or prepayment in the reset month')
            scheduled = prepaid = 0.0
            repricing = opening
        else:
            scheduled = 0.0
            if when in payments:
                remaining = sum(1 for payment in payments if payment >= when)
                if loan.amortisation == 'ANNUITY':
                    scheduled = annuity_principal(opening, rate / 12.0, remaining)
                elif loan.amortisation == 'LINEAR':
                    scheduled = opening / remaining
                else:
                    scheduled = opening
            prepaid = smm * (opening - scheduled)
        closing = opening - scheduled - prepaid - repricing
        result.append(Month(k, when, opening, interest, scheduled, prepaid, repricing, closing, cpr, smm))
        balance = closing
    return result


def read_csv(path: Path, fields: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(encoding='ascii', newline='') as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != fields:
            raise ValueError(f'{path}: header must be {",".join(fields)}')
        return list(reader)


def read_loans(path: Path) -> dict[str, Loan]:
    """Loan register rows (data contract header); only the fields the projection needs are kept."""
    loans: dict[str, Loan] = {}
    for row in read_csv(path, LOAN_FIELDS):
        loans[row['loan_id']] = Loan(
            row['loan_id'], row['segment'], row['currency'], date.fromisoformat(row['origination_date']),
            date.fromisoformat(row['maturity_date']), row['rate_type'],
            date.fromisoformat(row['fixed_until']) if row['fixed_until'] else None,
            int(row['reset_months']) if row['reset_months'] else None, row['amortisation'],
            int(row['payment_months']), row['penalty_type'])
    return loans


def read_positions(path: Path, loans: dict[str, Loan]) -> list[Position]:
    """The as-of row of each loan: balance and client rate; one as-of date for the whole book."""
    positions = [Position(loans[row['loan_id']], date.fromisoformat(row['as_of_date']), float(row['balance']),
                          float(row['client_rate'])) for row in read_csv(path, POSITION_FIELDS)]
    if len({p.as_of_date for p in positions}) > 1:
        raise ValueError(f'{path}: a book has one as-of date')
    return positions


def read_cprs(path: Path) -> dict[tuple[str, date], float]:
    """CPR of the month ending as_of_date per loan; a projected month without a row has CPR 0."""
    if not path.exists():
        return {}
    return {(row['loan_id'], date.fromisoformat(row['as_of_date'])): float(row['cpr'])
            for row in read_csv(path, CPR_FIELDS)}


def project_book(folder: Path) -> dict[str, list[Month]]:
    """Project every position of a fixture folder (loans.csv, positions.csv, optional cpr.csv)."""
    loans = read_loans(folder / 'loans.csv')
    cprs = read_cprs(folder / 'cpr.csv')
    results: dict[str, list[Month]] = {}
    used: set[tuple[str, date]] = set()
    for position in read_positions(folder / 'positions.csv', loans):
        months = projection_months(position.loan, position.as_of_date)
        keys = [(position.loan.loan_id, when) for when in months]
        used.update(keys)
        results[position.loan.loan_id] = project(position, [cprs.get(key, 0.0) for key in keys])
    if set(cprs) - used:
        raise ValueError(f'{folder}: CPR rows outside the projection: {sorted(set(cprs) - used)}')
    return results


def aggregate(loans: dict[str, Loan], results: dict[str, list[Month]]) -> dict[tuple[str, str, date], list[float]]:
    """Sums of each measure per segment, currency and month end; currencies are never added together."""
    totals: dict[tuple[str, str, date], list[float]] = {}
    for loan_id, months in results.items():
        loan = loans[loan_id]
        for month in months:
            sums = totals.setdefault((loan.segment, loan.currency, month.as_of_date), [0.0] * len(MEASURES))
            for i, measure in enumerate(MEASURES):
                sums[i] += getattr(month, measure)
    return totals
