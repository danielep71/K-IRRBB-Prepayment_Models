Attribute VB_Name = "TEST_Rates"
'==============================================================================
' MODULE: TEST_Rates
'------------------------------------------------------------------------------
' PURPOSE
'   VBA tests of the SMM and CPR conversions, run by TEST_Harness.
'
' CASES
'   RATE-CONV-01  Round trips SMM -> CPR -> SMM and CPR -> SMM -> CPR on the
'                 grid of docs/methodology/TEST_CASES.md; rel 1e-12. At
'                 SMM 0.999999 the CPR, 1 - 1e-72, rounds to 1 in double
'                 precision, so no round trip exists; that point checks
'                 CPR = 1 instead.
'   RATE-CONV-02  Worked check of the model contracts: A = 99,000,
'                 SMM = 2,000 / 99,000, CPR = 1 - (1 - SMM)^12; abs 1e-12.
'                 Expected values computed outside the toolkit with the
'                 Python 3.13 decimal module at 50 digits on 2026-10-26,
'                 rounded to double: SMM 0.020202020202020204,
'                 CPR 0.21722224381820712.
'   UNIT-RATE-BOUNDS-01  The facade rejects rates outside [0, 1] with
'                 vbObjectError + 1001; not a register case.
'==============================================================================

Option Explicit
Option Private Module

'Long and very small literals are written as Val strings: the VBE re-prints
'numeric literals, which would change the exported source and may round them.
Private Function Tol() As Double
    Tol = Val("1E-12")
End Function

Public Sub TEST_RateConv01()
    Dim Grid As Variant, I As Long, X As Double
    Grid = Array(0#, Val("1E-08"), 0.02, 0.5, 0.999999, 1#)
    For I = LBound(Grid) To UBound(Grid)
        X = Grid(I)
        If X = 0.999999 Then
            TEST_Harness.TEST_CheckNear "CPR at SMM " & CStr(X), PREPAY_CprFromSmm(X), 1#, 0#
        Else
            TEST_Harness.TEST_CheckNear "SMM round trip at " & CStr(X), _
                PREPAY_SmmFromCpr(PREPAY_CprFromSmm(X)), X, Tol(), True
        End If
        TEST_Harness.TEST_CheckNear "CPR round trip at " & CStr(X), _
            PREPAY_CprFromSmm(PREPAY_SmmFromCpr(X)), X, Tol(), True
    Next I
End Sub

Public Sub TEST_RateConv02()
    Dim Available As Double, Smm As Double
    Available = 100000# - 1000#    'balance(t-1) - scheduled_principal, no other_change
    Smm = 2000# / Available
    TEST_Harness.TEST_CheckNear "available amount A", Available, 99000#, Tol()
    TEST_Harness.TEST_CheckNear "SMM", Smm, Val("0.020202020202020204"), Tol()
    TEST_Harness.TEST_CheckNear "CPR", PREPAY_CprFromSmm(Smm), Val("0.21722224381820712"), Tol()
    TEST_Harness.TEST_CheckNear "SMM from CPR", PREPAY_SmmFromCpr(Val("0.21722224381820712")), _
        Val("0.020202020202020204"), Tol()
End Sub

Public Sub TEST_RateBounds01()
    TEST_Harness.TEST_CheckTrue "SMM -0.01 rejected", Rejects(-0.01, True)
    TEST_Harness.TEST_CheckTrue "SMM 1.01 rejected", Rejects(1.01, True)
    TEST_Harness.TEST_CheckTrue "CPR -0.01 rejected", Rejects(-0.01, False)
    TEST_Harness.TEST_CheckTrue "CPR 1.01 rejected", Rejects(1.01, False)
    TEST_Harness.TEST_CheckTrue "SMM 0 accepted", Not Rejects(0#, True)
    TEST_Harness.TEST_CheckTrue "CPR 1 accepted", Not Rejects(1#, False)
End Sub

Private Function Rejects(ByVal Value As Double, ByVal FromSmm As Boolean) As Boolean
    'True when the facade raises its range error for Value.
    Dim Result As Double
    On Error GoTo Raised
    If FromSmm Then
        Result = PREPAY_CprFromSmm(Value)
    Else
        Result = PREPAY_SmmFromCpr(Value)
    End If
    Rejects = False
    Exit Function
Raised:
    Rejects = (Err.Number = vbObjectError + 1001)
End Function
