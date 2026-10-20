Attribute VB_Name = "CORE_Prepay"
'==============================================================================
' MODULE: CORE_Prepay
'------------------------------------------------------------------------------
' PURPOSE
'   The prepayment function of the model: the logistic S-curve of the
'   annual conditional prepayment rate (CPR) in the refinancing
'   incentive, its burnout, seasoning and seasonality multipliers, and the
'   conversion between CPR and the single monthly mortality (SMM).
'
' PUBLIC SURFACE
'   None outside this VBA project (Option Private Module). PPM_Formulas
'   exposes SCurveCPR, SmmFromCpr and CprFromSmm as worksheet functions.
'
' DEPENDENCIES
'   None.
'
' STATE OWNERSHIP
'   Pure functions of their arguments; no state, no Excel access.
'
' ERROR POLICY
'   Callers validate the domains (0 <= CPR min <= CPR max <= 1, slope > 0);
'   these functions do not raise.
'
' REFERENCE
'   tools/reference_model.py logistic, scurve, smm and project; README
'   "Prepayment function".
'
' UPDATED
'   2026-10-20
'
' AUTHOR
'   Daniele Penza
'==============================================================================

'------------------------------------------------------------------------------
' MODULE SETTINGS
'------------------------------------------------------------------------------
    Option Explicit
    Option Private Module


'
'------------------------------------------------------------------------------
'
'                              PREPAYMENT RATES
'
'------------------------------------------------------------------------------
'

Public Function Logistic( _
    ByVal X As Double) _
    As Double
'
'==============================================================================
'                                   Logistic
'------------------------------------------------------------------------------
' PURPOSE
'   1 / (1 + exp(-X)), evaluated without overflow for large |X|.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim E              As Double    'exp(X) for negative X

        If X >= 0# Then
            Logistic = 1# / (1# + Exp(-X))
        Else
            If X < -700# Then
                Logistic = 0#
                Exit Function
            End If
            E = Exp(X)
            Logistic = E / (1# + E)
        End If

End Function


Public Function SCurveCPR( _
    ByVal Incentive As Double, _
    ByVal CprMin As Double, _
    ByVal CprMax As Double, _
    ByVal Slope As Double, _
    ByVal Midpoint As Double, _
    Optional ByVal Burnout As Double = 1#) _
    As Double
'
'==============================================================================
'                                  SCurveCPR
'------------------------------------------------------------------------------
' PURPOSE
'   Annual CPR of the S-curve before seasoning and seasonality.
'
' INPUTS
'   Incentive: decimal (client rate - refinancing rate - penalty cost).
'   CprMin, CprMax: annual CPR at very negative / positive incentive,
'   0 <= CprMin <= CprMax <= 1. Slope: per unit of incentive, > 0.
'   Midpoint: incentive of the inflection, decimal. Burnout: multiplier
'   of the incentive response, 0 < Burnout <= 1.
'
' RETURNS
'   CprMin + (CprMax - CprMin) x Burnout x Logistic(Slope x (Incentive -
'   Midpoint)), decimal.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        SCurveCPR = CprMin + (CprMax - CprMin) * Burnout * Logistic(Slope * (Incentive - Midpoint))

End Function


Public Function SmmFromCpr( _
    ByVal Cpr As Double) _
    As Double
'
'==============================================================================
'                                  SmmFromCpr
'------------------------------------------------------------------------------
' PURPOSE
'   Single monthly mortality of an annual CPR: 1 - (1 - CPR)^(1/12).
'
' INPUTS
'   Cpr: decimal, 0 <= Cpr <= 1; 1 or more gives 1.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        If Cpr >= 1# Then
            SmmFromCpr = 1#
        Else
            SmmFromCpr = 1# - (1# - Cpr) ^ (1# / 12#)
        End If

End Function


Public Function CprFromSmm( _
    ByVal Smm As Double) _
    As Double
'
'==============================================================================
'                                  CprFromSmm
'------------------------------------------------------------------------------
' PURPOSE
'   Annual CPR of a single monthly mortality: 1 - (1 - SMM)^12.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        If Smm >= 1# Then
            CprFromSmm = 1#
        Else
            CprFromSmm = 1# - (1# - Smm) ^ 12#
        End If

End Function


Public Function BehaviouralCPR( _
    ByVal ClientRate As Double, _
    ByVal RefinancingZero As Double, _
    ByVal RefinancingMargin As Double, _
    ByVal Penalty As Double, _
    ByVal RemainingYears As Double, _
    ByVal CprMin As Double, _
    ByVal CprMax As Double, _
    ByVal Slope As Double, _
    ByVal Midpoint As Double, _
    ByVal BurnoutSpeed As Double, _
    ByVal Survival As Double, _
    ByVal Ramp As Double, _
    ByVal Season As Double) _
    As Double
'
'==============================================================================
'                                BehaviouralCPR
'------------------------------------------------------------------------------
' PURPOSE
'   Annual CPR of a fixed-rate loan in one projection month.
'
' INPUTS
'   ClientRate: loan rate, decimal. RefinancingZero: scenario zero rate
'   for the remaining maturity. RefinancingMargin: spread at which the
'   borrower can refinance. Penalty: share of the prepaid amount, >= 0.
'   RemainingYears: maturity left at the start of the month, > 0.
'   CprMin ... Midpoint: S-curve of the segment. BurnoutSpeed: >= 0.
'   Survival: share of the balance not yet prepaid, 0 < Survival <= 1.
'   Ramp: seasoning multiplier, 0 to 1. Season: calendar multiplier.
'
' RETURNS
'   min(1, max(0, S-curve x Ramp x Season)), decimal.
'
' REFERENCE
'   Incentive = ClientRate - (RefinancingZero + RefinancingMargin) -
'   Penalty / max(RemainingYears, 1); Burnout = exp(-BurnoutSpeed x (1 -
'   Survival)). tools/reference_model.py project.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Refinancing    As Double    'Rate the borrower can refinance at
    Dim PenaltyYears   As Double    'Years over which the penalty is spread
    Dim Incentive      As Double    'Refinancing incentive, decimal
    Dim Burnout        As Double    'Multiplier of the incentive response
    Dim Result         As Double    'CPR

        Refinancing = RefinancingZero + RefinancingMargin
        PenaltyYears = RemainingYears
        If PenaltyYears < 1# Then PenaltyYears = 1#
        Incentive = ClientRate - Refinancing - Penalty / PenaltyYears
        Burnout = Exp(-BurnoutSpeed * (1# - Survival))
        Result = SCurveCPR(Incentive, CprMin, CprMax, Slope, Midpoint, Burnout) * Ramp * Season
        If Result > 1# Then Result = 1#
        If Result < 0# Then Result = 0#
        BehaviouralCPR = Result

End Function


Public Function SeasoningRamp( _
    ByVal AgeMonths As Long, _
    ByVal RampMonths As Long) _
    As Double
'
'==============================================================================
'                                SeasoningRamp
'------------------------------------------------------------------------------
' PURPOSE
'   min(1, AgeMonths / RampMonths); 1 when RampMonths <= 0.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        If RampMonths <= 0 Then
            SeasoningRamp = 1#
        ElseIf AgeMonths >= RampMonths Then
            SeasoningRamp = 1#
        Else
            SeasoningRamp = AgeMonths / RampMonths
        End If

End Function
