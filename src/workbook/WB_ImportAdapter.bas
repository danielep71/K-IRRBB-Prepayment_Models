Attribute VB_Name = "WB_ImportAdapter"
'==============================================================================
' MODULE: WB_ImportAdapter
'------------------------------------------------------------------------------
' PURPOSE
'   Workbook adapter of the import (docs/WORKBOOK_CONTRACT.md, operation
'   WB_Import): reads the run settings and Controls_Totals, calls the
'   PREPAY_Dataset facade and writes the Import, Findings, Reconciliation and
'   Log areas and the statuses.
'
' ENTRY POINTS
'   WB_Import        Asks for the three files, reads them read-only and
'                    imports them; shows the outcome in a message box.
'   WB_ImportBytes   The import from bytes already read, with the file
'                    names to record. Used by WB_Import and by the tests, so
'                    that no test reads a file (W10). Returns the number of
'                    errors, or -1 when the operation failed before or
'                    outside the validation (a name, a setting or a VBA
'                    error).
'
' FILE ACCESS (W10)
'   Only WB_Import reads files: the three files the user selects, read-only
'   and whole. No directory path is kept; the lineage records file names.
'
' OUTCOMES
'   ACCEPTED  Import, Findings, Reconciliation and Run_Status CURRENT.
'   REJECTED  Findings CURRENT; Import, Reconciliation and the accepted
'             dataset unchanged; Run_Status FAILED.
'   FAILED    Findings cleared and FAILED; Run_Status FAILED; Import and
'             Reconciliation unchanged, or FAILED if they were partly
'             written.
'   Every outcome marks every result sheet STALE and appends one Log row,
'   after Calculation, EnableEvents, ScreenUpdating and DisplayAlerts are
'   restored; a failed Log write is reported apart. A missing or misplaced
'   name stops the operation before anything is written, so it is reported
'   by WB_Import only. A cancelled file selection changes and logs nothing.
'
' VALUES
'   Settings and control-total cells are read as text in the file format
'   (W11); every value written is text, so nothing depends on the host
'   locale or loses decimals.
'==============================================================================

Option Explicit

Private Const OPERATION As String = "IMPORT"
Private Const MAX_FINDING_ROWS As Long = 100000    'W4
Private Const XL_MANUAL As Long = -4135
Private Const ERR_SETUP As Long = 1401
Private Const SOURCE As String = "WB_ImportAdapter"

'Of the last WB_ImportBytes, for the message of WB_Import.
Private mFailure As String    'the error that made it fail
Private mLogError As String   'the error that stopped its Log row, if any

'------------------------------------------------------------------------------
' Entry points
'------------------------------------------------------------------------------

Public Sub WB_Import()
    Dim Roles As Variant, Paths(0 To 2) As String, Picked As Variant, I As Long, Errors As Long
    Dim L() As Byte, LN As Long, P() As Byte, PN As Long, R() As Byte, RN As Long
    Roles = Array("loans.csv", "loan_panel.csv", "market_rates.csv")
    If Not Attested() Then
        MsgBox "Set timely_reporting_attested to Y on Settings before an import.", vbExclamation, SOURCE
        Exit Sub
    End If
    For I = 0 To 2
        Picked = Application.GetOpenFilename("CSV files (*.csv),*.csv", , "Select " & Roles(I))
        If VarType(Picked) = vbBoolean Then
            MsgBox "Import cancelled; nothing was changed.", vbInformation, SOURCE
            Exit Sub
        End If
        Paths(I) = CStr(Picked)
    Next I
    On Error GoTo Unreadable
    ReadFile Paths(0), L, LN
    ReadFile Paths(1), P, PN
    ReadFile Paths(2), R, RN
    On Error GoTo 0
    Errors = WB_ImportBytes(L, LN, P, PN, R, RN, Array(BaseName(Paths(0)), BaseName(Paths(1)), BaseName(Paths(2))))
    Select Case Errors
        Case 0
            MsgBox "Import accepted: " & NamedText("Run_ID") & ". Warnings are on Findings.", vbInformation, SOURCE
        Case Is > 0
            MsgBox "Import rejected with " & Errors & " errors; see Findings. The accepted dataset is unchanged.", _
                   vbExclamation, SOURCE
        Case Else
            MsgBox "Import failed: " & mFailure, vbCritical, SOURCE
    End Select
    If Len(mLogError) > 0 Then MsgBox "The Log row could not be written: " & mLogError, vbExclamation, SOURCE
    Exit Sub
Unreadable:
    MsgBox "A selected file could not be read: " & Err.Description & ". Nothing was changed.", vbCritical, SOURCE
End Sub

Public Function WB_ImportBytes(ByRef LoansData() As Byte, ByVal LoansLength As Long, _
                               ByRef PanelData() As Byte, ByVal PanelLength As Long, _
                               ByRef RatesData() As Byte, ByVal RatesLength As Long, _
                               ByVal FileNames As Variant) As Long
    'FileNames: 0-based array of the selected file names, without directory,
    'for loans.csv, loan_panel.csv and market_rates.csv.
    Dim State As Variant, Started As Date, RunId As String, Errors As Long, Outcome As String
    Dim FirstError As String, Restored As Boolean, Stage As String, Settings As Collection, Controls As Variant
    Started = Now
    mFailure = ""
    mLogError = ""
    State = SaveState()
    Errors = -1
    On Error GoTo Failed
    QuietState
    Stage = "names"
    CheckNames
    RunId = NewRunId(Started)
    Stage = "settings"
    Set Settings = ReadSettings()
    If Settings.Item("timely_reporting_attested") <> "Y" Then
        Err.Raise vbObjectError + ERR_SETUP, SOURCE, "timely_reporting_attested must be Y"
    End If
    Controls = ControlLines()
    Stage = "import"
    Errors = PREPAY_Import(LoansData, LoansLength, PanelData, PanelLength, RatesData, RatesLength, _
                           Settings.Item("data_window_start"), Settings.Item("data_window_end"), _
                           Settings.Item("currency_allowlist"), Controls, RunId)
    Stage = "findings"
    WriteFindings
    If Errors = 0 Then
        Stage = "dataset"
        WriteDataset RunId, Started, FileNames, Settings, UBound(Controls) - 1
        SetStatus "Import", "CURRENT", RunId, Started
        SetStatus "Reconciliation", "CURRENT", RunId, Started
        Outcome = "ACCEPTED"
    Else
        Outcome = "REJECTED"
        FirstError = FirstFinding()
    End If
    SetStatus "Findings", "CURRENT", RunId, Started
    MarkResultsStale RunId, Started
    SetRun IIf(Errors = 0, "CURRENT", "FAILED"), RunId, Started
Finish:
    Restored = RestoreState(State)
    If Stage <> "names" Then mLogError = AppendLog(RunId, Started, Outcome, Restored, FirstError)
    WB_ImportBytes = Errors
    Exit Function
Failed:
    FirstError = "VBA error " & Err.Number & " in " & Stage & ": " & Err.Description
    mFailure = FirstError
    Errors = -1
    Outcome = "FAILED"
    If Stage <> "names" Then RecordFailure RunId, Started
    Resume Finish
End Function

'------------------------------------------------------------------------------
' Inputs
'------------------------------------------------------------------------------

Private Function ControlLines() As Variant
    'The Controls_Totals table as lines, header first: every row from the
    'header down to the last row with a value, its cells joined with commas.
    'A cell holding a number or date instead of text becomes "?", which no
    'rule accepts, so its row is invalid (W11).
    Dim Header As Range, Width As Long, Last As Long, Lines() As String, I As Long, J As Long, Line As String
    Set Header = NamedRange("Controls_Totals")
    Width = HeaderWidth(Header)
    Last = LastRow(Header, Width)
    ReDim Lines(1 To Last - Header.Row + 1)
    For I = 0 To Last - Header.Row
        Line = ""
        For J = 0 To Width - 1
            If J > 0 Then Line = Line & ","
            Line = Line & CellText(Header.Offset(I, J), True)
        Next J
        Lines(I + 1) = Line
    Next I
    ControlLines = Lines
End Function

Private Function ReadSettings() As Collection
    'The run settings the import uses or records, keyed by code, as typed; a
    'number or date value stops the operation (W11).
    Dim Code As Variant, Cell As Range, Out As Collection
    Set Out = New Collection
    For Each Code In SettingCodes()
        Set Cell = NamedRange("cfg_" & Code)
        If Not IsEmpty(Cell.Value) And VarType(Cell.Value) <> vbString Then
            Err.Raise vbObjectError + ERR_SETUP, SOURCE, Code & " must be text in the file format (W11)"
        End If
        Out.Add CellText(Cell, False), CStr(Code)
    Next Code
    Set ReadSettings = Out
End Function

Private Function SettingCodes() As Variant
    SettingCodes = Array("data_window_start", "data_window_end", "segment_list", "currency_allowlist", _
                         "refi_curve_series", "timely_reporting_attested")
End Function

Private Function CellText(ByVal Cell As Range, ByVal MarkNonText As Boolean) As String
    Dim V As Variant
    V = Cell.Value
    If IsEmpty(V) Then
        CellText = ""
    ElseIf VarType(V) = vbString Then
        CellText = V
    ElseIf MarkNonText Then
        CellText = "?"
    Else
        CellText = CStr(V)
    End If
End Function

Private Function Attested() As Boolean
    On Error Resume Next
    Attested = (CellText(NamedRange("cfg_timely_reporting_attested"), True) = "Y")
End Function

Private Sub ReadFile(ByVal Path As String, ByRef Data() As Byte, ByRef Length As Long)
    'The whole file, opened read-only and shared; closed on every path.
    Dim F As Integer, Message As String
    F = FreeFile
    Open Path For Binary Access Read Shared As #F
    On Error GoTo Closing
    Length = LOF(F)
    If Length = 0 Then
        ReDim Data(0 To 0)
    Else
        ReDim Data(0 To Length - 1)
        Get #F, , Data
    End If
    Close #F
    Exit Sub
Closing:
    Message = Err.Description
    Close #F
    Err.Raise vbObjectError + ERR_SETUP, SOURCE, Message
End Sub

Private Function BaseName(ByVal Path As String) As String
    'The name without directory, for any of the separators \ / :.
    Dim I As Long
    For I = Len(Path) To 1 Step -1
        If InStr(1, "\/:", Mid$(Path, I, 1), vbBinaryCompare) > 0 Then Exit For
    Next I
    BaseName = Mid$(Path, I + 1)
End Function

'------------------------------------------------------------------------------
' Outputs
'------------------------------------------------------------------------------

Private Sub WriteFindings()
    'Findings_Rows in the contract order (errors, then warnings), at most
    'MAX_FINDING_ROWS rows; Findings_Summary with every count. E12, W01 and
    'E17 carry their keys.
    Dim Errors As Variant, Warnings As Variant, Gaps As Variant, Missing As Variant, Differences As Variant
    Dim N As Long, Found() As Variant, K As Long, I As Long, G As Long, M As Long, D As Long
    Dim Code As String, Key As String, Message As String, Counts As Collection
    Errors = PREPAY_ImportResult("errors")
    Warnings = PREPAY_ImportResult("warnings")
    Gaps = PREPAY_ImportResult("gaps")
    Missing = PREPAY_ImportResult("missing")
    Differences = PREPAY_ImportResult("differences")
    N = RowCount(Errors) + RowCount(Warnings)
    Set Counts = New Collection
    If N > 0 Then ReDim Found(1 To MinOf(N, MAX_FINDING_ROWS), 1 To 5)
    For I = 1 To RowCount(Errors)
        Code = Errors(I, 3)
        Key = ""
        Message = CodeMessage(Code)
        If Code = "E12" Then
            M = M + 1
            Key = Missing(M, 1)
        ElseIf Code = "E17" Then
            D = D + 1
            Key = Differences(D, 2)
            If Len(Differences(D, 3)) > 0 Then
                Message = Message & ": " & Differences(D, 3)
            ElseIf CLng(Differences(D, 1)) = 1 Then
                Message = Message & ": the header differs"
            Else
                Message = Message & ": the row is empty, duplicated or does not parse"
            End If
        End If
        AddFinding Found, K, Counts, Code, CStr(Errors(I, 1)), CStr(Errors(I, 2)), Key, Message
    Next I
    For I = 1 To RowCount(Warnings)
        Code = Warnings(I, 3)
        Key = ""
        If Code = "W01" Then
            G = G + 1
            Key = Gaps(G, 1) & "|" & Gaps(G, 2)
        End If
        AddFinding Found, K, Counts, Code, CStr(Warnings(I, 1)), CStr(Warnings(I, 2)), Key, CodeMessage(Code)
    Next I
    If N > 0 Then
        WriteTable "Findings_Rows", Found
    Else
        WriteTable "Findings_Rows", Empty
    End If
    WriteTable "Findings_Summary", SummaryRows(Counts)
End Sub

Private Sub AddFinding(ByRef Found() As Variant, ByRef K As Long, ByVal Counts As Collection, ByVal Code As String, _
                       ByVal File As String, ByVal Line As String, ByVal Key As String, ByVal Message As String)
    Dim Count As Long
    On Error Resume Next
    Count = Counts.Item(Code)
    If Count > 0 Then Counts.Remove Code
    On Error GoTo 0
    Counts.Add Count + 1, Code
    If K >= MAX_FINDING_ROWS Then Exit Sub
    K = K + 1
    Found(K, 1) = Code
    Found(K, 2) = File
    Found(K, 3) = Line
    Found(K, 4) = Key
    Found(K, 5) = Message
End Sub

Private Function SummaryRows(ByVal Counts As Collection) As Variant
    'code, severity, count for every code found, in code order.
    Dim Codes As Variant, Code As Variant, Out() As Variant, N As Long, Count As Long, I As Long
    SummaryRows = Empty
    Codes = Split("E01 E02 E03 E04 E05 E06 E07 E08 E09 E10 E11 E12 E13 E14 E15 E16 E17 " & _
                  "W01 W02 W03 W04 W05 W06", " ")
    If Counts.Count = 0 Then Exit Function
    ReDim Out(1 To Counts.Count, 1 To 3)
    For Each Code In Codes
        Count = 0
        On Error Resume Next
        Count = Counts.Item(CStr(Code))
        On Error GoTo 0
        If Count > 0 Then
            N = N + 1
            Out(N, 1) = Code
            Out(N, 2) = IIf(Left$(Code, 1) = "E", "ERROR", "WARNING")
            Out(N, 3) = CStr(Count)
        End If
    Next Code
    SummaryRows = Out
End Function

Private Function CodeMessage(ByVal Code As String) As String
    'The rule of each code, as worded in the data contract.
    Select Case Code
        Case "E01": CodeMessage = "Header or field count does not match, or a non-ASCII character"
        Case "E02": CodeMessage = "Invalid ISO date, or as_of_date not a month end"
        Case "E03": CodeMessage = "A required field is empty, or a field that must be empty is not"
        Case "E04": CodeMessage = "Value cannot be parsed or is out of range"
        Case "E05": CodeMessage = "Duplicate key"
        Case "E06": CodeMessage = "Unknown code"
        Case "E07": CodeMessage = "Currency not in the run allowlist"
        Case "E08": CodeMessage = "Unknown loan_id or predecessor_id, or market series currency or tenor differs"
        Case "E09": CodeMessage = "Negative balance, scheduled or prepaid principal"
        Case "E10": CodeMessage = "Row dated after the loan's terminal event"
        Case "E11": CodeMessage = "Inconsistent dates"
        Case "E12": CodeMessage = "Missing extract: no panel rows at this month end"
        Case "E13": CodeMessage = "Balance identity broken"
        Case "E14": CodeMessage = "Event inconsistent with its required flows or dates"
        Case "E15": CodeMessage = "Prepayment above exposure"
        Case "E16": CodeMessage = "RENEG successor mismatch"
        Case "E17": CodeMessage = "Control-total mismatch"
        Case "W01": CodeMessage = "Gap: loan missing in a month between its first and last row"
        Case "W02": CodeMessage = "Censored disappearance: loan stops before the window end without a terminal event"
        Case "W03": CodeMessage = "Non-zero other_change"
        Case "W04": CodeMessage = "Row outside the data window; excluded and counted"
        Case "W05": CodeMessage = "Past maturity: positive balance after the month end of maturity_date"
        Case "W06": CodeMessage = "Segment change at RENEG"
        Case Else: CodeMessage = "Unknown finding"
    End Select
End Function

Private Function FirstFinding() As String
    Dim Errors As Variant
    Errors = PREPAY_ImportResult("errors")
    If RowCount(Errors) > 0 Then FirstFinding = Errors(1, 3) & " " & Errors(1, 1) & " line " & Errors(1, 2)
End Function

Private Sub WriteDataset(ByVal RunId As String, ByVal Started As Date, ByVal FileNames As Variant, _
                         ByVal Settings As Collection, ByVal ControlRows As Long)
    'Import and Reconciliation from the accepted dataset.
    WriteTable "Import_Lineage", Lineage(RunId, Started, FileNames, Settings, ControlRows)
    WriteTable "Import_Counts", PREPAY_DatasetResult("counts")
    WriteTable "Import_Outcomes", PREPAY_DatasetResult("outcomes")
    WriteTable "Reconciliation_Totals", PREPAY_DatasetResult("totals")
    WriteTable "Reconciliation_Controls", PREPAY_DatasetResult("comparisons")
End Sub

Private Function Lineage(ByVal RunId As String, ByVal Started As Date, ByVal FileNames As Variant, _
                         ByVal Settings As Collection, ByVal ControlRows As Long) As Variant
    'The lineage items of the data contract that are not in Import_Counts.
    Dim Warnings As Variant, Code As Variant, I As Long, Count As Long, Out() As Variant, N As Long
    ReDim Out(1 To 13 + UBound(SettingCodes()) + 1, 1 To 2)    '13 fixed items and the settings
    AddItem Out, N, "run_id", RunId
    AddItem Out, N, "import_timestamp", Stamp(Started)
    AddItem Out, N, "commit", NamedText("Build_Commit")
    AddItem Out, N, "source_loans.csv", CStr(FileNames(0))
    AddItem Out, N, "source_loan_panel.csv", CStr(FileNames(1))
    AddItem Out, N, "source_market_rates.csv", CStr(FileNames(2))
    For Each Code In SettingCodes()
        AddItem Out, N, CStr(Code), Settings.Item(CStr(Code))
    Next Code
    AddItem Out, N, "control_total_rows", CStr(ControlRows)
    Warnings = PREPAY_DatasetResult("warnings")
    For Each Code In Array("W01", "W02", "W03", "W04", "W05", "W06")
        Count = 0
        For I = 1 To RowCount(Warnings)
            If Warnings(I, 3) = Code Then Count = Count + 1
        Next I
        AddItem Out, N, "warnings_" & Code, CStr(Count)
    Next Code
    Lineage = Out
End Function

Private Sub AddItem(ByRef Out() As Variant, ByRef N As Long, ByVal Item As String, ByVal Value As String)
    N = N + 1
    Out(N, 1) = Item
    Out(N, 2) = Value
End Sub

Private Sub WriteTable(ByVal Name As String, ByVal Data As Variant)
    'Replace the rows under the header of table Name with Data, a 1-based
    '(n x width) array or Empty, written as text.
    Dim Header As Range, Width As Long, Last As Long, Body As Range
    Set Header = NamedRange(Name)
    Width = HeaderWidth(Header)
    Last = LastRow(Header, Width)
    If Last > Header.Row Then Header.Offset(1, 0).Resize(Last - Header.Row, Width).ClearContents
    If IsEmpty(Data) Then Exit Sub
    If UBound(Data, 2) <> Width Then
        Err.Raise vbObjectError + ERR_SETUP, SOURCE, Name & " has " & Width & " columns, not " & UBound(Data, 2)
    End If
    Set Body = Header.Offset(1, 0).Resize(UBound(Data, 1), Width)
    Body.NumberFormat = "@"
    Body.Value = Data
End Sub

Private Sub MarkResultsStale(ByVal RunId As String, ByVal Started As Date)
    Dim Sheet As Variant
    For Each Sheet In Array("Calibration", "Backtest", "CashFlows", "EVE", "Gap", "Measures")
        SetStatus CStr(Sheet), "STALE", RunId, Started
    Next Sheet
End Sub

Private Sub SetStatus(ByVal Sheet As String, ByVal State As String, ByVal RunId As String, ByVal Started As Date)
    SetText NamedRange(Sheet & "_Status"), StatusText(State, RunId, Started)
End Sub

Private Sub SetRun(ByVal State As String, ByVal RunId As String, ByVal Started As Date)
    SetText NamedRange("Run_Status"), StatusText(State, RunId, Started)
    SetText NamedRange("Run_ID"), RunId
    SetText NamedRange("Run_Operation"), OPERATION
    SetText NamedRange("Run_Timestamp"), Stamp(Started)
    SetText NamedRange("Run_Commit"), NamedText("Build_Commit")
End Sub

Private Sub RecordFailure(ByVal RunId As String, ByVal Started As Date)
    'After a VBA error: Findings cleared, results stale, the run failed; the
    'dataset areas are FAILED when this run's import was accepted, since they
    'no longer match the accepted dataset. A second error here leaves the
    'remaining steps undone.
    On Error Resume Next
    WriteTable "Findings_Rows", Empty
    WriteTable "Findings_Summary", Empty
    SetStatus "Findings", "FAILED", RunId, Started
    If PREPAY_DatasetRunId() = RunId Then
        SetStatus "Import", "FAILED", RunId, Started
        SetStatus "Reconciliation", "FAILED", RunId, Started
    End If
    MarkResultsStale RunId, Started
    SetRun "FAILED", RunId, Started
End Sub

Private Function AppendLog(ByVal RunId As String, ByVal Started As Date, ByVal Outcome As String, _
                           ByVal Restored As Boolean, ByVal FirstError As String) As String
    'One Log_Runs row per operation; never edits an earlier row. Returns ""
    'or the error that stopped the write, reported apart from the outcome.
    Dim Header As Range, Values(1 To 1, 1 To 8) As Variant, Target As Range
    On Error GoTo Unwritten
    Set Header = NamedRange("Log_Runs")
    Values(1, 1) = RunId
    Values(1, 2) = OPERATION
    Values(1, 3) = Stamp(Started)
    Values(1, 4) = Stamp(Now)
    Values(1, 5) = Outcome
    Values(1, 6) = ""
    Values(1, 7) = IIf(Restored, "Y", "N")
    Values(1, 8) = FirstError
    Set Target = Header.Offset(LastRow(Header, 8) - Header.Row + 1, 0).Resize(1, 8)
    Target.NumberFormat = "@"
    Target.Value = Values
    Exit Function
Unwritten:
    AppendLog = "VBA error " & Err.Number & ": " & Err.Description
End Function

'------------------------------------------------------------------------------
' Run IDs, status text and time stamps
'------------------------------------------------------------------------------

Private Function NewRunId(ByVal Started As Date) As String
    'IMPORT-yyyymmdd-hhnnss in host local time; -2, -3, ... when the Log
    'already has that ID (W13).
    Dim Prefix As String, Header As Range, Last As Long, Ids As Collection, I As Long, N As Long, Id As String
    Prefix = OPERATION & "-" & Replace(Stamp(Started), "-", "")
    Prefix = Replace(Replace(Prefix, " ", "-"), ":", "")
    Set Header = NamedRange("Log_Runs")
    Last = LastRow(Header, 8)
    Set Ids = New Collection
    On Error Resume Next
    For I = Header.Row + 1 To Last
        Id = CStr(Header.Worksheet.Cells(I, Header.Column).Value)
        If Left$(Id, Len(Prefix)) = Prefix Then Ids.Add Id, Id
    Next I
    On Error GoTo 0
    Id = Prefix
    N = 1
    Do While Contains(Ids, Id)
        N = N + 1
        Id = Prefix & "-" & N
    Loop
    NewRunId = Id
End Function

Private Function Contains(ByVal Items As Collection, ByVal Key As String) As Boolean
    Dim V As Variant
    On Error GoTo Absent
    V = Items.Item(Key)
    Contains = True
Absent:
End Function

Private Function StatusText(ByVal State As String, ByVal RunId As String, ByVal Started As Date) As String
    StatusText = State & ": " & RunId & ", " & Stamp(Started)
End Function

Private Function Stamp(ByVal T As Date) As String
    'yyyy-mm-dd hh:nn:ss, independent of the host date and time separators.
    Stamp = Format$(Year(T), "0000") & "-" & Format$(Month(T), "00") & "-" & Format$(Day(T), "00") & " " & _
            Format$(Hour(T), "00") & ":" & Format$(Minute(T), "00") & ":" & _
            Format$(Second(T), "00")
End Function

'------------------------------------------------------------------------------
' Names, ranges and Excel state
'------------------------------------------------------------------------------

Private Sub CheckNames()
    'Every name the operation uses exists and is on its sheet, before any
    'calculation (workbook contract, defined names).
    Dim Pairs As Variant, I As Long, Names As Variant, Name As Variant, Target As Range
    Pairs = Array( _
        "shSettings", "cfg_data_window_start cfg_data_window_end cfg_segment_list cfg_currency_allowlist " & _
                      "cfg_refi_curve_series cfg_timely_reporting_attested", _
        "shControls", "Controls_Totals", _
        "shImport", "Import_Status Import_Lineage Import_Counts Import_Outcomes", _
        "shFindings", "Findings_Status Findings_Summary Findings_Rows", _
        "shReconciliation", "Reconciliation_Status Reconciliation_Totals Reconciliation_Controls", _
        "shCalibration", "Calibration_Status", "shBacktest", "Backtest_Status", "shCashFlows", "CashFlows_Status", _
        "shEVE", "EVE_Status", "shGap", "Gap_Status", "shMeasures", "Measures_Status", _
        "shLog", "Log_Runs Run_Status Run_ID Run_Operation Run_Timestamp Run_Commit", _
        "shReadme", "Build_Commit")
    For I = 0 To UBound(Pairs) Step 2
        Names = Split(Pairs(I + 1), " ")
        For Each Name In Names
            Set Target = Nothing
            On Error Resume Next
            Set Target = ThisWorkbook.Names(CStr(Name)).RefersToRange
            On Error GoTo 0
            If Target Is Nothing Then
                Err.Raise vbObjectError + ERR_SETUP, SOURCE, "Name " & Name & " is missing"
            End If
            If Target.Worksheet.CodeName <> Pairs(I) Then
                Err.Raise vbObjectError + ERR_SETUP, SOURCE, "Name " & Name & " is not on " & Pairs(I)
            End If
        Next Name
    Next I
End Sub

Private Function NamedRange(ByVal Name As String) As Range
    Set NamedRange = ThisWorkbook.Names(Name).RefersToRange
End Function

Private Function NamedText(ByVal Name As String) As String
    NamedText = CellText(NamedRange(Name), False)
End Function

Private Sub SetText(ByVal Cell As Range, ByVal Text As String)
    Cell.NumberFormat = "@"
    Cell.Value = Text
End Sub

Private Function HeaderWidth(ByVal Header As Range) As Long
    'The number of header cells, from the named cell to the first empty one.
    Do While Len(CStr(Header.Offset(0, HeaderWidth).Value)) > 0
        HeaderWidth = HeaderWidth + 1
    Loop
End Function

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

Private Function RowCount(ByVal Table As Variant) As Long
    If Not IsEmpty(Table) Then RowCount = UBound(Table, 1)
End Function

Private Function MinOf(ByVal A As Long, ByVal B As Long) As Long
    If A < B Then MinOf = A Else MinOf = B
End Function

Private Function SaveState() As Variant
    SaveState = Array(Application.Calculation, Application.EnableEvents, Application.ScreenUpdating, _
                      Application.DisplayAlerts)
End Function

Private Sub QuietState()
    Application.ScreenUpdating = False
    Application.EnableEvents = False
    Application.DisplayAlerts = False
    Application.Calculation = XL_MANUAL
End Sub

Private Function RestoreState(ByVal State As Variant) As Boolean
    'Restore and confirm the saved settings; False when any differs.
    On Error GoTo Unrestored
    Application.Calculation = State(0)
    Application.EnableEvents = State(1)
    Application.ScreenUpdating = State(2)
    Application.DisplayAlerts = State(3)
    RestoreState = (Application.Calculation = State(0) And Application.EnableEvents = State(1) And _
                    Application.ScreenUpdating = State(2) And Application.DisplayAlerts = State(3))
Unrestored:
End Function
