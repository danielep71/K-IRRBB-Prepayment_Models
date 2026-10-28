Attribute VB_Name = "CORE_Import"
'==============================================================================
' MODULE: CORE_Import
'------------------------------------------------------------------------------
' PURPOSE
'   Validates one import of docs/methodology/DATA_CONTRACT.md from the bytes
'   of its three files: errors E01 to E16 in the contract's first-error
'   order, warnings W01 to W06, the data window, RENEG successor
'   reconciliation (D11, D15), loan-month exposures and the risk-set outcome
'   of every loan-month, with the validation conventions of D16. E17,
'   reconciliation totals and control totals are not part of this module yet.
'
' USAGE
'   CORE_ReadImport reads one import and keeps the results of that import in
'   module state; CORE_ImportResult returns each kind of result as an array.
'   The caller reads the files; this module touches no file.
'
' ORDER OF FINDINGS
'   Errors by file (loans.csv, loan_panel.csv, market_rates.csv), then line;
'   warnings by file, line and code (D16). E12 and W01 are at line 0, with
'   their keys in the "missing" and "gaps" results.
'
' AMOUNTS
'   Every amount is an exact Decimal (D17); no comparison rounds.
'
' DEPENDENCIES
'   CORE_Csv, CORE_Parse. Arrays and scalars only; no workbook, UI, file or
'   COM access.
'==============================================================================

Option Explicit
Option Private Module

Private Const LOANS As String = "loans.csv"
Private Const PANEL As String = "loan_panel.csv"
Private Const RATES As String = "market_rates.csv"
Private Const LOANS_HEADER As String = "loan_id,segment,currency,origination_date,maturity_date,original_balance," & _
    "rate_type,fixed_until,reset_months,amortisation,payment_months,penalty_type,penalty_value,predecessor_id"
Private Const PANEL_HEADER As String = "as_of_date,loan_id,balance,client_rate,scheduled_principal," & _
    "prepaid_principal,other_change,event"
Private Const RATES_HEADER As String = "as_of_date,rate_id,currency,tenor_months,rate"
Private Const TERMINAL As String = "|FULL|MATURITY|DEFAULT|RENEG|SALE|"
Private Const SEP As String = vbTab

'Register fields (0-based).
Private Const L_ID As Long = 0, L_SEGMENT As Long = 1, L_CURRENCY As Long = 2, L_ORIGINATION As Long = 3
Private Const L_MATURITY As Long = 4, L_BALANCE As Long = 5, L_RATE_TYPE As Long = 6, L_FIXED As Long = 7
Private Const L_RESET As Long = 8, L_AMORTISATION As Long = 9, L_PAYMENT As Long = 10, L_PENALTY_TYPE As Long = 11
Private Const L_PENALTY_VALUE As Long = 12, L_PREDECESSOR As Long = 13
'Panel fields.
Private Const P_AS_OF As Long = 0, P_ID As Long = 1, P_EVENT As Long = 7
'Market-rate fields.
Private Const R_AS_OF As Long = 0, R_ID As Long = 1, R_CURRENCY As Long = 2, R_TENOR As Long = 3, R_RATE As Long = 4

'Register rows.
Private mLN As Long, mLLine() As Long, mLF() As Variant, mLOk() As Boolean
Private mLOrig() As Date, mLMat() As Date, mLHasFixed() As Boolean, mLFixed() As Date, mLBal() As Variant
'Panel rows.
Private mPN As Long, mPLine() As Long, mPF() As Variant, mPOk() As Boolean, mPInside() As Boolean
Private mPAsOf() As Date, mPBal() As Variant, mPRate() As Variant, mPSched() As Variant
Private mPPrepaid() As Variant, mPOther() As Variant
'Market-rate rows.
Private mRN As Long, mRLine() As Long, mRF() As Variant, mROk() As Boolean, mRInside() As Boolean, mRAsOf() As Date

'Results, each a list of tab-joined records.
Private mErrors As Collection, mWarnings As Collection, mGaps As Collection, mMissing As Collection
Private mLoanMonths As Collection, mOutcomes As Collection

Private mTolerance As Variant

'------------------------------------------------------------------------------
' Entry points
'------------------------------------------------------------------------------

Public Function CORE_ReadImport(ByRef LoansData() As Byte, ByVal LoansLength As Long, _
                                ByRef PanelData() As Byte, ByVal PanelLength As Long, _
                                ByRef RatesData() As Byte, ByVal RatesLength As Long, _
                                ByVal WindowStart As Date, ByVal WindowEnd As Date, _
                                ByVal Allowlist As Variant) As Long
    'Validate one import; returns the number of errors (0: accepted).
    'Allowlist is a 0-based array of ISO currency codes.
    Dim Register As Collection
    Set mErrors = New Collection
    Set mWarnings = New Collection
    Set mGaps = New Collection
    Set mMissing = New Collection
    Set mLoanMonths = New Collection
    Set mOutcomes = New Collection
    mTolerance = CDec(5) / CDec(1000)    'decision D9
    LoadRows LoansData, LoansLength, PanelData, PanelLength, RatesData, RatesLength
    CheckSingleRows Allowlist
    CheckDates
    MarkWindow WindowStart, WindowEnd
    CheckDuplicates
    Set Register = RegisterIndex()
    CheckReferences Register
    CheckHistories Register, WindowEnd
    CheckSuccessors Register, WindowStart, WindowEnd
    CheckExtracts WindowStart, WindowEnd
    CORE_ReadImport = mErrors.Count
End Function

Public Function CORE_ImportResult(ByVal Kind As String) As Variant
    'A 1-based (n x k) array of the last import's results, or Empty when
    'there are none:
    '  errors, warnings   file, line, code
    '  gaps               loan_id, missing month end (ISO), sorted
    '  missing            month end (ISO) of each E12
    '  loan_months        loan_id, as_of_date (ISO), available, prepaid
    '  outcomes           loan_id, start month end t-1 (ISO), outcome
    Dim Items As Collection
    Select Case Kind
        Case "errors": CORE_ImportResult = Table(Sorted(mErrors, True), 3)
        Case "warnings": CORE_ImportResult = Table(Sorted(mWarnings, False), 3)
        Case "gaps": CORE_ImportResult = Table(Sorted(mGaps, False), 2)
        Case "missing"
            Set Items = mMissing
            CORE_ImportResult = Table(Items, 1)
        Case "loan_months"
            Set Items = mLoanMonths
            CORE_ImportResult = Table(Items, 4)
        Case "outcomes"
            Set Items = mOutcomes
            CORE_ImportResult = Table(Items, 3)
        Case Else
            Err.Raise vbObjectError + 1201, "CORE_Import", "Unknown result: " & Kind
    End Select
End Function

'------------------------------------------------------------------------------
' E01: file format
'------------------------------------------------------------------------------

Private Sub LoadRows(ByRef LoansData() As Byte, ByVal LoansLength As Long, ByRef PanelData() As Byte, _
                     ByVal PanelLength As Long, ByRef RatesData() As Byte, ByVal RatesLength As Long)
    Dim I As Long
    mLN = SplitFile(LoansData, LoansLength, LOANS, LOANS_HEADER, mLLine, mLF)
    mPN = SplitFile(PanelData, PanelLength, PANEL, PANEL_HEADER, mPLine, mPF)
    mRN = SplitFile(RatesData, RatesLength, RATES, RATES_HEADER, mRLine, mRF)
    ReDim mLOk(0 To mLN): ReDim mLOrig(0 To mLN): ReDim mLMat(0 To mLN): ReDim mLHasFixed(0 To mLN)
    ReDim mLFixed(0 To mLN): ReDim mLBal(0 To mLN)
    ReDim mPOk(0 To mPN): ReDim mPInside(0 To mPN): ReDim mPAsOf(0 To mPN): ReDim mPBal(0 To mPN)
    ReDim mPRate(0 To mPN): ReDim mPSched(0 To mPN): ReDim mPPrepaid(0 To mPN): ReDim mPOther(0 To mPN)
    ReDim mROk(0 To mRN): ReDim mRInside(0 To mRN): ReDim mRAsOf(0 To mRN)
    For I = 1 To mLN: mLOk(I) = True: Next I
    For I = 1 To mPN: mPOk(I) = True: Next I
    For I = 1 To mRN: mROk(I) = True: Next I
End Sub

Private Function SplitFile(ByRef Data() As Byte, ByVal Length As Long, ByVal FileName As String, _
                           ByVal Header As String, ByRef LineNo() As Long, ByRef Fields() As Variant) As Long
    'Rows of one file that pass E01, numbered by line; E01 at line 1 for a
    'header that differs (no rows are read), else at each bad row.
    Dim Lines() As String, Ascii() As Boolean, N As Long, I As Long, F As Variant, Count As Long, Width As Long
    N = CORE_SplitLines(Data, Length, Lines, Ascii)
    ReDim LineNo(0 To 0)
    ReDim Fields(0 To 0)
    If N = 0 Then
        AddError FileName, 1, "E01"
        Exit Function
    End If
    If Not Ascii(1) Or Lines(1) <> Header Then
        AddError FileName, 1, "E01"
        Exit Function
    End If
    Width = UBound(Split(Header, ",")) + 1
    ReDim LineNo(0 To N)
    ReDim Fields(0 To N)
    For I = 2 To N
        F = CORE_SplitFields(Lines(I))
        If Not Ascii(I) Or UBound(F) + 1 <> Width Then
            AddError FileName, I, "E01"
        Else
            Count = Count + 1
            LineNo(Count) = I
            Fields(Count) = F
        End If
    Next I
    SplitFile = Count
End Function

'------------------------------------------------------------------------------
' Single-row rules E03, E02, E04, E06, E07, E09
'------------------------------------------------------------------------------

Private Sub CheckSingleRows(ByVal Allowlist As Variant)
    Dim I As Long, Code As String
    For I = 1 To mLN
        Code = LoanRowError(I, Allowlist)
        If Len(Code) > 0 Then FailLoan I, Code
    Next I
    For I = 1 To mPN
        Code = PanelRowError(I)
        If Len(Code) > 0 Then FailPanel I, Code
    Next I
    For I = 1 To mRN
        Code = RateRowError(I, Allowlist)
        If Len(Code) > 0 Then FailRate I, Code
    Next I
End Sub

Private Function LoanRowError(ByVal I As Long, ByVal Allowlist As Variant) As String
    Dim F As Variant, RateType As String, Penalty As String, D As Date, V As Variant, K As Variant
    F = mLF(I)
    For Each K In Array(L_ID, L_SEGMENT, L_CURRENCY, L_ORIGINATION, L_MATURITY, L_BALANCE, L_RATE_TYPE, _
                        L_AMORTISATION, L_PAYMENT, L_PENALTY_TYPE)
        If Len(F(K)) = 0 Then LoanRowError = "E03": Exit Function
    Next K
    RateType = F(L_RATE_TYPE)
    Penalty = F(L_PENALTY_TYPE)
    If RateType = "RESET" And Len(F(L_FIXED)) = 0 Then LoanRowError = "E03": Exit Function
    If (RateType = "FIXED" Or RateType = "FLOAT") And Len(F(L_FIXED)) > 0 Then LoanRowError = "E03": Exit Function
    If (RateType = "RESET" Or RateType = "FLOAT") And Len(F(L_RESET)) = 0 Then LoanRowError = "E03": Exit Function
    If RateType = "FIXED" And Len(F(L_RESET)) > 0 Then LoanRowError = "E03": Exit Function
    If Penalty = "NONE" And Len(F(L_PENALTY_VALUE)) > 0 Then LoanRowError = "E03": Exit Function
    If (Penalty = "PCT" Or Penalty = "MONTHS_INTEREST") And Len(F(L_PENALTY_VALUE)) = 0 Then
        LoanRowError = "E03": Exit Function
    End If
    If Not CORE_ParseDate(F(L_ORIGINATION), D) Then LoanRowError = "E02": Exit Function
    mLOrig(I) = D
    If Not CORE_ParseDate(F(L_MATURITY), D) Then LoanRowError = "E02": Exit Function
    mLMat(I) = D
    If Len(F(L_FIXED)) > 0 Then
        If Not CORE_ParseDate(F(L_FIXED), D) Then LoanRowError = "E02": Exit Function
        mLHasFixed(I) = True
        mLFixed(I) = D
    End If
    If Not IsId(F(L_ID)) Or Not IsCurrency(F(L_CURRENCY)) Then LoanRowError = "E04": Exit Function
    If Not CORE_ParseDecimal(F(L_BALANCE), 4, V) Then LoanRowError = "E04": Exit Function
    If V <= 0 Then LoanRowError = "E04": Exit Function
    mLBal(I) = V
    If Len(F(L_PREDECESSOR)) > 0 And Not IsId(F(L_PREDECESSOR)) Then LoanRowError = "E04": Exit Function
    If Len(F(L_RESET)) > 0 And Not IsPositiveInteger(F(L_RESET)) Then LoanRowError = "E04": Exit Function
    If Len(F(L_PENALTY_VALUE)) > 0 Then
        If Not CORE_ParseDecimal(F(L_PENALTY_VALUE), 8, V) Then LoanRowError = "E04": Exit Function
        If V < 0 Then LoanRowError = "E04": Exit Function
    End If
    If Not CORE_IsCode("segment", F(L_SEGMENT)) Or Not CORE_IsCode("rate_type", RateType) _
       Or Not CORE_IsCode("amortisation", F(L_AMORTISATION)) Or Not CORE_IsCode("payment_months", F(L_PAYMENT)) _
       Or Not CORE_IsCode("penalty_type", Penalty) Then
        LoanRowError = "E06": Exit Function
    End If
    If Not InList(F(L_CURRENCY), Allowlist) Then LoanRowError = "E07"
End Function

Private Function PanelRowError(ByVal I As Long) As String
    Dim F As Variant, K As Long, D As Date, V As Variant
    F = mPF(I)
    For K = 0 To 7
        If Len(F(K)) = 0 Then PanelRowError = "E03": Exit Function
    Next K
    If Not CORE_ParseDate(F(P_AS_OF), D) Then PanelRowError = "E02": Exit Function
    If Not CORE_IsMonthEnd(D) Then PanelRowError = "E02": Exit Function
    mPAsOf(I) = D
    If Not IsId(F(P_ID)) Then PanelRowError = "E04": Exit Function
    If Not CORE_ParseDecimal(F(2), 4, V) Then PanelRowError = "E04": Exit Function
    mPBal(I) = V
    If Not CORE_ParseDecimal(F(3), 8, V) Then PanelRowError = "E04": Exit Function
    mPRate(I) = V
    If Not CORE_ParseDecimal(F(4), 4, V) Then PanelRowError = "E04": Exit Function
    mPSched(I) = V
    If Not CORE_ParseDecimal(F(5), 4, V) Then PanelRowError = "E04": Exit Function
    mPPrepaid(I) = V
    If Not CORE_ParseDecimal(F(6), 4, V) Then PanelRowError = "E04": Exit Function
    mPOther(I) = V
    If mPRate(I) < CDec(-5) / CDec(100) Or mPRate(I) > CDec(50) / CDec(100) Then PanelRowError = "E04": Exit Function
    If Not CORE_IsCode("event", F(P_EVENT)) Then PanelRowError = "E06": Exit Function
    If mPBal(I) < 0 Or mPSched(I) < 0 Or mPPrepaid(I) < 0 Then PanelRowError = "E09"
End Function

Private Function RateRowError(ByVal I As Long, ByVal Allowlist As Variant) As String
    Dim F As Variant, K As Long, D As Date, V As Variant
    F = mRF(I)
    For K = 0 To 4
        If Len(F(K)) = 0 Then RateRowError = "E03": Exit Function
    Next K
    If Not CORE_ParseDate(F(R_AS_OF), D) Then RateRowError = "E02": Exit Function
    If Not CORE_IsMonthEnd(D) Then RateRowError = "E02": Exit Function
    mRAsOf(I) = D
    If Not IsId(F(R_ID)) Or Not IsCurrency(F(R_CURRENCY)) Or Not IsPositiveInteger(F(R_TENOR)) Then
        RateRowError = "E04": Exit Function
    End If
    If Not CORE_ParseDecimal(F(R_RATE), 8, V) Then RateRowError = "E04": Exit Function
    If V < CDec(-5) / CDec(100) Or V > CDec(25) / CDec(100) Then RateRowError = "E04": Exit Function
    If Not InList(F(R_CURRENCY), Allowlist) Then RateRowError = "E07"
End Function

'------------------------------------------------------------------------------
' E11, data window (W04), E05, E08
'------------------------------------------------------------------------------

Private Sub CheckDates()
    'E11 for register rows, then for panel rows dated before their loan's
    'origination month end. The panel check uses the register as it stood
    'after the single-row rules (the last row of a duplicated loan_id), and
    'skips a loan whose register row has itself failed.
    Dim I As Long, Loans As Collection, J As Long
    Set Loans = RegisterIndex()
    For I = 1 To mLN
        If mLOk(I) Then
            If mLMat(I) <= mLOrig(I) Then
                FailLoan I, "E11"
            ElseIf mLHasFixed(I) Then
                If Not (mLOrig(I) < mLFixed(I) And mLFixed(I) < mLMat(I)) Then FailLoan I, "E11"
            End If
        End If
    Next I
    For I = 1 To mPN
        If mPOk(I) Then
            J = Lookup(Loans, mPF(I)(P_ID))
            If J > 0 Then
                If mLOk(J) Then
                    If mPAsOf(I) < MonthEnd(mLOrig(J)) Then FailPanel I, "E11"
                End If
            End If
        End If
    Next I
End Sub

Private Sub MarkWindow(ByVal WindowStart As Date, ByVal WindowEnd As Date)
    Dim I As Long
    For I = 1 To mPN
        If mPOk(I) Then
            If mPAsOf(I) >= WindowStart And mPAsOf(I) <= WindowEnd Then
                mPInside(I) = True
            Else
                AddWarning PANEL, mPLine(I), "W04"
            End If
        End If
    Next I
    For I = 1 To mRN
        If mROk(I) Then
            If mRAsOf(I) >= WindowStart And mRAsOf(I) <= WindowEnd Then
                mRInside(I) = True
            Else
                AddWarning RATES, mRLine(I), "W04"
            End If
        End If
    Next I
End Sub

Private Sub CheckDuplicates()
    'E05 among rows that passed the earlier rules, in line order (D16).
    Dim Seen As Collection, I As Long, K As String
    Set Seen = New Collection
    For I = 1 To mLN
        If mLOk(I) Then
            K = KeyOf(mLF(I)(L_ID))
            If Lookup(Seen, K, True) > 0 Then
                FailLoan I, "E05"
            Else
                Seen.Add I, K
            End If
        End If
    Next I
    Set Seen = New Collection
    For I = 1 To mPN
        If mPInside(I) And mPOk(I) Then
            K = KeyOf(mPF(I)(P_AS_OF) & SEP & mPF(I)(P_ID))
            If Lookup(Seen, K, True) > 0 Then
                FailPanel I, "E05"
            Else
                Seen.Add I, K
            End If
        End If
    Next I
    Set Seen = New Collection
    For I = 1 To mRN
        If mRInside(I) And mROk(I) Then
            K = KeyOf(mRF(I)(R_AS_OF) & SEP & mRF(I)(R_ID))
            If Lookup(Seen, K, True) > 0 Then
                FailRate I, "E05"
            Else
                Seen.Add I, K
            End If
        End If
    Next I
End Sub

Private Sub CheckReferences(ByVal Register As Collection)
    Dim I As Long, Pred As String, Series As Collection, K As String, J As Long
    For I = 1 To mLN
        If mLOk(I) Then
            Pred = mLF(I)(L_PREDECESSOR)
            If Len(Pred) > 0 Then
                If Lookup(Register, Pred) = 0 Then FailLoan I, "E08"
            End If
        End If
    Next I
    For I = 1 To mPN
        If mPInside(I) And mPOk(I) Then
            If Lookup(Register, mPF(I)(P_ID)) = 0 Then FailPanel I, "E08"
        End If
    Next I
    Set Series = New Collection    'rate_id -> first row of the series
    For I = 1 To mRN
        If mRInside(I) And mROk(I) Then
            K = KeyOf(mRF(I)(R_ID))
            J = Lookup(Series, K, True)
            If J = 0 Then
                Series.Add I, K
            ElseIf mRF(J)(R_CURRENCY) <> mRF(I)(R_CURRENCY) Or mRF(J)(R_TENOR) <> mRF(I)(R_TENOR) Then
                FailRate I, "E08"
            End If
        End If
    Next I
End Sub

'------------------------------------------------------------------------------
' Loan histories: E14, E10, E13, E15, W01, W02, W03, W05; exposures, outcomes
'------------------------------------------------------------------------------

Private Sub CheckHistories(ByVal Register As Collection, ByVal WindowEnd As Date)
    'Panel rows still valid, grouped by loan in date order.
    Dim Keys() As String, Order As Variant, N As Long, I As Long, First As Long, Rows() As Long, K As Long
    Dim Last As Boolean, Loan As Long
    ReDim Keys(1 To MaxOf(mPN, 1))
    For I = 1 To mPN
        If mPInside(I) And mPOk(I) Then
            N = N + 1
            Keys(N) = KeyOf(mPF(I)(P_ID)) & "|" & Format$(CLng(mPAsOf(I)), "0000000") & "|" & Format$(I, "0000000000")
        End If
    Next I
    If N = 0 Then Exit Sub
    Order = SortedOrder(Keys, N)
    First = 1
    For I = 1 To N
        If I = N Then
            Last = True
        Else
            Last = (LoanOfKey(Keys(Order(I + 1))) <> LoanOfKey(Keys(Order(I))))
        End If
        If Last Then
            ReDim Rows(1 To I - First + 1)
            For K = First To I
                Rows(K - First + 1) = RowOfKey(Keys(Order(K)))
            Next K
            Loan = Lookup(Register, mPF(Rows(1))(P_ID))
            CheckHistory Loan, Rows, WindowEnd
            RecordOutcomes Loan, Rows, WindowEnd
            First = I + 1
        End If
    Next I
End Sub

Private Sub CheckHistory(ByVal Loan As Long, ByRef Rows() As Long, ByVal WindowEnd As Date)
    Dim MaturityEnd As Date, TerminalSeen As Boolean, Prev As Long, R As Long, I As Long
    Dim Opening As Variant, HasOpening As Boolean, Available As Variant, Month As Date, Ev As String
    MaturityEnd = MonthEnd(mLMat(Loan))
    For I = LBound(Rows) To UBound(Rows)
        R = Rows(I)
        HasOpening = False
        If Prev > 0 Then
            If mPAsOf(Prev) = PreviousMonthEnd(mPAsOf(R)) Then
                Opening = mPBal(Prev)
                HasOpening = True
            End If
        ElseIf mPAsOf(R) = MonthEnd(mLOrig(Loan)) Then
            Opening = mLBal(Loan)
            HasOpening = True
        End If
        Ev = mPF(R)(P_EVENT)
        If Not EventConsistent(Ev, R, HasOpening, Opening, MaturityEnd) Then
            FailPanel R, "E14"
        ElseIf TerminalSeen Then
            FailPanel R, "E10"
        ElseIf HasOpening Then
            If Abs(mPBal(R) - (Opening - mPSched(R) - mPPrepaid(R) + mPOther(R))) > mTolerance Then
                FailPanel R, "E13"
            ElseIf mPPrepaid(R) > Opening - mPSched(R) + Positive(mPOther(R)) Then
                FailPanel R, "E15"    'also on a first row in the origination month (D16)
            End If
        End If
        If Prev > 0 And HasOpening Then
            If Opening > 0 And mPAsOf(Prev) < MaturityEnd Then
                Available = Opening - mPSched(R) + Positive(mPOther(R))
                If Available > 0 And (Ev = "NONE" Or Ev = "PARTIAL" Or Ev = "FULL") Then
                    mLoanMonths.Add Join(Array(mPF(R)(P_ID), mPF(R)(P_AS_OF), CORE_DecimalText(Available), _
                                               CORE_DecimalText(mPPrepaid(R))), SEP)
                End If
            End If
        End If
        If mPOther(R) <> 0 Then AddWarning PANEL, mPLine(R), "W03"
        If mPBal(R) > 0 And mPAsOf(R) > MaturityEnd Then AddWarning PANEL, mPLine(R), "W05"
        If Prev > 0 And mPOk(R) Then
            Month = PreviousMonthEnd(mPAsOf(R))
            Do While Month > mPAsOf(Prev)
                AddWarning PANEL, 0, "W01"    'at the missing month: line 0 (D16)
                mGaps.Add mPF(R)(P_ID) & SEP & IsoDate(Month)
                Month = PreviousMonthEnd(Month)
            Loop
        End If
        If InStr(1, TERMINAL, "|" & Ev & "|", vbBinaryCompare) > 0 Then TerminalSeen = True
        Prev = R
    Next I
    If Prev > 0 And Not TerminalSeen And mPAsOf(Prev) < WindowEnd Then AddWarning PANEL, mPLine(Prev), "W02"
End Sub

Private Function EventConsistent(ByVal Ev As String, ByVal R As Long, ByVal HasOpening As Boolean, _
                                 ByVal Opening As Variant, ByVal MaturityEnd As Date) As Boolean
    Select Case Ev
        Case "NONE": EventConsistent = (mPPrepaid(R) = 0 And mPBal(R) > 0)
        Case "PARTIAL": EventConsistent = (mPPrepaid(R) > 0 And mPBal(R) > 0)
        Case "FULL": EventConsistent = (mPPrepaid(R) > 0 And mPBal(R) = 0 And mPAsOf(R) < MaturityEnd)
        Case "MATURITY": EventConsistent = (mPBal(R) = 0 And mPAsOf(R) = MaturityEnd)
        Case "DEFAULT", "SALE": EventConsistent = (mPPrepaid(R) = 0)
        Case Else    'RENEG
            If mPPrepaid(R) <> 0 Or mPBal(R) <> 0 Or Not HasOpening Then Exit Function
            EventConsistent = (mPSched(R) <= Opening And mPOther(R) = -(Opening - mPSched(R)))
    End Select
End Function

Private Sub RecordOutcomes(ByVal Loan As Long, ByRef Rows() As Long, ByVal WindowEnd As Date)
    'One outcome per loan-month starting at a non-terminal row still valid.
    Dim Valid() As Long, N As Long, I As Long, R As Long, MaturityEnd As Date, Outcome As String
    ReDim Valid(1 To UBound(Rows) - LBound(Rows) + 1)
    For I = LBound(Rows) To UBound(Rows)
        If mPOk(Rows(I)) Then
            N = N + 1
            Valid(N) = Rows(I)
        End If
    Next I
    MaturityEnd = MonthEnd(mLMat(Loan))
    For I = 1 To N
        R = Valid(I)
        If InStr(1, TERMINAL, "|" & mPF(R)(P_EVENT) & "|", vbBinaryCompare) = 0 Then
            If mPAsOf(R) >= MaturityEnd Then
                Outcome = "PAST_MATURITY"
            ElseIf mPAsOf(R) = WindowEnd Then
                Outcome = "END_OF_WINDOW"
            ElseIf I = N Then
                Outcome = "CENSORED"
            ElseIf mPAsOf(Valid(I + 1)) = NextMonthEnd(mPAsOf(R)) Then
                Outcome = mPF(Valid(I + 1))(P_EVENT)
            Else
                Outcome = "GAP"
            End If
            mOutcomes.Add mPF(R)(P_ID) & SEP & mPF(R)(P_AS_OF) & SEP & Outcome
        End If
    Next I
End Sub

'------------------------------------------------------------------------------
' E16 RENEG successors (D11, D15) and E12 missing extracts
'------------------------------------------------------------------------------

Private Sub CheckSuccessors(ByVal Register As Collection, ByVal WindowStart As Date, ByVal WindowEnd As Date)
    Dim I As Long, J As Long, Pred As String, Successors As Collection, Reneg As Collection
    Dim Found As Variant, Transferred As Variant, S As Long, Ending As Long, Start As Date, Item As Variant
    Set Successors = New Collection    'predecessor key -> tab-joined successor rows
    For I = 1 To mLN
        If IsRegistered(Register, I) Then
            Pred = mLF(I)(L_PREDECESSOR)
            If Pred = mLF(I)(L_ID) Then
                FailLoan I, "E16"    'D6: a modification continues under a new loan_id
            ElseIf Len(Pred) > 0 Then
                AppendRow Successors, KeyOf(Pred), I
            End If
        End If
    Next I
    Set Reneg = New Collection    'loan key -> its RENEG row (the last one)
    For I = 1 To mPN
        If mPInside(I) And mPOk(I) Then
            If mPF(I)(P_EVENT) = "RENEG" Then
                If Lookup(Reneg, KeyOf(mPF(I)(P_ID)), True) > 0 Then Reneg.Remove KeyOf(mPF(I)(P_ID))
                Reneg.Add I, KeyOf(mPF(I)(P_ID))
            End If
        End If
    Next I
    For Each Item In Reneg
        I = Item
        Found = RowsOf(Successors, KeyOf(mPF(I)(P_ID)))
        Transferred = -mPOther(I)
        If Transferred <= mTolerance Then    'D15: no successor needed, and none may name it
            For J = 1 To UBound(Found)
                FailLoan CLng(Found(J)), "E16"
            Next J
        ElseIf UBound(Found) <> 1 Then
            FailPanel I, "E16"
        Else
            S = Found(1)
            J = Lookup(Register, mPF(I)(P_ID))
            If MonthEnd(mLOrig(S)) <> mPAsOf(I) Or mLF(S)(L_CURRENCY) <> mLF(J)(L_CURRENCY) _
               Or Abs(mLBal(S) - Transferred) > mTolerance Then
                FailPanel I, "E16"
            ElseIf mLF(S)(L_SEGMENT) <> mLF(J)(L_SEGMENT) Then
                AddWarning LOANS, mLLine(S), "W06"
            End If
        End If
    Next Item
    For I = 1 To mLN
        If IsRegistered(Register, I) Then
            Pred = mLF(I)(L_PREDECESSOR)
            If Len(Pred) > 0 And Pred <> mLF(I)(L_ID) Then
                Start = MonthEnd(mLOrig(I))
                If Start >= WindowStart And Start <= WindowEnd And mLOk(I) Then
                    Ending = Lookup(Reneg, KeyOf(Pred), True)
                    If Ending = 0 Then
                        FailLoan I, "E16"
                    ElseIf mPAsOf(Ending) <> Start Then
                        FailLoan I, "E16"
                    End If
                End If
            End If
        End If
    Next I
End Sub

Private Sub CheckExtracts(ByVal WindowStart As Date, ByVal WindowEnd As Date)
    'E12 at line 0 for each month end of the window without a panel row that
    'entered the window (D14).
    Dim Present As Collection, I As Long, Month As Date
    Set Present = New Collection
    For I = 1 To mPN
        If mPInside(I) Then
            If Lookup(Present, "d" & CLng(mPAsOf(I)), True) = 0 Then Present.Add I, "d" & CLng(mPAsOf(I))
        End If
    Next I
    Month = MonthEnd(WindowStart)
    Do While Month <= WindowEnd
        If Lookup(Present, "d" & CLng(Month), True) = 0 Then
            AddError PANEL, 0, "E12"
            mMissing.Add IsoDate(Month)
        End If
        If Month >= WindowEnd Then Exit Do    'never build the month after 9999-12
        Month = NextMonthEnd(Month)
    Loop
End Sub

'------------------------------------------------------------------------------
' Findings
'------------------------------------------------------------------------------

Private Sub FailLoan(ByVal I As Long, ByVal Code As String)
    If mLOk(I) Then
        mLOk(I) = False
        AddError LOANS, mLLine(I), Code
    End If
End Sub

Private Sub FailPanel(ByVal I As Long, ByVal Code As String)
    If mPOk(I) Then
        mPOk(I) = False
        AddError PANEL, mPLine(I), Code
    End If
End Sub

Private Sub FailRate(ByVal I As Long, ByVal Code As String)
    If mROk(I) Then
        mROk(I) = False
        AddError RATES, mRLine(I), Code
    End If
End Sub

Private Sub AddError(ByVal FileName As String, ByVal Line As Long, ByVal Code As String)
    mErrors.Add FileName & SEP & CStr(Line) & SEP & Code
End Sub

Private Sub AddWarning(ByVal FileName As String, ByVal Line As Long, ByVal Code As String)
    mWarnings.Add FileName & SEP & CStr(Line) & SEP & Code
End Sub

Private Function Sorted(ByVal Items As Collection, ByVal FileAndLineOnly As Boolean) As Collection
    'Findings by file order, then line, then (for warnings) code; stable.
    'Other lists by their text.
    Dim Keys() As String, Order As Variant, I As Long, Parts As Variant, Result As Collection
    Set Result = New Collection
    Set Sorted = Result
    If Items.Count = 0 Then Exit Function
    ReDim Keys(1 To Items.Count)
    For I = 1 To Items.Count
        Parts = Split(Items.Item(I), SEP)
        If Items Is mErrors Or Items Is mWarnings Then
            Keys(I) = CStr(FileRank(CStr(Parts(0)))) & Format$(CLng(Parts(1)), "0000000000")
            If Not FileAndLineOnly Then Keys(I) = Keys(I) & Parts(2)
        Else
            Keys(I) = Items.Item(I)
        End If
    Next I
    Order = SortedOrder(Keys, Items.Count)
    For I = 1 To Items.Count
        Result.Add Items.Item(Order(I))
    Next I
End Function

Private Function FileRank(ByVal FileName As String) As Long
    Select Case FileName
        Case LOANS: FileRank = 1
        Case PANEL: FileRank = 2
        Case Else: FileRank = 3
    End Select
End Function

Private Function Table(ByVal Items As Collection, ByVal Width As Long) As Variant
    'A 1-based (n x Width) array of the tab-separated items; Empty if none.
    Dim Out() As Variant, I As Long, J As Long, Parts As Variant
    Table = Empty    'explicit: LibreOffice Basic, used for smoke runs, may otherwise return Nothing
    If Items.Count = 0 Then Exit Function
    ReDim Out(1 To Items.Count, 1 To Width)
    For I = 1 To Items.Count
        Parts = Split(Items.Item(I), SEP)
        For J = 1 To Width
            Out(I, J) = Parts(J - 1)
        Next J
    Next I
    Table = Out
End Function

'------------------------------------------------------------------------------
' Register lookups
'------------------------------------------------------------------------------

Private Function RegisterIndex() As Collection
    'loan_id -> register row, among the rows still valid; the last row of a
    'duplicated loan_id wins (after E05 only the first one is still valid).
    Dim I As Long, K As String, Index As Collection
    Set Index = New Collection
    For I = 1 To mLN
        If mLOk(I) Then
            K = KeyOf(mLF(I)(L_ID))
            If Lookup(Index, K, True) > 0 Then Index.Remove K
            Index.Add I, K
        End If
    Next I
    Set RegisterIndex = Index
End Function

Private Function IsRegistered(ByVal Register As Collection, ByVal I As Long) As Boolean
    'True when register row I is the one the register holds for its loan_id.
    IsRegistered = (Lookup(Register, mLF(I)(L_ID)) = I)
End Function

Private Function Lookup(ByVal Index As Collection, ByVal Key As String, Optional ByVal IsKey As Boolean = False) As Long
    'The row stored under Key (a loan_id, or a prepared key when IsKey), or 0.
    If Not IsKey Then Key = KeyOf(Key)
    On Error Resume Next
    Lookup = Index.Item(Key)
    On Error GoTo 0
End Function

Private Sub AppendRow(ByVal Index As Collection, ByVal Key As String, ByVal Row As Long)
    Dim Text As String
    On Error Resume Next
    Text = Index.Item(Key)
    On Error GoTo 0
    If Len(Text) > 0 Then
        Index.Remove Key
        Text = Text & SEP
    End If
    Index.Add Text & CStr(Row), Key
End Sub

Private Function RowsOf(ByVal Index As Collection, ByVal Key As String) As Variant
    'A 1-based array of the rows appended under Key (UBound 0 when none).
    Dim Text As String, Parts As Variant, Out() As Variant, I As Long
    On Error Resume Next
    Text = Index.Item(Key)
    On Error GoTo 0
    If Len(Text) = 0 Then
        ReDim Out(0 To 0)
    Else
        Parts = Split(Text, SEP)
        ReDim Out(0 To UBound(Parts) + 1)
        For I = 0 To UBound(Parts)
            Out(I + 1) = CLng(Parts(I))
        Next I
    End If
    RowsOf = Out
End Function

Private Function KeyOf(ByVal Text As String) As String
    'A Collection key for case-sensitive text: "k" and four hex digits per
    'character, since Collection keys ignore case.
    Dim I As Long
    KeyOf = "k"
    For I = 1 To Len(Text)
        KeyOf = KeyOf & Right$("000" & Hex$(AscW(Mid$(Text, I, 1))), 4)
    Next I
End Function

Private Function LoanOfKey(ByVal SortKey As String) As String
    LoanOfKey = Left$(SortKey, InStr(1, SortKey, "|") - 1)
End Function

Private Function RowOfKey(ByVal SortKey As String) As Long
    RowOfKey = CLng(Mid$(SortKey, InStrRev(SortKey, "|") + 1))
End Function

'------------------------------------------------------------------------------
' Sorting, dates and field checks
'------------------------------------------------------------------------------

Private Function SortedOrder(ByRef Keys() As String, ByVal N As Long) As Variant
    'Stable merge sort: the order (1-based) of Keys(1 To N) by binary text.
    Dim Order() As Long, Buffer() As Long, Width As Long, Lo As Long, Middle As Long, Hi As Long
    Dim I As Long, J As Long, K As Long
    ReDim Order(1 To N)
    ReDim Buffer(1 To N)
    For I = 1 To N
        Order(I) = I
    Next I
    Width = 1
    Do While Width < N
        Lo = 1
        Do While Lo <= N
            Middle = MinOf(Lo + Width - 1, N)
            Hi = MinOf(Lo + 2 * Width - 1, N)
            I = Lo: J = Middle + 1: K = Lo
            Do While I <= Middle Or J <= Hi
                If J > Hi Then
                    Buffer(K) = Order(I): I = I + 1
                ElseIf I > Middle Then
                    Buffer(K) = Order(J): J = J + 1
                ElseIf StrComp(Keys(Order(J)), Keys(Order(I)), vbBinaryCompare) < 0 Then
                    Buffer(K) = Order(J): J = J + 1
                Else
                    Buffer(K) = Order(I): I = I + 1
                End If
                K = K + 1
            Loop
            Lo = Lo + 2 * Width
        Loop
        For I = 1 To N
            Order(I) = Buffer(I)
        Next I
        Width = Width * 2
    Loop
    SortedOrder = Order
End Function

Private Function MinOf(ByVal A As Long, ByVal B As Long) As Long
    If A < B Then MinOf = A Else MinOf = B
End Function

Private Function MaxOf(ByVal A As Long, ByVal B As Long) As Long
    If A > B Then MaxOf = A Else MaxOf = B
End Function

Private Function MonthEnd(ByVal D As Date) As Date
    MonthEnd = DateSerial(Year(D), Month(D), CORE_DaysInMonth(Year(D), Month(D)))
End Function

Private Function PreviousMonthEnd(ByVal D As Date) As Date
    PreviousMonthEnd = DateSerial(Year(D), Month(D), 1) - 1
End Function

Private Function NextMonthEnd(ByVal D As Date) As Date
    Dim Y As Long, M As Long
    Y = Year(D) + IIf(Month(D) = 12, 1, 0)
    M = Month(D) Mod 12 + 1
    NextMonthEnd = DateSerial(Y, M, CORE_DaysInMonth(Y, M))
End Function

Private Function IsoDate(ByVal D As Date) As String
    IsoDate = Format$(Year(D), "0000") & "-" & Format$(Month(D), "00") & "-" & Format$(Day(D), "00")
End Function

Private Function Positive(ByVal V As Variant) As Variant
    If V > 0 Then Positive = V Else Positive = CDec(0)
End Function

Private Function InList(ByVal Text As String, ByVal Items As Variant) As Boolean
    Dim Item As Variant
    For Each Item In Items
        If StrComp(CStr(Item), Text, vbBinaryCompare) = 0 Then InList = True: Exit Function
    Next Item
End Function

Private Function IsId(ByVal Text As String) As Boolean
    '[A-Za-z0-9_-]{1,32}
    Dim I As Long, C As Long
    If Len(Text) < 1 Or Len(Text) > 32 Then Exit Function
    For I = 1 To Len(Text)
        C = AscW(Mid$(Text, I, 1))
        If Not ((C >= 48 And C <= 57) Or (C >= 65 And C <= 90) Or (C >= 97 And C <= 122) Or C = 95 Or C = 45) Then
            Exit Function
        End If
    Next I
    IsId = True
End Function

Private Function IsCurrency(ByVal Text As String) As Boolean
    '[A-Z]{3}
    Dim I As Long, C As Long
    If Len(Text) <> 3 Then Exit Function
    For I = 1 To 3
        C = AscW(Mid$(Text, I, 1))
        If C < 65 Or C > 90 Then Exit Function
    Next I
    IsCurrency = True
End Function

Private Function IsPositiveInteger(ByVal Text As String) As Boolean
    '[1-9][0-9]*
    Dim I As Long, C As Long
    If Len(Text) = 0 Then Exit Function
    For I = 1 To Len(Text)
        C = AscW(Mid$(Text, I, 1))
        If C < 48 Or C > 57 Or (I = 1 And C = 48) Then Exit Function
    Next I
    IsPositiveInteger = True
End Function
