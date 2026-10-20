Attribute VB_Name = "PPM_Formulas"
'==============================================================================
' MODULE: PPM_Formulas
'------------------------------------------------------------------------------
' PURPOSE
'   Expose the building blocks of the prepayment model as worksheet
'   functions, so that each rule can be checked cell by cell (Tests sheet)
'   and reused in the user's own analysis.
'
' PUBLIC SURFACE
'   PPM_SMM(CPR); PPM_CPRFromSMM(SMM);
'   PPM_SCurveCPR(Incentive, CprMin, CprMax, Slope, Midpoint, [Burnout]);
'   PPM_AnnuityPrincipal(Balance, Rate, PaymentsLeft, FrequencyMonths);
'   PPM_Shock(Scenario, T, Parallel, Short, Long, [Decay]);
'   PPM_LowerBound(T, ObservedRate, [FloorStart], [FloorSlope]).
'
' DEPENDENCIES
'   CORE_Prepay, CORE_Curve, CORE_Config.
'
' STATE OWNERSHIP
'   None; pure functions.
'
' ERROR POLICY
'   Worksheet functions never raise: an input outside its domain returns
'   #VALUE! (xlErrValue) or #NUM! (xlErrNum).
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
    'Public, so that the functions are visible to worksheet formulas.
    Option Explicit


'
'------------------------------------------------------------------------------
'
'                             WORKSHEET FUNCTIONS
'
'------------------------------------------------------------------------------
'

Public Function PPM_SMM( _
    ByVal CPR As Variant) _
    As Variant
'
'==============================================================================
'                                   PPM_SMM
'------------------------------------------------------------------------------
' PURPOSE
'   Single monthly mortality of an annual CPR: 1 - (1 - CPR)^(1/12).
'
' INPUTS
'   CPR: decimal, 0 <= CPR <= 1.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        On Error GoTo Failed
        If Not IsNumeric(CPR) Then GoTo Failed
        If CPR < 0 Or CPR > 1 Then
            PPM_SMM = CVErr(xlErrNum)
            Exit Function
        End If
        PPM_SMM = SmmFromCpr(CDbl(CPR))
        Exit Function
Failed:
        PPM_SMM = CVErr(xlErrValue)

End Function


Public Function PPM_CPRFromSMM( _
    ByVal SMM As Variant) _
    As Variant
'
'==============================================================================
'                                PPM_CPRFromSMM
'------------------------------------------------------------------------------
' PURPOSE
'   Annual CPR of a single monthly mortality: 1 - (1 - SMM)^12.
'
' INPUTS
'   SMM: decimal, 0 <= SMM <= 1.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        On Error GoTo Failed
        If Not IsNumeric(SMM) Then GoTo Failed
        If SMM < 0 Or SMM > 1 Then
            PPM_CPRFromSMM = CVErr(xlErrNum)
            Exit Function
        End If
        PPM_CPRFromSMM = CprFromSmm(CDbl(SMM))
        Exit Function
Failed:
        PPM_CPRFromSMM = CVErr(xlErrValue)

End Function


Public Function PPM_SCurveCPR( _
    ByVal Incentive As Variant, _
    ByVal CprMin As Variant, _
    ByVal CprMax As Variant, _
    ByVal Slope As Variant, _
    ByVal Midpoint As Variant, _
    Optional ByVal Burnout As Variant = 1) _
    As Variant
'
'==============================================================================
'                                PPM_SCurveCPR
'------------------------------------------------------------------------------
' PURPOSE
'   Annual CPR of the logistic S-curve: CprMin + (CprMax - CprMin) x
'   Burnout / (1 + exp(-Slope x (Incentive - Midpoint))).
'
' INPUTS
'   Incentive, Midpoint: decimals. 0 <= CprMin <= CprMax <= 1. Slope > 0,
'   per unit of incentive. 0 <= Burnout <= 1 (default 1).
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        On Error GoTo Failed
        If Not (IsNumeric(Incentive) And IsNumeric(CprMin) And IsNumeric(CprMax) And IsNumeric(Slope) And _
                IsNumeric(Midpoint) And IsNumeric(Burnout)) Then GoTo Failed
        If CprMin < 0 Or CprMax > 1 Or CprMax < CprMin Or Slope <= 0 Or Burnout < 0 Or Burnout > 1 Then
            PPM_SCurveCPR = CVErr(xlErrNum)
            Exit Function
        End If
        PPM_SCurveCPR = SCurveCPR(CDbl(Incentive), CDbl(CprMin), CDbl(CprMax), CDbl(Slope), CDbl(Midpoint), _
                                  CDbl(Burnout))
        Exit Function
Failed:
        PPM_SCurveCPR = CVErr(xlErrValue)

End Function


Public Function PPM_AnnuityPrincipal( _
    ByVal Balance As Variant, _
    ByVal Rate As Variant, _
    ByVal PaymentsLeft As Variant, _
    Optional ByVal FrequencyMonths As Variant = 1) _
    As Variant
'
'==============================================================================
'                             PPM_AnnuityPrincipal
'------------------------------------------------------------------------------
' PURPOSE
'   Principal part of the next annuity payment: B x j / ((1 + j)^n - 1),
'   j = Rate x FrequencyMonths / 12; B / n when j = 0.
'
' INPUTS
'   Balance >= 0. Rate: annual, decimal. PaymentsLeft: whole number >= 1.
'   FrequencyMonths: 1, 2, 3, 4, 6 or 12 (default 1).
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim PeriodRate     As Double    'Rate per payment period
    Dim Payments       As Long      'Payments left

        On Error GoTo Failed
        If Not (IsNumeric(Balance) And IsNumeric(Rate) And IsNumeric(PaymentsLeft) And IsNumeric(FrequencyMonths)) Then
            GoTo Failed
        End If
        If Balance < 0 Or PaymentsLeft < 1 Or PaymentsLeft <> Int(PaymentsLeft) Or FrequencyMonths < 1 Then
            PPM_AnnuityPrincipal = CVErr(xlErrNum)
            Exit Function
        End If
        Payments = CLng(PaymentsLeft)
        PeriodRate = CDbl(Rate) * CDbl(FrequencyMonths) / 12#
        If Abs(PeriodRate) < 0.000000000001 Then
            PPM_AnnuityPrincipal = CDbl(Balance) / Payments
        Else
            PPM_AnnuityPrincipal = CDbl(Balance) * PeriodRate / ((1# + PeriodRate) ^ Payments - 1#)
        End If
        Exit Function
Failed:
        PPM_AnnuityPrincipal = CVErr(xlErrValue)

End Function


Public Function PPM_Shock( _
    ByVal Scenario As Variant, _
    ByVal T As Variant, _
    ByVal ShockParallel As Variant, _
    ByVal ShockShort As Variant, _
    ByVal ShockLong As Variant, _
    Optional ByVal Decay As Variant = 4) _
    As Variant
'
'==============================================================================
'                                  PPM_Shock
'------------------------------------------------------------------------------
' PURPOSE
'   Rate shock of an IRRBB scenario at time T (BCBS d368 Annex 2).
'
' INPUTS
'   Scenario: PAR_UP, PAR_DOWN, STEEPENER, FLATTENER, SHORT_UP or
'   SHORT_DOWN (BASE and CONTRACT give 0). T: years >= 0. Shock sizes:
'   decimals >= 0. Decay: years > 0 (default 4).
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Index          As Long    'Scenario index

        On Error GoTo Failed
        If Not (IsNumeric(T) And IsNumeric(ShockParallel) And IsNumeric(ShockShort) And IsNumeric(ShockLong) And _
                IsNumeric(Decay)) Then GoTo Failed
        Index = ScenarioIndex(CStr(Scenario))
        If Index = 0 Or T < 0 Or Decay <= 0 Or _
           ShockParallel < 0 Or ShockShort < 0 Or ShockLong < 0 Then
            PPM_Shock = CVErr(xlErrNum)
            Exit Function
        End If
        PPM_Shock = ShockSize(Index, CDbl(T), CDbl(ShockParallel), CDbl(ShockShort), CDbl(ShockLong), CDbl(Decay))
        Exit Function
Failed:
        PPM_Shock = CVErr(xlErrValue)

End Function


Public Function PPM_LowerBound( _
    ByVal T As Variant, _
    ByVal ObservedRate As Variant, _
    Optional ByVal FloorStart As Variant = -0.015, _
    Optional ByVal FloorSlope As Variant = 0.0003) _
    As Variant
'
'==============================================================================
'                                PPM_LowerBound
'------------------------------------------------------------------------------
' PURPOSE
'   Post-shock lower bound of the zero rate at time T: min(observed rate,
'   min(0, FloorStart + FloorSlope x T)) (Reg. (EU) 2024/856 Art. 3(7)).
'
' INPUTS
'   T: years >= 0. ObservedRate: base zero rate at T, decimal.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        On Error GoTo Failed
        If Not (IsNumeric(T) And IsNumeric(ObservedRate) And IsNumeric(FloorStart) And IsNumeric(FloorSlope)) Then
            GoTo Failed
        End If
        If T < 0 Then
            PPM_LowerBound = CVErr(xlErrNum)
            Exit Function
        End If
        PPM_LowerBound = LowerBound(CDbl(T), CDbl(ObservedRate), CDbl(FloorStart), CDbl(FloorSlope))
        Exit Function
Failed:
        PPM_LowerBound = CVErr(xlErrValue)

End Function
