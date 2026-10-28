Attribute VB_Name = "CORE_Parse"
'==============================================================================
' MODULE: CORE_Parse
'------------------------------------------------------------------------------
' PURPOSE
'   Locale-independent parsing of the field types of the file format in
'   docs/methodology/DATA_CONTRACT.md: ISO dates, month ends, decimals and
'   codes, and the canonical text of a decimal. Never uses CDate, CDbl, Val
'   or any other conversion that depends on the host locale.
'
' DATES
'   YYYY-MM-DD, year 1900 to 9999, a real calendar date.
'
' DECIMALS
'   An optional leading "-", digits, and optionally "." followed by digits;
'   no "+", thousands separator or exponent; leading zeros are accepted
'   (decision D16). At most Places digits after the point, and an absolute
'   value below 10^15 (decision D17), so the value and every total of such
'   values are exact in a VBA Decimal. The value is a Variant of subtype
'   Decimal, built digit by digit.
'
' CODES
'   Exact, case-sensitive members of the code lists of the data contract.
'
' DEPENDENCIES
'   None. Scalars only; no workbook, UI, file or COM access.
'==============================================================================

Option Explicit
Option Private Module

Private Const MAX_INTEGER_DIGITS As Long = 15    'decision D17: below 10^15

Public Function CORE_ParseDate(ByVal Text As String, ByRef Value As Date) As Boolean
    'True and Value set when Text is an ISO date YYYY-MM-DD from 1900 to 9999.
    Dim Y As Long, M As Long, D As Long
    If Len(Text) <> 10 Then Exit Function
    If Mid$(Text, 5, 1) <> "-" Or Mid$(Text, 8, 1) <> "-" Then Exit Function
    If Not Digits(Mid$(Text, 1, 4), Y) Then Exit Function
    If Not Digits(Mid$(Text, 6, 2), M) Then Exit Function
    If Not Digits(Mid$(Text, 9, 2), D) Then Exit Function
    If Y < 1900 Or Y > 9999 Or M < 1 Or M > 12 Then Exit Function
    If D < 1 Or D > CORE_DaysInMonth(Y, M) Then Exit Function
    Value = DateSerial(Y, M, D)
    CORE_ParseDate = True
End Function

Public Function CORE_DaysInMonth(ByVal Y As Long, ByVal M As Long) As Long
    'Days in month M of year Y in the Gregorian calendar.
    Select Case M
        Case 4, 6, 9, 11
            CORE_DaysInMonth = 30
        Case 2
            If (Y Mod 4 = 0 And Y Mod 100 <> 0) Or Y Mod 400 = 0 Then
                CORE_DaysInMonth = 29
            Else
                CORE_DaysInMonth = 28
            End If
        Case Else
            CORE_DaysInMonth = 31
    End Select
End Function

Public Function CORE_IsMonthEnd(ByVal Value As Date) As Boolean
    CORE_IsMonthEnd = (Day(Value) = CORE_DaysInMonth(Year(Value), Month(Value)))
End Function

Public Function CORE_ParseDecimal(ByVal Text As String, ByVal Places As Long, ByRef Value As Variant) As Boolean
    'True and Value set (subtype Decimal) when Text is a decimal of the file
    'format with at most Places decimals and an absolute value below 10^15.
    Dim I As Long, Code As Long, Negative As Boolean, Point As Long
    Dim IntDigits As Long, Significant As Long, Decimals As Long, Acc As Variant, Divisor As Variant
    I = 1
    If Left$(Text, 1) = "-" Then
        Negative = True
        I = 2
    End If
    Acc = CDec(0)
    For I = I To Len(Text)
        Code = AscW(Mid$(Text, I, 1))
        If Code = 46 Then    '"."
            If Point > 0 Then Exit Function
            Point = I
        ElseIf Code >= 48 And Code <= 57 Then
            'Stop before a digit that breaks a limit, so Acc never exceeds
            '23 significant digits and cannot overflow.
            If Point > 0 Then
                Decimals = Decimals + 1
                If Decimals > Places Then Exit Function
            Else
                IntDigits = IntDigits + 1
                If Significant > 0 Or Code > 48 Then Significant = Significant + 1
                If Significant > MAX_INTEGER_DIGITS Then Exit Function
            End If
            Acc = Acc * 10 + (Code - 48)
        Else
            Exit Function
        End If
    Next I
    If IntDigits = 0 Then Exit Function
    If Point > 0 And Decimals = 0 Then Exit Function
    Divisor = CDec(1)
    For I = 1 To Decimals
        Divisor = Divisor * 10
    Next I
    Acc = Acc / Divisor
    If Negative Then Acc = -Acc
    Value = Acc
    CORE_ParseDecimal = True
End Function

Public Function CORE_DecimalText(ByVal Value As Variant) As String
    'Canonical text of a decimal below 10^15 in absolute value with at most
    '8 decimals: "-" for negatives, no leading or trailing zeros, "." only
    'when there are decimals. Locale-independent.
    Dim Units As Variant, Fraction As Variant, Digit As Long, Text As String, I As Long
    Value = CDec(Value)
    If Value < 0 Then
        CORE_DecimalText = "-"
        Value = -Value
    End If
    Units = Fix(Value)
    Fraction = Value - Units
    Text = ""
    Do
        Digit = CLng(Units - Fix(Units / 10) * 10)
        Text = ChrW$(48 + Digit) & Text
        Units = Fix(Units / 10)
    Loop While Units > 0
    If Fraction > 0 Then
        Text = Text & "."
        For I = 1 To 8
            If Fraction = 0 Then Exit For
            Fraction = Fraction * 10
            Digit = CLng(Fix(Fraction))
            Text = Text & ChrW$(48 + Digit)
            Fraction = Fraction - Digit
        Next I
    End If
    CORE_DecimalText = CORE_DecimalText & Text
End Function

Public Function CORE_IsCode(ByVal CodeSet As String, ByVal Text As String) As Boolean
    'True when Text is a member of the named code list of the data contract:
    'segment, rate_type, amortisation, payment_months, penalty_type, event.
    Dim Members As String
    Select Case CodeSet
        Case "segment": Members = "|MTG_FIX|MTG_RST|MTG_FLT|CON_FIX|SME_FIX|"
        Case "rate_type": Members = "|FIXED|RESET|FLOAT|"
        Case "amortisation": Members = "|ANNUITY|LINEAR|BULLET|"
        Case "payment_months": Members = "|1|3|6|12|"
        Case "penalty_type": Members = "|NONE|PCT|MONTHS_INTEREST|"
        Case "event": Members = "|NONE|PARTIAL|FULL|MATURITY|DEFAULT|RENEG|SALE|"
        Case Else
            Err.Raise vbObjectError + 1101, "CORE_Parse", "Unknown code list: " & CodeSet
    End Select
    If Len(Text) = 0 Or InStr(1, Text, "|", vbBinaryCompare) > 0 Then Exit Function
    CORE_IsCode = (InStr(1, Members, "|" & Text & "|", vbBinaryCompare) > 0)
End Function

Private Function Digits(ByVal Text As String, ByRef Value As Long) As Boolean
    'True and Value set when Text is one or more ASCII digits.
    Dim I As Long, Code As Long
    If Len(Text) = 0 Then Exit Function
    Value = 0
    For I = 1 To Len(Text)
        Code = AscW(Mid$(Text, I, 1))
        If Code < 48 Or Code > 57 Then Exit Function
        Value = Value * 10 + (Code - 48)
    Next I
    Digits = True
End Function
