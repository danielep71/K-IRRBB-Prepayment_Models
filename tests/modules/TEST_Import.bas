Attribute VB_Name = "TEST_Import"
'==============================================================================
' MODULE: TEST_Import
'------------------------------------------------------------------------------
' PURPOSE
'   VBA tests of CORE_Import against the committed fixtures and expected
'   files of the data-contract cases, carried by the generated TEST_Fixtures
'   module. Every variant of a case is read with the case's settings and
'   compared with its expected file the way tools/test_reference_cases.py
'   compares the reference reader:
'     accepted, errors        always, as exact lists
'     warnings, gaps,         when the expected file has them, as exact lists
'     missing_extracts
'     warning_counts          the count of each warning code
'     outcomes                the whole outcome table
'     loan_months             each listed loan-month: available, prepaid and,
'                             when given, SMM = prepaid / available, exactly
'     totals                  every key, each measure exactly (unlisted = 0)
'     control_differences     as an exact list
'     counts                  rows read, accepted and outside the window,
'                             and loans, per file
'     comparison_count,       the number of control comparisons and those
'     comparison_differences  with a nonzero difference
'   A variant with a controls.csv passes its lines as the control totals.
'
' CASES
'   DATA-VALID-01, DATA-INVALID-01, DATA-EVENT-01, DATA-IDENT-01,
'   DATA-EXPO-01, DATA-RENEG-01, DATA-PIT-01 and DATA-RECON-01 through
'   TEST_ImportCase; DATA-REJECT-01 through TEST_ImportCase and then
'   TEST_ImportAdapter.
'==============================================================================

Option Explicit
Option Private Module

Private Const SEP As String = "; "

Public Sub TEST_ImportCase(ByVal CaseId As String)
    Dim I As Long, Name As String, V As String, Start As Date, Finish As Date, Allow As Variant
    If Not CORE_ParseDate(TEST_Expected.TEST_Value(CaseId, "/settings/window_start"), Start) Then
        Err.Raise vbObjectError + 4, "TEST_Import", "Bad window_start in " & CaseId
    End If
    If Not CORE_ParseDate(TEST_Expected.TEST_Value(CaseId, "/settings/window_end"), Finish) Then
        Err.Raise vbObjectError + 4, "TEST_Import", "Bad window_end in " & CaseId
    End If
    Allow = Strings(CaseId, "/settings/currency_allowlist")
    For I = 0 To TEST_Expected.TEST_Count(CaseId, "/variants") - 1
        Name = TEST_Expected.TEST_Key(CaseId, "/variants", I)
        V = "/variants/" & Name
        CheckVariant CaseId, Name, V, Start, Finish, Allow
    Next I
End Sub

Private Sub CheckVariant(ByVal CaseId As String, ByVal Name As String, ByVal V As String, _
                         ByVal Start As Date, ByVal Finish As Date, ByVal Allow As Variant)
    Dim L() As Byte, LN As Long, P() As Byte, PN As Long, R() As Byte, RN As Long, Errors As Long
    Dim Label As String, Accepted As Boolean, Controls As Variant, C() As Byte, CN As Long
    Label = CaseId & "/" & Name & " "
    L = TEST_Fixtures.TEST_FixtureBytes(CaseId & "/" & Name & "/loans.csv", LN)
    P = TEST_Fixtures.TEST_FixtureBytes(CaseId & "/" & Name & "/loan_panel.csv", PN)
    R = TEST_Fixtures.TEST_FixtureBytes(CaseId & "/" & Name & "/market_rates.csv", RN)
    If TEST_Fixtures.TEST_HasFixture(CaseId & "/" & Name & "/controls.csv") Then
        C = TEST_Fixtures.TEST_FixtureBytes(CaseId & "/" & Name & "/controls.csv", CN)
        Controls = ControlLines(C, CN)
        Errors = CORE_ReadImport(L, LN, P, PN, R, RN, Start, Finish, Allow, Controls)
    Else
        Errors = CORE_ReadImport(L, LN, P, PN, R, RN, Start, Finish, Allow)
    End If
    Accepted = (TEST_Expected.TEST_Value(CaseId, V & "/accepted") = "1")
    TEST_Harness.TEST_CheckTrue Label & "accepted", (Errors = 0) = Accepted
    TEST_Harness.TEST_CheckEqual Label & "errors", ResultText(CORE_ImportResult("errors"), 3), ExpectedText(CaseId, V & "/errors", 3)
    If Len(TEST_Expected.TEST_Kind(CaseId, V & "/warnings")) > 0 Then
        TEST_Harness.TEST_CheckEqual Label & "warnings", ResultText(CORE_ImportResult("warnings"), 3), _
            ExpectedText(CaseId, V & "/warnings", 3)
    End If
    If Len(TEST_Expected.TEST_Kind(CaseId, V & "/gaps")) > 0 Then
        TEST_Harness.TEST_CheckEqual Label & "gaps", ResultText(CORE_ImportResult("gaps"), 2), ExpectedText(CaseId, V & "/gaps", 2)
    End If
    If Len(TEST_Expected.TEST_Kind(CaseId, V & "/missing_extracts")) > 0 Then
        TEST_Harness.TEST_CheckEqual Label & "missing extracts", ResultText(CORE_ImportResult("missing"), 1), _
            ExpectedText(CaseId, V & "/missing_extracts", 0)
    End If
    If Len(TEST_Expected.TEST_Kind(CaseId, V & "/warning_counts")) > 0 Then
        TEST_Harness.TEST_CheckEqual Label & "warning counts", WarningCounts(CORE_ImportResult("warnings")), _
            ExpectedCounts(CaseId, V & "/warning_counts")
    End If
    If Len(TEST_Expected.TEST_Kind(CaseId, V & "/outcomes")) > 0 Then
        TEST_Harness.TEST_CheckEqual Label & "outcomes", Outcomes(CORE_ImportResult("outcomes")), _
            ExpectedOutcomes(CaseId, V & "/outcomes")
    End If
    If Len(TEST_Expected.TEST_Kind(CaseId, V & "/loan_months")) > 0 Then
        CheckLoanMonths Label, CaseId, V & "/loan_months", CORE_ImportResult("loan_months")
    End If
    If Len(TEST_Expected.TEST_Kind(CaseId, V & "/totals")) > 0 Then
        TEST_Harness.TEST_CheckEqual Label & "totals", Totals(CORE_ImportResult("totals")), _
            ExpectedTotals(CaseId, V & "/totals")
    End If
    If Len(TEST_Expected.TEST_Kind(CaseId, V & "/control_differences")) > 0 Then
        TEST_Harness.TEST_CheckEqual Label & "control differences", _
            ResultText(CORE_ImportResult("differences"), 3), ExpectedText(CaseId, V & "/control_differences", 3)
    End If
    If Len(TEST_Expected.TEST_Kind(CaseId, V & "/counts")) > 0 Then
        TEST_Harness.TEST_CheckEqual Label & "counts", ResultText(CORE_ImportResult("counts"), 5), _
            ExpectedCounts5(CaseId, V & "/counts")
    End If
    If Len(TEST_Expected.TEST_Kind(CaseId, V & "/comparison_count")) > 0 Then
        CheckComparisons Label, CaseId, V, CORE_ImportResult("comparisons")
    End If
End Sub

Private Function ExpectedCounts5(ByVal CaseId As String, ByVal Path As String) As String
    'The expected counts as "file:read:accepted:outside:loans; ...", null
    'loans as empty text.
    Dim I As Long, File As String, Item As String
    For I = 0 To TEST_Expected.TEST_Count(CaseId, Path) - 1
        File = TEST_Expected.TEST_Key(CaseId, Path, I)
        Item = Path & "/" & File
        If I > 0 Then ExpectedCounts5 = ExpectedCounts5 & SEP
        ExpectedCounts5 = ExpectedCounts5 & File & ":" & TEST_Expected.TEST_Value(CaseId, Item & "/rows_read") & ":" & _
            TEST_Expected.TEST_Value(CaseId, Item & "/rows_accepted") & ":" & _
            TEST_Expected.TEST_Value(CaseId, Item & "/rows_outside_window") & ":" & _
            TEST_Expected.TEST_Value(CaseId, Item & "/loans")
    Next I
End Function

Private Sub CheckComparisons(ByVal Label As String, ByVal CaseId As String, ByVal V As String, ByVal Table As Variant)
    'The number of comparisons, every one MATCH, and those with a nonzero
    'difference as "key:measure:control:computed:difference".
    Dim I As Long, N As Long, Got As String, Want As String, J As Long, Path As String, Matches As Boolean
    If Not IsEmpty(Table) Then N = UBound(Table, 1)
    TEST_Harness.TEST_CheckEqual Label & "comparison count", CStr(N), _
        TEST_Expected.TEST_Value(CaseId, V & "/comparison_count")
    Matches = True
    For I = 1 To N
        If Table(I, 8) <> "MATCH" Then Matches = False
        If Table(I, 7) <> "0" Then
            If Len(Got) > 0 Then Got = Got & SEP
            Got = Got & Table(I, 1) & "|" & Table(I, 2) & "|" & Table(I, 3) & ":" & Table(I, 4) & ":" & _
                  Table(I, 5) & ":" & Table(I, 6) & ":" & Table(I, 7)
        End If
    Next I
    TEST_Harness.TEST_CheckTrue Label & "every comparison MATCH", Matches
    Path = V & "/comparison_differences"
    For I = 0 To TEST_Expected.TEST_Count(CaseId, Path) - 1
        If I > 0 Then Want = Want & SEP
        Want = Want & TEST_Expected.TEST_Value(CaseId, Path & "/" & I & "/0") & ":" & _
               TEST_Expected.TEST_Value(CaseId, Path & "/" & I & "/1")
        For J = 2 To 4
            Want = Want & ":" & CORE_DecimalText(Exact(TEST_Expected.TEST_Value(CaseId, Path & "/" & I & "/" & J)))
        Next J
    Next I
    TEST_Harness.TEST_CheckEqual Label & "comparison differences", Got, Want
End Sub

Private Function ControlLines(ByRef Data() As Byte, ByVal Length As Long) As Variant
    'The lines of a controls.csv, 1-based; an empty file gives no lines.
    Dim Lines() As String, Ascii() As Boolean, N As Long
    N = CORE_SplitLines(Data, Length, Lines, Ascii)
    If N = 0 Then
        ControlLines = Array()
    Else
        ControlLines = Lines
    End If
End Function

'------------------------------------------------------------------------------
' Reconciliation totals
'------------------------------------------------------------------------------

Private Function MeasureNames() As Variant
    MeasureNames = Array("loans", "balance", "scheduled_principal", "prepaid_partial", "prepaid_full", _
                         "other_change", "full_count", "full_balance", "maturity_count", "maturity_balance", _
                         "default_count", "default_balance", "reneg_count", "reneg_balance", "sale_count", _
                         "sale_balance")
End Function

Private Function Totals(ByVal Table As Variant) As String
    'Every total as "date|segment|currency=v1,...,v16" in key order, each
    'value as canonical decimal text.
    Dim Items() As String, I As Long, J As Long, N As Long
    If IsEmpty(Table) Then Exit Function
    N = UBound(Table, 1)
    ReDim Items(1 To N)
    For I = 1 To N
        Items(I) = Table(I, 1) & "|" & Table(I, 2) & "|" & Table(I, 3) & "="
        For J = 4 To 19
            If J > 4 Then Items(I) = Items(I) & ","
            Items(I) = Items(I) & Table(I, J)
        Next J
    Next I
    Totals = JoinSorted(Items, N)
End Function

Private Function ExpectedTotals(ByVal CaseId As String, ByVal Path As String) As String
    'The expected totals in the same form; a measure not listed is 0.
    Dim Items() As String, I As Long, J As Long, N As Long, Key As String, Names As Variant, Item As String
    N = TEST_Expected.TEST_Count(CaseId, Path)
    If N = 0 Then Exit Function
    Names = MeasureNames()
    ReDim Items(1 To N)
    For I = 1 To N
        Key = TEST_Expected.TEST_Key(CaseId, Path, I - 1)
        Items(I) = Key & "="
        For J = 0 To 15
            If J > 0 Then Items(I) = Items(I) & ","
            Item = Path & "/" & Key & "/" & Names(J)
            If Len(TEST_Expected.TEST_Kind(CaseId, Item)) > 0 Then
                Items(I) = Items(I) & CORE_DecimalText(Exact(TEST_Expected.TEST_Value(CaseId, Item)))
            Else
                Items(I) = Items(I) & "0"
            End If
        Next J
    Next I
    ExpectedTotals = JoinSorted(Items, N)
End Function

'------------------------------------------------------------------------------
' Lists as text
'------------------------------------------------------------------------------

Private Function ResultText(ByVal Table As Variant, ByVal Width As Long) As String
    'The rows of a result table as "a:b:c; a:b:c".
    Dim I As Long, J As Long, Row As String
    If IsEmpty(Table) Then Exit Function
    For I = 1 To UBound(Table, 1)
        Row = ""
        For J = 1 To Width
            If J > 1 Then Row = Row & ":"
            Row = Row & Table(I, J)
        Next J
        If I > 1 Then ResultText = ResultText & SEP
        ResultText = ResultText & Row
    Next I
End Function

Private Function ExpectedText(ByVal CaseId As String, ByVal Path As String, ByVal Width As Long) As String
    'An expected list in the same form; Width 0 for a list of scalars.
    Dim I As Long, J As Long, Row As String
    For I = 0 To TEST_Expected.TEST_Count(CaseId, Path) - 1
        If Width = 0 Then
            Row = TEST_Expected.TEST_Value(CaseId, Path & "/" & I)
        Else
            Row = ""
            For J = 0 To Width - 1
                If J > 0 Then Row = Row & ":"
                Row = Row & TEST_Expected.TEST_Value(CaseId, Path & "/" & I & "/" & J)
            Next J
        End If
        If I > 0 Then ExpectedText = ExpectedText & SEP
        ExpectedText = ExpectedText & Row
    Next I
End Function

Private Function Strings(ByVal CaseId As String, ByVal Path As String) As Variant
    'An expected list of strings as a 0-based array.
    Dim N As Long, I As Long, Out() As String
    N = TEST_Expected.TEST_Count(CaseId, Path)
    ReDim Out(0 To N - 1)
    For I = 0 To N - 1
        Out(I) = TEST_Expected.TEST_Value(CaseId, Path & "/" & I)
    Next I
    Strings = Out
End Function

Private Function WarningCounts(ByVal Table As Variant) As String
    'Counts of each warning code, as "W01=1; W03=2" in code order.
    Dim Codes As Variant, Code As Variant, I As Long, N As Long, Text As String
    Codes = Array("W01", "W02", "W03", "W04", "W05", "W06")
    For Each Code In Codes
        N = 0
        If Not IsEmpty(Table) Then
            For I = 1 To UBound(Table, 1)
                If Table(I, 3) = Code Then N = N + 1
            Next I
        End If
        If N > 0 Then
            If Len(Text) > 0 Then Text = Text & SEP
            Text = Text & Code & "=" & N
        End If
    Next Code
    WarningCounts = Text
End Function

Private Function ExpectedCounts(ByVal CaseId As String, ByVal Path As String) As String
    Dim Codes As Variant, Code As Variant, Text As String
    Codes = Array("W01", "W02", "W03", "W04", "W05", "W06")
    For Each Code In Codes
        If Len(TEST_Expected.TEST_Kind(CaseId, Path & "/" & Code)) > 0 Then
            If Len(Text) > 0 Then Text = Text & SEP
            Text = Text & Code & "=" & TEST_Expected.TEST_Value(CaseId, Path & "/" & Code)
        End If
    Next Code
    ExpectedCounts = Text
End Function

Private Function Outcomes(ByVal Table As Variant) As String
    'The outcome table as "loan|start=outcome" entries in text order.
    Dim Items() As String, I As Long, N As Long
    If IsEmpty(Table) Then Exit Function
    N = UBound(Table, 1)
    ReDim Items(1 To N)
    For I = 1 To N
        Items(I) = Table(I, 1) & "|" & Table(I, 2) & "=" & Table(I, 3)
    Next I
    Outcomes = JoinSorted(Items, N)
End Function

Private Function ExpectedOutcomes(ByVal CaseId As String, ByVal Path As String) As String
    Dim Items() As String, I As Long, N As Long, Key As String
    N = TEST_Expected.TEST_Count(CaseId, Path)
    If N = 0 Then Exit Function
    ReDim Items(1 To N)
    For I = 1 To N
        Key = TEST_Expected.TEST_Key(CaseId, Path, I - 1)
        Items(I) = Key & "=" & TEST_Expected.TEST_Value(CaseId, Path & "/" & Key)
    Next I
    ExpectedOutcomes = JoinSorted(Items, N)
End Function

Private Function JoinSorted(ByRef Items() As String, ByVal N As Long) As String
    'Insertion sort by binary text; the lists here are short.
    Dim I As Long, J As Long, T As String
    For I = 2 To N
        T = Items(I)
        J = I - 1
        Do While J >= 1
            If StrComp(Items(J), T, vbBinaryCompare) <= 0 Then Exit Do
            Items(J + 1) = Items(J)
            J = J - 1
        Loop
        Items(J + 1) = T
    Next I
    For I = 1 To N
        If I > 1 Then JoinSorted = JoinSorted & SEP
        JoinSorted = JoinSorted & Items(I)
    Next I
End Function

'------------------------------------------------------------------------------
' Loan-month exposures
'------------------------------------------------------------------------------

Private Sub CheckLoanMonths(ByVal Label As String, ByVal CaseId As String, ByVal Path As String, ByVal Table As Variant)
    Dim I As Long, J As Long, Key As String, Row As Long, Available As Variant, Prepaid As Variant
    Dim Want As Variant, Item As String
    For I = 0 To TEST_Expected.TEST_Count(CaseId, Path) - 1
        Key = TEST_Expected.TEST_Key(CaseId, Path, I)
        Item = Path & "/" & Key
        Row = 0
        If Not IsEmpty(Table) Then
            For J = 1 To UBound(Table, 1)
                If Table(J, 1) & "|" & Table(J, 2) = Key Then Row = J
            Next J
        End If
        TEST_Harness.TEST_CheckTrue Label & "loan-month " & Key & " present", Row > 0
        If Row > 0 Then
            Available = Exact(Table(Row, 3))
            Prepaid = Exact(Table(Row, 4))
            TEST_Harness.TEST_CheckTrue Label & Key & " available", _
                Available = Exact(TEST_Expected.TEST_Value(CaseId, Item & "/available"))
            TEST_Harness.TEST_CheckTrue Label & Key & " prepaid", _
                Prepaid = Exact(TEST_Expected.TEST_Value(CaseId, Item & "/prepaid"))
            If Len(TEST_Expected.TEST_Kind(CaseId, Item & "/smm")) > 0 Then
                Want = Exact(TEST_Expected.TEST_Value(CaseId, Item & "/smm"))
                TEST_Harness.TEST_CheckTrue Label & Key & " SMM", Prepaid / Available = Want
            End If
        End If
    Next I
End Sub

Private Function Exact(ByVal Text As String) As Variant
    'The Decimal value of a decimal text of up to 28 decimals.
    Dim V As Variant
    If Not CORE_ParseDecimal(Text, 28, V) Then
        Err.Raise vbObjectError + 5, "TEST_Import", "Not a decimal: " & Text
    End If
    Exact = V
End Function
