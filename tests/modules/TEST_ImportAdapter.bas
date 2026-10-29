Attribute VB_Name = "TEST_ImportAdapter"
'==============================================================================
' MODULE: TEST_ImportAdapter
'------------------------------------------------------------------------------
' PURPOSE
'   DATA-REJECT-01 in the test build: the import adapter WB_Import, driven
'   through WB_ImportBytes with the committed fixtures (no file is read,
'   W10). After the core checks of every variant (TEST_Import), the accepted
'   variant is imported, its Import, Reconciliation and Run areas are
'   checked against the expected file, and then each rejected variant is
'   imported and must leave the accepted dataset and its areas unchanged,
'   mark the result sheets STALE and the run FAILED, and log the rejection.
'
' STATE
'   Sets the run settings and Controls_Totals of the test build for the run
'   and restores them on every exit path. The Import, Findings,
'   Reconciliation and Log areas keep what the last import wrote.
'==============================================================================

Option Explicit
Option Private Module

Private Const CASE_ID As String = "DATA-REJECT-01"
Private Const SEP As String = "; "

Private mStep As String    'the step running, named in an error message

Public Sub TEST_DataReject01()
    Dim Saved As Variant, Failure As String
    mStep = "core checks"
    TEST_Import.TEST_ImportCase CASE_ID
    mStep = "saving the inputs"
    Saved = SaveInputs()
    On Error GoTo Restore
    mStep = "setting the inputs"
    SetInputs
    CheckImports
Restore:
    If Err.Number <> 0 Then Failure = "VBA error " & Err.Number & " at " & mStep & ": " & Err.Description
    On Error GoTo 0
    RestoreInputs Saved
    If Len(Failure) > 0 Then Err.Raise vbObjectError + 6, "TEST_ImportAdapter", Failure
End Sub

Private Sub CheckImports()
    Dim Errors As Long, RunA As String, Before As String, Variants As Variant, Name As Variant, V As String
    Dim Sheet As Variant, RunId As String, Logged As Variant
    mStep = "accepted import"
    Errors = ImportVariant("accepted")
    TEST_Harness.TEST_CheckTrue "accepted import has no error", Errors = 0
    RunA = PREPAY_DatasetRunId()
    TEST_Harness.TEST_CheckEqual "dataset run ID", RunA, NamedText("Run_ID")
    TEST_Harness.TEST_CheckTrue "run ID form", RunA Like "IMPORT-########-######*"
    TEST_Harness.TEST_CheckEqual "Run_Status", Left$(NamedText("Run_Status"), Len(StatusPrefix("CURRENT", RunA))), _
        StatusPrefix("CURRENT", RunA)
    For Each Sheet In Array("Import", "Findings", "Reconciliation")
        TEST_Harness.TEST_CheckEqual Sheet & "_Status", Left$(NamedText(Sheet & "_Status"), Len(StatusPrefix("CURRENT", RunA))), _
            StatusPrefix("CURRENT", RunA)
    Next Sheet
    mStep = "accepted areas"
    CheckAccepted
    mStep = "snapshot"
    Before = Snapshot()
    Variants = Array("invalid-loans", "invalid-panel", "invalid-rates")
    For Each Name In Variants
        V = "/variants/" & Name
        mStep = Name & " import"
        Errors = ImportVariant(CStr(Name))
        mStep = Name & " checks"
        RunId = NamedText("Run_ID")
        TEST_Harness.TEST_CheckEqual Name & " errors", CStr(Errors), CStr(TEST_Expected.TEST_Count(CASE_ID, V & "/errors"))
        TEST_Harness.TEST_CheckTrue Name & " has its own run ID", RunId <> RunA And Len(RunId) > 0
        TEST_Harness.TEST_CheckEqual Name & " leaves the dataset and its areas", Snapshot(), Before
        TEST_Harness.TEST_CheckEqual Name & " Run_Status", Left$(NamedText("Run_Status"), Len(StatusPrefix("FAILED", RunId))), _
            StatusPrefix("FAILED", RunId)
        TEST_Harness.TEST_CheckEqual Name & " Findings_Status", _
            Left$(NamedText("Findings_Status"), Len(StatusPrefix("CURRENT", RunId))), StatusPrefix("CURRENT", RunId)
        For Each Sheet In Array("Calibration", "Backtest", "CashFlows", "EVE", "Gap", "Measures")
            TEST_Harness.TEST_CheckEqual Name & " " & Sheet & "_Status", _
                Left$(NamedText(Sheet & "_Status"), Len(StatusPrefix("STALE", RunId))), StatusPrefix("STALE", RunId)
        Next Sheet
        TEST_Harness.TEST_CheckEqual Name & " first finding", FirstFinding(), _
            TEST_Expected.TEST_Value(CASE_ID, V & "/errors/0/2") & ":" & _
            TEST_Expected.TEST_Value(CASE_ID, V & "/errors/0/0") & ":" & TEST_Expected.TEST_Value(CASE_ID, V & "/errors/0/1")
        Logged = LastLogRow()
        TEST_Harness.TEST_CheckEqual Name & " log row", Logged(1) & ":" & Logged(2) & ":" & Logged(5) & ":" & Logged(7), _
            RunId & ":IMPORT:REJECTED:Y"
    Next Name
End Sub

Private Sub CheckAccepted()
    'Import_Counts, Import_Outcomes, Reconciliation_Totals and
    'Reconciliation_Controls of the accepted variant.
    Dim V As String, Want As String, I As Long, File As String, Item As String, N As Long, Key As String
    Dim Parts As Variant, Path As String, Items() As String
    V = "/variants/accepted"
    mStep = "Import_Counts"
    Path = V & "/counts"
    For I = 0 To TEST_Expected.TEST_Count(CASE_ID, Path) - 1
        File = TEST_Expected.TEST_Key(CASE_ID, Path, I)
        Item = Path & "/" & File
        If I > 0 Then Want = Want & SEP
        Want = Want & File & ":" & TEST_Expected.TEST_Value(CASE_ID, V & "/sizes/" & File) & ":" & _
               TEST_Expected.TEST_Value(CASE_ID, V & "/fingerprints/" & File) & ":" & _
               TEST_Expected.TEST_Value(CASE_ID, Item & "/rows_read") & ":" & _
               TEST_Expected.TEST_Value(CASE_ID, Item & "/rows_accepted") & ":" & _
               TEST_Expected.TEST_Value(CASE_ID, Item & "/rows_outside_window") & ":" & _
               TEST_Expected.TEST_Value(CASE_ID, Item & "/loans")
    Next I
    TEST_Harness.TEST_CheckEqual "Import_Counts", TableText("Import_Counts", ":", False), Want
    mStep = "Import_Outcomes"
    Path = V & "/import_outcomes"
    N = TEST_Expected.TEST_Count(CASE_ID, Path)
    ReDim Items(1 To N)
    For I = 1 To N
        Key = TEST_Expected.TEST_Key(CASE_ID, Path, I - 1)
        Parts = Split(Key, "|")
        Items(I) = Join(Parts, ":") & ":" & TEST_Expected.TEST_Value(CASE_ID, Path & "/" & Key & "/loan_months") & ":" & _
                   CORE_DecimalText(Exact(TEST_Expected.TEST_Value(CASE_ID, Path & "/" & Key & "/balance")))
    Next I
    TEST_Harness.TEST_CheckEqual "Import_Outcomes", TableText("Import_Outcomes", ":", True), JoinSorted(Items, N)
    mStep = "Reconciliation"
    TEST_Harness.TEST_CheckEqual "Reconciliation_Totals", TableText("Reconciliation_Totals", ":", False), _
        ResultText(PREPAY_DatasetResult("totals"))
    TEST_Harness.TEST_CheckEqual "Reconciliation_Controls", TableText("Reconciliation_Controls", ":", False), _
        ResultText(PREPAY_DatasetResult("comparisons"))
    TEST_Harness.TEST_CheckEqual "Reconciliation_Controls rows", CStr(TableRows("Reconciliation_Controls")), _
        TEST_Expected.TEST_Value(CASE_ID, V & "/comparison_count")
    mStep = "Findings_Summary"
    TEST_Harness.TEST_CheckEqual "Findings_Summary", TableText("Findings_Summary", ":", False), _
        "W02:WARNING:1; W04:WARNING:2"
End Sub

'------------------------------------------------------------------------------
' Driving the adapter
'------------------------------------------------------------------------------

Private Function ImportVariant(ByVal Name As String) As Long
    Dim L() As Byte, LN As Long, P() As Byte, PN As Long, R() As Byte, RN As Long, Prefix As String
    Prefix = CASE_ID & "/" & Name & "/"
    L = TEST_Fixtures.TEST_FixtureBytes(Prefix & "loans.csv", LN)
    P = TEST_Fixtures.TEST_FixtureBytes(Prefix & "loan_panel.csv", PN)
    R = TEST_Fixtures.TEST_FixtureBytes(Prefix & "market_rates.csv", RN)
    ImportVariant = WB_ImportBytes(L, LN, P, PN, R, RN, Array("loans.csv", "loan_panel.csv", "market_rates.csv"))
End Function

Private Sub SetInputs()
    'The case settings and the controls.csv of the accepted variant (all
    'variants share it), as text.
    Dim Data() As Byte, Length As Long, Lines() As String, Ascii() As Boolean, N As Long, I As Long
    Dim Header As Range, Fields As Variant, Allow As String, J As Long
    SetText NamedRange("cfg_data_window_start"), TEST_Expected.TEST_Value(CASE_ID, "/settings/window_start")
    SetText NamedRange("cfg_data_window_end"), TEST_Expected.TEST_Value(CASE_ID, "/settings/window_end")
    For I = 0 To TEST_Expected.TEST_Count(CASE_ID, "/settings/currency_allowlist") - 1
        If I > 0 Then Allow = Allow & ","
        Allow = Allow & TEST_Expected.TEST_Value(CASE_ID, "/settings/currency_allowlist/" & I)
    Next I
    SetText NamedRange("cfg_currency_allowlist"), Allow
    SetText NamedRange("cfg_timely_reporting_attested"), "Y"
    Set Header = NamedRange("Controls_Totals")
    ClearBody Header, 19
    Data = TEST_Fixtures.TEST_FixtureBytes(CASE_ID & "/accepted/controls.csv", Length)
    N = CORE_SplitLines(Data, Length, Lines, Ascii)
    For I = 2 To N
        Fields = Split(Lines(I), ",")
        For J = 0 To UBound(Fields)
            SetText Header.Offset(I - 1, J), CStr(Fields(J))
        Next J
    Next I
End Sub

Private Function SaveInputs() As Variant
    'The four settings and the Controls_Totals body, values and formats.
    Dim Header As Range, Height As Long
    Set Header = NamedRange("Controls_Totals")
    Height = MaxOf(LastRow(Header, 19) - Header.Row, 20)
    SaveInputs = Array( _
        SavedCell("cfg_data_window_start"), SavedCell("cfg_data_window_end"), _
        SavedCell("cfg_currency_allowlist"), SavedCell("cfg_timely_reporting_attested"), _
        Height, Header.Offset(1, 0).Resize(Height, 19).Value, Header.Offset(1, 0).Resize(Height, 19).NumberFormat)
End Function

Private Function SavedCell(ByVal Name As String) As Variant
    SavedCell = Array(Name, NamedRange(Name).Value, NamedRange(Name).NumberFormat)
End Function

Private Sub RestoreInputs(ByVal Saved As Variant)
    Dim I As Long, Header As Range, Body As Range, Cell As Variant
    On Error Resume Next    'restore as much as possible; a failure here is reported by the checks that follow
    For I = 0 To 3
        Cell = Saved(I)
        NamedRange(CStr(Cell(0))).NumberFormat = Cell(2)
        If IsEmpty(Cell(1)) Then
            NamedRange(CStr(Cell(0))).ClearContents
        Else
            NamedRange(CStr(Cell(0))).Value = Cell(1)
        End If
    Next I
    Set Header = NamedRange("Controls_Totals")
    ClearBody Header, 19
    Set Body = Header.Offset(1, 0).Resize(Saved(4), 19)
    Body.NumberFormat = "@"
    Body.Value = Saved(5)
    If Not IsNull(Saved(6)) Then Body.NumberFormat = Saved(6)
End Sub

'------------------------------------------------------------------------------
' Reading the workbook
'------------------------------------------------------------------------------

Private Function Snapshot() As String
    'Everything a rejected import must leave unchanged: the dataset and the
    'Import and Reconciliation areas with their statuses.
    Dim Kind As Variant, Name As Variant
    Snapshot = PREPAY_DatasetRunId()
    For Each Kind In Array("counts", "outcomes", "loan_outcomes", "totals", "comparisons", "warnings", "gaps", _
                           "loan_months")
        Snapshot = Snapshot & "|" & Kind & "=" & ResultText(PREPAY_DatasetResult(CStr(Kind)))
    Next Kind
    For Each Name In Array("Import_Lineage", "Import_Counts", "Import_Outcomes", "Reconciliation_Totals", _
                           "Reconciliation_Controls")
        Snapshot = Snapshot & "|" & Name & "=" & TableText(CStr(Name), ":", False)
    Next Name
    Snapshot = Snapshot & "|" & NamedText("Import_Status") & "|" & NamedText("Reconciliation_Status")
End Function

Private Function FirstFinding() As String
    'code:file:line of the first Findings_Rows row.
    Dim Header As Range
    Set Header = NamedRange("Findings_Rows")
    FirstFinding = CStr(Header.Offset(1, 0).Value) & ":" & CStr(Header.Offset(1, 1).Value) & ":" & _
                   CStr(Header.Offset(1, 2).Value)
End Function

Private Function LastLogRow() As Variant
    'The cells of the last Log_Runs row, 1-based.
    Dim Header As Range, Last As Long, Out(1 To 8) As String, J As Long
    Set Header = NamedRange("Log_Runs")
    Last = LastRow(Header, 8)
    For J = 1 To 8
        Out(J) = CStr(Header.Worksheet.Cells(Last, Header.Column + J - 1).Value)
    Next J
    LastLogRow = Out
End Function

Private Function TableText(ByVal Name As String, ByVal Joint As String, ByVal Sort As Boolean) As String
    'The rows under a table's header as "a:b:c; a:b:c", optionally sorted.
    Dim Header As Range, Width As Long, N As Long, I As Long, J As Long, Row As String, Items() As String
    Set Header = NamedRange(Name)
    Do While Len(CStr(Header.Offset(0, Width).Value)) > 0
        Width = Width + 1
    Loop
    N = LastRow(Header, Width) - Header.Row
    If N = 0 Then Exit Function
    ReDim Items(1 To N)
    For I = 1 To N
        Row = ""
        For J = 0 To Width - 1
            If J > 0 Then Row = Row & Joint
            Row = Row & CStr(Header.Offset(I, J).Value)
        Next J
        Items(I) = Row
    Next I
    If Sort Then
        TableText = JoinSorted(Items, N)
    Else
        TableText = Join(Items, SEP)
    End If
End Function

Private Function TableRows(ByVal Name As String) As Long
    Dim Header As Range
    Set Header = NamedRange(Name)
    TableRows = LastRow(Header, 1) - Header.Row
End Function

Private Function ResultText(ByVal Table As Variant) As String
    Dim I As Long, J As Long, Row As String
    If IsEmpty(Table) Then Exit Function
    For I = 1 To UBound(Table, 1)
        Row = ""
        For J = 1 To UBound(Table, 2)
            If J > 1 Then Row = Row & ":"
            Row = Row & Table(I, J)
        Next J
        If I > 1 Then ResultText = ResultText & SEP
        ResultText = ResultText & Row
    Next I
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

Private Function StatusPrefix(ByVal State As String, ByVal RunId As String) As String
    StatusPrefix = State & ": " & RunId & ", "
End Function

Private Function NamedRange(ByVal Name As String) As Range
    Set NamedRange = ThisWorkbook.Names(Name).RefersToRange
End Function

Private Function NamedText(ByVal Name As String) As String
    NamedText = CStr(NamedRange(Name).Value)
End Function

Private Sub SetText(ByVal Cell As Range, ByVal Text As String)
    Cell.NumberFormat = "@"
    Cell.Value = Text
End Sub

Private Sub ClearBody(ByVal Header As Range, ByVal Width As Long)
    Dim Last As Long
    Last = LastRow(Header, Width)
    If Last > Header.Row Then Header.Offset(1, 0).Resize(Last - Header.Row, Width).ClearContents
End Sub

Private Function LastRow(ByVal Header As Range, ByVal Width As Long) As Long
    'The last row with a value in the columns of the table, at least the
    'header row: one read of the block between the header and the bottom
    'of the used range.
    Dim Used As Range, Bottom As Long, Block As Variant, I As Long, J As Long
    LastRow = Header.Row
    Set Used = Header.Worksheet.UsedRange
    Bottom = Used.Row + Used.Rows.Count - 1
    If Bottom <= Header.Row Then Exit Function
    Block = Header.Offset(1, 0).Resize(Bottom - Header.Row, Width).Value
    If Not IsArray(Block) Then
        If Not IsEmpty(Block) Then LastRow = Header.Row + 1
        Exit Function
    End If
    For I = UBound(Block, 1) To 1 Step -1
        For J = 1 To Width
            If Not IsEmpty(Block(I, J)) Then
                LastRow = Header.Row + I
                Exit Function
            End If
        Next J
    Next I
End Function

Private Function MaxOf(ByVal A As Long, ByVal B As Long) As Long
    If A > B Then MaxOf = A Else MaxOf = B
End Function

Private Function Exact(ByVal Text As String) As Variant
    Dim V As Variant
    If Not CORE_ParseDecimal(Text, 28, V) Then
        Err.Raise vbObjectError + 5, "TEST_ImportAdapter", "Not a decimal: " & Text
    End If
    Exact = V
End Function
