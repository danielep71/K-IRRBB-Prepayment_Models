"""Reference implementation of the K-PREPAY prepayment and EVE model.

This module is the executable specification of the VBA engine in src/.
It builds the illustrative input data of the template (curve, segments,
seasonality, loan book and calibration history) and computes every output
the engine writes, so that the expected values on the Tests sheet are
independent of the VBA code under test.

Standard library only. Every convention below is mirrored, operation for
operation, in src/core/*.bas; a change here is a methodology change.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import date

# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------
SCENARIOS = ["CONTRACT", "BASE", "PAR_UP", "PAR_DOWN", "STEEPENER",
             "FLATTENER", "SHORT_UP", "SHORT_DOWN"]
SHOCKS = SCENARIOS[2:]

# BCBS d368 Table 3: CPR scenario multipliers for fixed-rate loans
GAMMA = {"BASE": 1.0, "PAR_UP": 0.8, "PAR_DOWN": 1.2, "STEEPENER": 0.8,
         "FLATTENER": 1.2, "SHORT_UP": 0.8, "SHORT_DOWN": 1.2}

# BCBS d368 Table 1: upper bounds of the 19 time buckets, in years
BUCKET_LABELS = ["O/N", ">O/N-1M", "1M-3M", "3M-6M", "6M-9M", "9M-1Y",
                 "1Y-1.5Y", "1.5Y-2Y", "2Y-3Y", "3Y-4Y", "4Y-5Y", "5Y-6Y",
                 "6Y-7Y", "7Y-8Y", "8Y-9Y", "9Y-10Y", "10Y-15Y", "15Y-20Y",
                 ">20Y"]
BUCKET_UPPER = [1 / 365, 1 / 12, 3 / 12, 6 / 12, 9 / 12, 1.0, 1.5, 2.0, 3.0,
                4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 15.0, 20.0, 1e9]
BUCKET_MID = [0.0028, 0.0417, 0.1667, 0.375, 0.625, 0.875, 1.25, 1.75, 2.5,
              3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 12.5, 17.5, 25.0]


# ---------------------------------------------------------------------------
# Parameters and inputs
# ---------------------------------------------------------------------------
@dataclass
class Params:
    as_of: date = date(2026, 9, 30)
    ccy: str = "EUR"
    mode: str = "BEHAVIOURAL"          # or BCBS_SA
    shock_parallel: float = 0.02       # EUR, Reg. (EU) 2024/856 Annex
    shock_short: float = 0.025
    shock_long: float = 0.01
    shock_decay: float = 4.0           # x in BCBS d368 Annex 2
    apply_floor: bool = True
    floor_start: float = -0.015        # Reg. (EU) 2024/856 Art. 3(7)
    floor_slope: float = 0.0003
    max_months: int = 600
    tier1: float = 6_000_000.0
    outlier_ratio: float = 0.15
    gamma: dict = field(default_factory=lambda: dict(GAMMA))


@dataclass
class Segment:
    sid: str
    desc: str
    cpr_min: float
    cpr_max: float
    slope: float
    mid: float
    ramp: int
    burnout: float
    margin: float
    float_cpr: float
    seasonal: bool


@dataclass
class Loan:
    lid: str
    sid: str
    rate_type: str
    ccy: str
    balance: float
    rate: float
    orig: date
    mat: date
    amort: str
    freq: int
    reset: date | None
    penalty: float


# ---------------------------------------------------------------------------
# Calendar helpers (whole months, as in CORE_Util.MonthsUp / MonthsDown)
# ---------------------------------------------------------------------------
def months_up(d1: date, d2: date) -> int:
    """Months from d1 to d2, a started month counting as one."""
    m = (d2.year - d1.year) * 12 + (d2.month - d1.month)
    if d2.day > d1.day:
        m += 1
    return m


def months_down(d1: date, d2: date) -> int:
    """Completed months from d1 to d2."""
    m = (d2.year - d1.year) * 12 + (d2.month - d1.month)
    if d2.day < d1.day:
        m -= 1
    return m


def add_months(d: date, k: int) -> date:
    """EDATE: same day k months later, clipped to the month end."""
    y = d.year + (d.month - 1 + k) // 12
    m = (d.month - 1 + k) % 12 + 1
    last = [31, 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    return date(y, m, min(d.day, last))


# ---------------------------------------------------------------------------
# Curve (CORE_Curve)
# ---------------------------------------------------------------------------
class Curve:
    def __init__(self, tenors, rates, prm: Params):
        self.t = list(tenors)
        self.r = list(rates)
        self.p = prm

    def base(self, t: float) -> float:
        """Continuously compounded zero rate, linear in t, flat outside."""
        if t <= self.t[0]:
            return self.r[0]
        if t >= self.t[-1]:
            return self.r[-1]
        for i in range(1, len(self.t)):
            if t <= self.t[i]:
                w = (t - self.t[i - 1]) / (self.t[i] - self.t[i - 1])
                return self.r[i - 1] + w * (self.r[i] - self.r[i - 1])
        return self.r[-1]

    def shock(self, scen: str, t: float) -> float:
        p = self.p
        s_short = p.shock_short * math.exp(-t / p.shock_decay)
        s_long = p.shock_long * (1.0 - math.exp(-t / p.shock_decay))
        if scen == "PAR_UP":
            return p.shock_parallel
        if scen == "PAR_DOWN":
            return -p.shock_parallel
        if scen == "SHORT_UP":
            return s_short
        if scen == "SHORT_DOWN":
            return -s_short
        if scen == "STEEPENER":
            return -0.65 * abs(s_short) + 0.9 * abs(s_long)
        if scen == "FLATTENER":
            return 0.8 * abs(s_short) - 0.6 * abs(s_long)
        return 0.0

    def lower_bound(self, t: float, r0: float) -> float:
        p = self.p
        bound = min(0.0, p.floor_start + p.floor_slope * t)
        return min(bound, r0)

    def zero(self, scen: str, t: float) -> float:
        r0 = self.base(t)
        if scen in ("BASE", "CONTRACT"):
            return r0
        r = r0 + self.shock(scen, t)
        if self.p.apply_floor:
            r = max(r, self.lower_bound(t, r0))
        return r

    def df(self, scen: str, t: float) -> float:
        return math.exp(-self.zero(scen, t) * t)


# ---------------------------------------------------------------------------
# Prepayment function (CORE_Prepay)
# ---------------------------------------------------------------------------
def logistic(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def scurve(incentive, cpr_min, cpr_max, slope, mid, burn=1.0):
    return cpr_min + (cpr_max - cpr_min) * burn * logistic(slope * (incentive - mid))


def smm(cpr: float) -> float:
    if cpr >= 1.0:
        return 1.0
    return 1.0 - (1.0 - cpr) ** (1.0 / 12.0)


# ---------------------------------------------------------------------------
# Loan projection (CORE_Engine.ProjectLoan)
# ---------------------------------------------------------------------------
@dataclass
class Flow:
    sched: list
    prep: list
    repr_: list
    intr: list
    bal_start: list
    bal_end: list
    cpr: list


def project(loan: Loan, seg: Segment, seas: list, curve: Curve, prm: Params,
            scen: str, base_cpr: list | None = None) -> Flow:
    rem = months_up(prm.as_of, loan.mat)
    age0 = max(0, months_down(loan.orig, prm.as_of))
    is_float = loan.rate_type == "FLOAT"
    end = rem
    if is_float:
        end = min(rem, months_up(prm.as_of, loan.reset))
    bal = loan.balance
    acc = 0.0
    survival = 1.0
    r = loan.rate
    f = loan.freq
    fl = Flow([0.0] * end, [0.0] * end, [0.0] * end, [0.0] * end,
              [0.0] * end, [0.0] * end, [0.0] * end)
    for k in range(1, end + 1):
        t_rem = (rem - k + 1) / 12.0
        ramp = 1.0 if seg.ramp <= 0 else min(1.0, (age0 + k) / seg.ramp)
        cal = (prm.as_of.month - 1 + k) % 12 + 1
        sm = seas[cal - 1] if seg.seasonal else 1.0
        if scen == "CONTRACT":
            cpr = 0.0
        elif is_float:
            cpr = min(1.0, seg.float_cpr * ramp * sm)
        elif prm.mode == "BCBS_SA" and scen != "BASE":
            cpr = min(1.0, prm.gamma[scen] * base_cpr[k - 1])
        else:
            refi = curve.zero(scen, t_rem) + seg.margin
            inc = r - refi - loan.penalty / max(t_rem, 1.0)
            burn = math.exp(-seg.burnout * (1.0 - survival))
            cpr = min(1.0, scurve(inc, seg.cpr_min, seg.cpr_max, seg.slope,
                                  seg.mid, burn) * ramp * sm)
            if cpr < 0.0:
                cpr = 0.0
        s = smm(cpr)
        fl.bal_start[k - 1] = bal
        fl.cpr[k - 1] = cpr
        acc += bal * r / 12.0
        if k == end:
            if is_float and end < rem:
                fl.repr_[k - 1] = bal
            else:
                fl.sched[k - 1] = bal
            fl.intr[k - 1] = acc
            fl.bal_end[k - 1] = 0.0
            break
        sp = 0.0
        ip = 0.0
        if (rem - k) % f == 0:
            n = (rem - k) // f + 1
            j = r * f / 12.0
            if loan.amort == "ANNUITY":
                if abs(j) < 1e-12:
                    sp = bal / n
                else:
                    sp = bal * j / ((1.0 + j) ** n - 1.0)
            elif loan.amort == "LINEAR":
                sp = bal / n
            ip = acc
            acc = 0.0
        bal1 = bal - sp
        prep = s * bal1
        iprep = s * acc
        acc -= iprep
        bal = bal1 - prep
        survival *= (1.0 - s)
        fl.sched[k - 1] = sp
        fl.prep[k - 1] = prep
        fl.intr[k - 1] = ip + iprep
        fl.bal_end[k - 1] = bal
    return fl


# ---------------------------------------------------------------------------
# Book run (CORE_Engine.Calculate)
# ---------------------------------------------------------------------------
def run_book(loans, segs, seas, curve, prm):
    segmap = {s.sid: s for s in segs}
    out = {"loan": {}, "agg": {}, "seg": {}}
    nmax = max(months_up(prm.as_of, l.mat) for l in loans)
    for sc in SCENARIOS:
        out["agg"][sc] = {k: [0.0] * nmax for k in
                          ("sched", "prep", "repr", "intr", "cf", "bal",
                           "cprw", "balw", "pv")}
    for ln in loans:
        seg = segmap[ln.sid]
        rec = {}
        base = project(ln, seg, seas, curve, prm, "BASE")
        flows = {"BASE": base}
        for sc in SCENARIOS:
            if sc != "BASE":
                flows[sc] = project(ln, seg, seas, curve, prm, sc, base.cpr)
        for sc in SCENARIOS:
            fl = flows[sc]
            pv = 0.0
            wal_num = 0.0
            prin = 0.0
            dur = 0.0
            a = out["agg"][sc]
            for i in range(len(fl.sched)):
                k = i + 1
                t = k / 12.0
                p = fl.sched[i] + fl.prep[i] + fl.repr_[i]
                cf = p + fl.intr[i]
                d = curve.df(sc, t)
                pv += cf * d
                dur += t * cf * d
                wal_num += t * p
                prin += p
                a["sched"][i] += fl.sched[i]
                a["prep"][i] += fl.prep[i]
                a["repr"][i] += fl.repr_[i]
                a["intr"][i] += fl.intr[i]
                a["cf"][i] += cf
                a["bal"][i] += fl.bal_end[i]
                a["cprw"][i] += fl.cpr[i] * fl.bal_start[i]
                a["balw"][i] += fl.bal_start[i]
                a["pv"][i] += cf * d
            n12 = min(12, len(fl.cpr))
            w = sum(fl.bal_start[:n12])
            cpr1 = sum(fl.cpr[i] * fl.bal_start[i] for i in range(n12)) / w if w else 0.0
            rec[sc] = {"pv": pv, "wal": wal_num / prin if prin else 0.0,
                       "dur": dur / pv if pv else 0.0, "cpr1": cpr1,
                       "prep": sum(fl.prep), "n": len(fl.sched)}
        out["loan"][ln.lid] = rec
    # book and segment summaries
    res = {}
    for sc in SCENARIOS:
        a = out["agg"][sc]
        pv = sum(out["loan"][l.lid][sc]["pv"] for l in loans)
        prin = [a["sched"][i] + a["prep"][i] + a["repr"][i] for i in range(nmax)]
        wal = sum((i + 1) / 12.0 * prin[i] for i in range(nmax)) / sum(prin)
        w1 = sum(a["balw"][:12])
        cpr1 = sum(a["cprw"][:12]) / w1
        cprl = sum(a["cprw"]) / sum(a["balw"])
        res[sc] = {"pv": pv, "wal": wal, "cpr1": cpr1, "cprl": cprl,
                   "prep": sum(a["prep"]), "intr": sum(a["intr"])}
    for sc in SCENARIOS:
        res[sc]["deve"] = res[sc]["pv"] - res["BASE"]["pv"]
        res[sc]["deve_t1"] = res[sc]["deve"] / prm.tier1
    out["res"] = res
    out["nmax"] = nmax
    out["balance"] = sum(l.balance for l in loans)
    out["eff_dur"] = ((res["PAR_DOWN"]["pv"] - res["PAR_UP"]["pv"]) /
                      (2.0 * res["BASE"]["pv"] * prm.shock_parallel))
    for s in segs:
        ls = [l for l in loans if l.sid == s.sid]
        if not ls:
            continue
        d = {"n": len(ls), "bal": sum(l.balance for l in ls)}
        for sc in SCENARIOS:
            d[sc] = sum(out["loan"][l.lid][sc]["pv"] for l in ls)
        d["wal"] = sum(out["loan"][l.lid]["BASE"]["wal"] * l.balance for l in ls) / d["bal"]
        out["seg"][s.sid] = d
    # gap buckets
    gap = {sc: [0.0] * 19 for sc in SCENARIOS}
    gapp = {sc: [0.0] * 19 for sc in SCENARIOS}
    for sc in SCENARIOS:
        a = out["agg"][sc]
        for i in range(nmax):
            t = (i + 1) / 12.0
            b = bucket_of(t)
            gap[sc][b] += a["cf"][i]
            gapp[sc][b] += a["sched"][i] + a["prep"][i] + a["repr"][i]
    out["gap_cf"] = gap
    out["gap_prin"] = gapp
    return out


def bucket_of(t: float) -> int:
    for b, ub in enumerate(BUCKET_UPPER):
        if t <= ub + 1e-9:
            return b
    return 18


# ---------------------------------------------------------------------------
# Calibration (CORE_Calibrate): weighted least squares, Nelder-Mead
# ---------------------------------------------------------------------------
def unpack(th):
    cmin = logistic(th[0])
    cmax = cmin + (1.0 - cmin) * logistic(th[1])
    return cmin, cmax, math.exp(th[2]), th[3]


def objective(th, xs, ys, ws):
    cmin, cmax, slope, mid = unpack(th)
    sse = 0.0
    sw = 0.0
    for x, y, w in zip(xs, ys, ws):
        e = y - scurve(x, cmin, cmax, slope, mid)
        sse += w * e * e
        sw += w
    return sse / sw


def logit(p):
    return math.log(p / (1.0 - p))


def nelder_mead(fun, x0, steps, max_iter=4000, tol=1e-13):
    n = len(x0)
    pts = [list(x0)]
    for i in range(n):
        x = list(x0)
        x[i] += steps[i]
        pts.append(x)
    vals = [fun(p) for p in pts]
    it = 0
    while it < max_iter:
        # sort ascending, stable by index (insertion sort as in VBA)
        for i in range(1, n + 1):
            j = i
            while j > 0 and vals[j - 1] > vals[j]:
                vals[j - 1], vals[j] = vals[j], vals[j - 1]
                pts[j - 1], pts[j] = pts[j], pts[j - 1]
                j -= 1
        if vals[n] - vals[0] <= tol * (abs(vals[0]) + 1e-30):
            break
        it += 1
        cen = [sum(pts[i][d] for i in range(n)) / n for d in range(n)]
        xr = [cen[d] + 1.0 * (cen[d] - pts[n][d]) for d in range(n)]
        fr = fun(xr)
        if fr < vals[0]:
            xe = [cen[d] + 2.0 * (xr[d] - cen[d]) for d in range(n)]
            fe = fun(xe)
            if fe < fr:
                pts[n], vals[n] = xe, fe
            else:
                pts[n], vals[n] = xr, fr
        elif fr < vals[n - 1]:
            pts[n], vals[n] = xr, fr
        else:
            if fr < vals[n]:
                xc = [cen[d] + 0.5 * (xr[d] - cen[d]) for d in range(n)]
                fc = fun(xc)
                accept = fc <= fr
            else:
                xc = [cen[d] + 0.5 * (pts[n][d] - cen[d]) for d in range(n)]
                fc = fun(xc)
                accept = fc < vals[n]
            if accept:
                pts[n], vals[n] = xc, fc
            else:
                for i in range(1, n + 1):
                    pts[i] = [pts[0][d] + 0.5 * (pts[i][d] - pts[0][d]) for d in range(n)]
                    vals[i] = fun(pts[i])
    return pts[0], vals[0], it, it < max_iter


def calibrate(xs, ys, ws):
    ymin = min(max(min(ys), 0.001), 0.95)
    ymax = max(min(max(ys), 0.999), ymin + 0.01)
    x0 = [logit(ymin), logit((ymax - ymin) / (1.0 - ymin)), math.log(100.0),
          sum(x * w for x, w in zip(xs, ws)) / sum(ws)]
    fun = lambda th: objective(th, xs, ys, ws)
    steps = [0.5, 0.5, 0.25, 0.005]
    th, fv, it1, ok1 = nelder_mead(fun, x0, steps)
    th, fv, it2, ok2 = nelder_mead(fun, th, steps)          # one restart
    cmin, cmax, slope, mid = unpack(th)
    sw = sum(ws)
    ybar = sum(y * w for y, w in zip(ys, ws)) / sw
    sst = sum(w * (y - ybar) ** 2 for y, w in zip(ys, ws)) / sw
    return {"n": len(xs), "cmin": cmin, "cmax": cmax, "slope": slope, "mid": mid,
            "rmse": math.sqrt(fv), "r2": 1.0 - fv / sst, "iter": it1 + it2,
            "ok": ok1 and ok2}


# ---------------------------------------------------------------------------
# Illustrative data of the template
# ---------------------------------------------------------------------------
CURVE_T = [1 / 12, 0.25, 0.5, 1, 2, 3, 4, 5, 7, 10, 15, 20, 30, 50]
CURVE_R = [0.0190, 0.0192, 0.0195, 0.0200, 0.0205, 0.0212, 0.0220, 0.0228,
           0.0242, 0.0260, 0.0280, 0.0288, 0.0285, 0.0270]

SEASONALITY_RAW = [0.85, 0.85, 0.95, 1.00, 1.05, 1.15, 1.20, 0.90, 1.05,
                   1.05, 0.95, 1.00]
_ms = sum(SEASONALITY_RAW) / 12.0
SEASONALITY = [round(v / _ms, 6) for v in SEASONALITY_RAW]

SEGMENTS = [
    Segment("MTG_FIX", "Residential mortgages, fixed rate", 0.030, 0.250,
            250.0, 0.0100, 24, 1.5, 0.0120, 0.0, True),
    Segment("MTG_FLT", "Residential mortgages, floating rate", 0.0, 0.0,
            1.0, 0.0, 24, 0.0, 0.0, 0.040, True),
    Segment("CONS_FIX", "Consumer loans, fixed rate", 0.050, 0.200,
            150.0, 0.0200, 6, 0.5, 0.0400, 0.0, False),
    Segment("SME_FIX", "SME amortising loans, fixed rate", 0.015, 0.100,
            200.0, 0.0150, 12, 1.0, 0.0200, 0.0, False),
    Segment("SME_BUL", "SME bullet loans, fixed rate", 0.010, 0.060,
            200.0, 0.0150, 0, 0.0, 0.0200, 0.0, False),
]


def make_loans(prm: Params):
    rnd = random.Random(20261020)
    loans = []
    spec = [  # segment, count, rate type, amort, freq, bal range, rate range, term years, penalty
        ("MTG_FIX", 24, "FIXED", "ANNUITY", 1, (80e3, 320e3), (0.015, 0.050), (15, 30), 0.0),
        ("MTG_FLT", 12, "FLOAT", "ANNUITY", 1, (80e3, 280e3), (0.030, 0.042), (15, 30), 0.0),
        ("CONS_FIX", 12, "FIXED", "ANNUITY", 1, (5e3, 40e3), (0.050, 0.095), (3, 8), 0.0),
        ("SME_FIX", 12, "FIXED", "LINEAR", 3, (150e3, 900e3), (0.025, 0.060), (4, 10), 0.01),
        ("SME_BUL", 6, "FIXED", "BULLET", 12, (250e3, 1500e3), (0.030, 0.055), (2, 7), 0.01),
    ]
    n = 0
    for sid, cnt, rt, am, fq, br, rr, tr, pen in spec:
        for i in range(cnt):
            n += 1
            term = rnd.randint(tr[0], tr[1])
            age_m = rnd.randint(1, min(term * 12 - 6, 96))
            orig = add_months(prm.as_of, -age_m)
            orig = date(orig.year, orig.month, rnd.choice([5, 10, 15, 20, 25]))
            mat = add_months(orig, term * 12)
            bal = round(rnd.uniform(*br) / 100.0) * 100.0
            rate = round(rnd.uniform(*rr), 4)
            reset = None
            if rt == "FLOAT":
                nxt = rnd.randint(1, 3)
                reset = add_months(date(prm.as_of.year, prm.as_of.month, 1), nxt)
                reset = date(reset.year, reset.month, orig.day)
            loans.append(Loan(f"L{n:04d}", sid, rt, "EUR", bal, rate, orig, mat,
                              am, fq, reset, pen))
    return loans


def make_history(prm: Params):
    rnd = random.Random(7)
    rows = []
    for seg in SEGMENTS:
        if seg.cpr_max <= 0:
            continue
        for k in range(120):
            mdate = add_months(date(2016, 10, 31), k)
            inc = round(rnd.uniform(-0.025, 0.045), 5)
            true = scurve(inc, seg.cpr_min, seg.cpr_max, seg.slope, seg.mid)
            obs = min(1.0, max(0.0, true + rnd.gauss(0.0, 0.008)))
            w = round(rnd.uniform(2e6, 12e6) / 1000.0) * 1000.0
            rows.append((mdate, seg.sid, inc, round(obs, 6), w))
    return rows


def build():
    prm = Params()
    curve = Curve(CURVE_T, CURVE_R, prm)
    loans = make_loans(prm)
    out = run_book(loans, SEGMENTS, SEASONALITY, curve, prm)
    hist = make_history(prm)
    cal = {}
    for seg in SEGMENTS:
        rows = [h for h in hist if h[1] == seg.sid]
        if rows:
            cal[seg.sid] = calibrate([r[2] for r in rows], [r[3] for r in rows],
                                     [r[4] for r in rows])
    return prm, curve, loans, out, hist, cal


if __name__ == "__main__":
    prm, curve, loans, out, hist, cal = build()
    print("loans", len(loans), "balance", round(out["balance"], 2), "months", out["nmax"])
    for sc in SCENARIOS:
        r = out["res"][sc]
        print(f"{sc:10s} PV {r['pv']:16,.2f} dEVE {r['deve']:14,.2f} {r['deve_t1']:8.4%} "
              f"WAL {r['wal']:6.3f} CPR1 {r['cpr1']:7.4%} CPRl {r['cprl']:7.4%}")
    print("eff dur", out["eff_dur"])
    for k, v in cal.items():
        print(k, {a: (round(b, 6) if isinstance(b, float) else b) for a, b in v.items()})
    prm2 = Params(mode="BCBS_SA")
    out2 = run_book(loans, SEGMENTS, SEASONALITY, Curve(CURVE_T, CURVE_R, prm2), prm2)
    for sc in SCENARIOS:
        r = out2["res"][sc]
        print(f"SA {sc:10s} PV {r['pv']:16,.2f} dEVE {r['deve']:14,.2f} CPR1 {r['cpr1']:7.4%}")
