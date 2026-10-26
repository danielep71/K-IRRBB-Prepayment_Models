Attribute VB_Name = "PREPAY_Rates"
'==============================================================================
' MODULE: PREPAY_Rates
'------------------------------------------------------------------------------
' PURPOSE
'   Supported facade for the SMM and CPR conversions of
'   docs/methodology/MODEL_CONTRACTS.md, section "CPR and SMM". Listed in
'   docs/PUBLIC_API.txt.
'
' UNITS AND BOUNDS
'   SMM is a monthly rate and CPR an annual rate, both decimals in [0, 1]
'   (0.02 = 2 %).
'
' FAILURE
'   An argument outside [0, 1], or not a number, raises error
'   vbObjectError + 1001 with source "PREPAY_Rates" before any calculation.
'   No value is clamped.
'
' DEPENDENCIES
'   CORE_Rates.
'==============================================================================

Option Explicit

Private Const ERR_RANGE As Long = 1001
Private Const SOURCE As String = "PREPAY_Rates"

Public Function PREPAY_CprFromSmm(ByVal Smm As Double) As Double
    'CPR = 1 - (1 - SMM)^12 for a monthly rate Smm in [0, 1].
    CheckRate Smm, "Smm"
    PREPAY_CprFromSmm = CORE_CprFromSmm(Smm)
End Function

Public Function PREPAY_SmmFromCpr(ByVal Cpr As Double) As Double
    'SMM = 1 - (1 - CPR)^(1/12) for an annual rate Cpr in [0, 1].
    CheckRate Cpr, "Cpr"
    PREPAY_SmmFromCpr = CORE_SmmFromCpr(Cpr)
End Function

Private Sub CheckRate(ByVal Value As Double, ByVal Name As String)
    'NaN fails every comparison, so test for the valid range positively.
    If Not (Value >= 0# And Value <= 1#) Then
        Err.Raise vbObjectError + ERR_RANGE, SOURCE, _
                  Name & " must be a decimal rate in [0, 1]; got " & CStr(Value)
    End If
End Sub
