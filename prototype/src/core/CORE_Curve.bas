Attribute VB_Name = "CORE_Curve"
'==============================================================================
' MODULE: CORE_Curve
'------------------------------------------------------------------------------
' PURPOSE
'   Interest-rate curve arithmetic of the model: the base zero rate by
'   linear interpolation, the six IRRBB shock shapes, the post-shock lower
'   bound, the shocked zero rate and the discount factor.
'
' PUBLIC SURFACE
'   None outside this VBA project (Option Private Module). PPM_Formulas
'   exposes ShockSize and LowerBound as worksheet functions.
'
' DEPENDENCIES
'   CORE_Config for the scenario indices and shape coefficients.
'
' STATE OWNERSHIP
'   Pure functions of their arguments; no state, no Excel access.
'
' ERROR POLICY
'   Callers validate the curve (at least one point, tenors increasing);
'   these functions assume it and do not raise.
'
' REFERENCE
'   BCBS d368 (April 2016) Annex 2: shock shapes, x = 4; continuously
'   compounded zero rates. Reg. (EU) 2024/856 Annex Part A (EUR shock
'   sizes) and Art. 3(7) (lower bound -150 bp + 3 bp per year, 0 at 50
'   years; the observed rate when it is lower).
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
'                                  BASE CURVE
'
'------------------------------------------------------------------------------
'

Public Function BaseZero( _
    ByRef Tenors() As Double, _
    ByRef Rates() As Double, _
    ByVal PointCount As Long, _
    ByVal T As Double) _
    As Double
'
'==============================================================================
'                                   BaseZero
'------------------------------------------------------------------------------
' PURPOSE
'   Base zero rate for time T, linear in the rate between curve points and
'   flat beyond the first and the last point.
'
' INPUTS
'   Tenors, Rates: 1-based, PointCount >= 1 points, tenors strictly
'   increasing, in years; rates continuously compounded decimals.
'   T: years, >= 0.
'
' RETURNS
'   The zero rate, decimal.
'
' REFERENCE
'   tools/reference_model.py Curve.base.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim i              As Long      'Curve point
    Dim Weight         As Double    'Interpolation weight

        If T <= Tenors(1) Then
            BaseZero = Rates(1)
            Exit Function
        End If
        If T >= Tenors(PointCount) Then
            BaseZero = Rates(PointCount)
            Exit Function
        End If
        For i = 2 To PointCount
            If T <= Tenors(i) Then
                Weight = (T - Tenors(i - 1)) / (Tenors(i) - Tenors(i - 1))
                BaseZero = Rates(i - 1) + Weight * (Rates(i) - Rates(i - 1))
                Exit Function
            End If
        Next i
        BaseZero = Rates(PointCount)

End Function


'
'------------------------------------------------------------------------------
'
'                               SHOCK SCENARIOS
'
'------------------------------------------------------------------------------
'

Public Function ShockSize( _
    ByVal Scenario As Long, _
    ByVal T As Double, _
    ByVal ShockParallel As Double, _
    ByVal ShockShort As Double, _
    ByVal ShockLong As Double, _
    ByVal Decay As Double) _
    As Double
'
'==============================================================================
'                                  ShockSize
'------------------------------------------------------------------------------
' PURPOSE
'   Rate change of a scenario at time T.
'
' INPUTS
'   Scenario: SC_CONTRACT ... SC_SHORT_DOWN; CONTRACT and BASE give 0.
'   T: years, >= 0. Shock sizes: decimals, >= 0. Decay: years, > 0.
'
' RETURNS
'   The shock, decimal (positive = rates up).
'
' REFERENCE
'   BCBS d368 Annex 2: short = R_short x exp(-T / x); long =
'   R_long x (1 - exp(-T / x)); steepener = -0.65 |short| + 0.9 |long|;
'   flattener = 0.8 |short| - 0.6 |long|.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim ShortShape     As Double    'Short-rate shock at T
    Dim LongShape      As Double    'Long-rate shock at T

        ShortShape = ShockShort * Exp(-T / Decay)
        LongShape = ShockLong * (1# - Exp(-T / Decay))
        Select Case Scenario
            Case SC_PAR_UP
                ShockSize = ShockParallel
            Case SC_PAR_DOWN
                ShockSize = -ShockParallel
            Case SC_SHORT_UP
                ShockSize = ShortShape
            Case SC_SHORT_DOWN
                ShockSize = -ShortShape
            Case SC_STEEPENER
                ShockSize = STEEP_SHORT * Abs(ShortShape) + STEEP_LONG * Abs(LongShape)
            Case SC_FLATTENER
                ShockSize = FLAT_SHORT * Abs(ShortShape) + FLAT_LONG * Abs(LongShape)
            Case Else
                ShockSize = 0#
        End Select

End Function


Public Function LowerBound( _
    ByVal T As Double, _
    ByVal ObservedRate As Double, _
    ByVal FloorStart As Double, _
    ByVal FloorSlope As Double) _
    As Double
'
'==============================================================================
'                                  LowerBound
'------------------------------------------------------------------------------
' PURPOSE
'   Post-shock lower bound of the zero rate at time T.
'
' INPUTS
'   T: years. ObservedRate: base zero rate at T. FloorStart: bound at 0
'   years (-0.015). FloorSlope: increase per year (0.0003).
'
' RETURNS
'   min(observed rate, min(0, FloorStart + FloorSlope x T)).
'
' REFERENCE
'   Reg. (EU) 2024/856 Art. 3(7).
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Bound          As Double    'Regulatory bound before the observed rate

        Bound = FloorStart + FloorSlope * T
        If Bound > 0# Then Bound = 0#
        If ObservedRate < Bound Then Bound = ObservedRate
        LowerBound = Bound

End Function


Public Function ScenarioZero( _
    ByVal Scenario As Long, _
    ByVal T As Double, _
    ByRef Tenors() As Double, _
    ByRef Rates() As Double, _
    ByVal PointCount As Long, _
    ByVal ShockParallel As Double, _
    ByVal ShockShort As Double, _
    ByVal ShockLong As Double, _
    ByVal Decay As Double, _
    ByVal ApplyFloor As Boolean, _
    ByVal FloorStart As Double, _
    ByVal FloorSlope As Double) _
    As Double
'
'==============================================================================
'                                 ScenarioZero
'------------------------------------------------------------------------------
' PURPOSE
'   Zero rate of a scenario at time T: base rate plus shock, floored at
'   the lower bound when ApplyFloor is True. CONTRACT and BASE return the
'   base rate unfloored.
'
' RETURNS
'   Continuously compounded zero rate, decimal.
'
' REFERENCE
'   tools/reference_model.py Curve.zero.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim BaseRate       As Double    'Base zero rate at T
    Dim Shocked        As Double    'Rate after the shock
    Dim Bound          As Double    'Lower bound at T

        BaseRate = BaseZero(Tenors, Rates, PointCount, T)
        If Scenario = SC_CONTRACT Or Scenario = SC_BASE Then
            ScenarioZero = BaseRate
            Exit Function
        End If
        Shocked = BaseRate + ShockSize(Scenario, T, ShockParallel, ShockShort, ShockLong, Decay)
        If ApplyFloor Then
            Bound = LowerBound(T, BaseRate, FloorStart, FloorSlope)
            If Shocked < Bound Then Shocked = Bound
        End If
        ScenarioZero = Shocked

End Function


Public Function ScenarioIndex( _
    ByVal Code As String) _
    As Long
'
'==============================================================================
'                                ScenarioIndex
'------------------------------------------------------------------------------
' PURPOSE
'   Scenario index of a code (case and spaces ignored); 0 when unknown.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Codes          As Variant    'Scenario codes, 0-based
    Dim i              As Long       'Code index

        Codes = Split(SCEN_CODES, ",")
        For i = 0 To UBound(Codes)
            If UCase$(Trim$(Code)) = Codes(i) Then
                ScenarioIndex = i + 1
                Exit Function
            End If
        Next i
        ScenarioIndex = 0

End Function
