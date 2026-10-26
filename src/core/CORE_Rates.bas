Attribute VB_Name = "CORE_Rates"
'==============================================================================
' MODULE: CORE_Rates
'------------------------------------------------------------------------------
' PURPOSE
'   Conversions between the monthly prepayment rate (SMM) and its annualised
'   equivalent (CPR), as specified in docs/methodology/MODEL_CONTRACTS.md,
'   section "CPR and SMM":
'       CPR = 1 - (1 - SMM)^12        SMM = 1 - (1 - CPR)^(1/12)
'   CPR / 12 is never used as a monthly rate.
'
' NUMERICS
'   Both conversions are evaluated through log1p and expm1 so that rates
'   close to 0 keep full relative precision. Rates of exactly 1 map to 1.
'
' BOUNDS
'   Arguments are decimals in [0, 1]. This module does not validate them;
'   PREPAY_Rates does, before calling it.
'
' DEPENDENCIES
'   None. Scalars only; no workbook, UI, file or COM access.
'==============================================================================

Option Explicit
Option Private Module

Public Function CORE_CprFromSmm(ByVal Smm As Double) As Double
    'Annualised CPR of a constant monthly rate Smm in [0, 1].
    If Smm >= 1# Then
        CORE_CprFromSmm = 1#
    Else
        CORE_CprFromSmm = -Expm1(12# * Log1p(-Smm))
    End If
End Function

Public Function CORE_SmmFromCpr(ByVal Cpr As Double) As Double
    'Constant monthly rate SMM equivalent to an annual Cpr in [0, 1].
    If Cpr >= 1# Then
        CORE_SmmFromCpr = 1#
    Else
        CORE_SmmFromCpr = -Expm1(Log1p(-Cpr) / 12#)
    End If
End Function

Private Function Log1p(ByVal X As Double) As Double
    'log(1 + x) for x > -1, accurate for small x (Goldberg/Kahan correction).
    Dim U As Double
    U = 1# + X
    If U = 1# Then
        Log1p = X
    Else
        Log1p = Log(U) * X / (U - 1#)
    End If
End Function

Private Function Expm1(ByVal X As Double) As Double
    'exp(x) - 1, accurate for small x (Kahan correction).
    Dim U As Double
    U = Exp(X)
    If U = 1# Then
        Expm1 = X
    ElseIf U - 1# = -1# Then
        Expm1 = -1#
    Else
        Expm1 = (U - 1#) * X / Log(U)
    End If
End Function
