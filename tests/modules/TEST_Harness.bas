Attribute VB_Name = "TEST_Harness"
'==============================================================================
' MODULE: TEST_Harness
'------------------------------------------------------------------------------
' PURPOSE
'   Test harness of the test build (docs/WORKBOOK_CONTRACT.md, W8): a case
'   registry, a runner with the outcomes NOT RUN, ERROR, FAIL and PASS, and
'   the failure-injection path of docs/EXCEL_EVIDENCE.md, stage 4.
'
' ENTRY POINTS
'   TEST_RunAll        Runs every case, writes the Tests sheet and shows the
'                      summary line in a message box.
'   TEST_RunInjected   The same with an injected failure in INJECTED_CASE.
'   TEST_Run           Function behind both; returns the summary line.
'   TEST_RunCases      Pure runner; returns the case table without touching
'                      the workbook.
'
' OUTCOMES
'   PASS     the case ran and every check held;
'   FAIL     the case ran and at least one check failed;
'   ERROR    the case raised a VBA error;
'   NOT RUN  the case was not reached because the run stopped.
'
' STATE OWNERSHIP
'   Writes only the Tests_Cases table and Tests_Status. Saves Calculation,
'   EnableEvents, ScreenUpdating and DisplayAlerts and restores them on
'   every exit path.
'==============================================================================

Option Explicit

Public Const INJECTED_CASE As String = "RATE-CONV-02"

Private Const COLS As Long = 4    'case_id, outcome, injected, message

Private mFailures As String
Private mInjectActive As Boolean

'------------------------------------------------------------------------------
' Registry
'------------------------------------------------------------------------------

Private Function CaseIds() As Variant
    'Every case of the harness, in run order. IDs without a UNIT- prefix are
    'cases of docs/methodology/TEST_CASES.md.
    CaseIds = Array("UNIT-HARNESS-01", "RATE-CONV-01", "RATE-CONV-02", "UNIT-RATE-BOUNDS-01")
End Function

Private Sub RunCase(ByVal CaseId As String)
    Select Case CaseId
        Case "UNIT-HARNESS-01": CaseHarness
        Case "RATE-CONV-01": TEST_Rates.TEST_RateConv01
        Case "RATE-CONV-02": TEST_Rates.TEST_RateConv02
        Case "UNIT-RATE-BOUNDS-01": TEST_Rates.TEST_RateBounds01
        Case Else: Err.Raise vbObjectError + 1, "TEST_Harness", "Case not in the registry: " & CaseId
    End Select
End Sub

'------------------------------------------------------------------------------
' Entry points
'------------------------------------------------------------------------------

Public Sub TEST_RunAll()
    Report TEST_Run("")
End Sub

Public Sub TEST_RunInjected()
    Report TEST_Run(INJECTED_CASE)
End Sub

Public Function TEST_Run(Optional ByVal InjectCase As String = "") As String
    'Run every case, write the Tests sheet and return the summary line.
    Dim Calc As Long, Events As Boolean, Screen As Boolean, Alerts As Boolean
    Dim Results As Variant, Summary As String
    Calc = Application.Calculation
    Events = Application.EnableEvents
    Screen = Application.ScreenUpdating
    Alerts = Application.DisplayAlerts
    On Error GoTo Failed
    Application.ScreenUpdating = False
    Results = TEST_RunCases(InjectCase)
    Summary = SummaryLine(Results, InjectCase)
    WriteResults Results, "CURRENT " & Summary & " at " & Format$(Now, "yyyy-mm-dd hh:nn:ss")
    TEST_Run = Summary
Restore:
    Application.Calculation = Calc
    Application.EnableEvents = Events
    Application.ScreenUpdating = Screen
    Application.DisplayAlerts = Alerts
    Exit Function
Failed:
    TEST_Run = "FAILED harness error " & Err.Number & ": " & Err.Description
    MarkFailed TEST_Run
    Resume Restore
End Function

Public Function TEST_RunCases(Optional ByVal InjectCase As String = "") As Variant
    'Run every case; return a 1-based (cases x 4) array of case_id, outcome,
    'injected flag and message. Cases after a harness failure stay NOT RUN.
    Dim Ids As Variant, Out() As Variant, I As Long, N As Long
    Ids = CaseIds()
    N = UBound(Ids) - LBound(Ids) + 1
    ReDim Out(1 To N, 1 To COLS)
    For I = 1 To N
        Out(I, 1) = Ids(LBound(Ids) + I - 1)
        Out(I, 2) = "NOT RUN"
        Out(I, 3) = (Out(I, 1) = InjectCase)
        Out(I, 4) = ""
    Next I
    For I = 1 To N
        RunOne Out, I
    Next I
    TEST_RunCases = Out
End Function

'------------------------------------------------------------------------------
' Checks used by the case modules
'------------------------------------------------------------------------------

Public Sub TEST_CheckNear(ByVal Label As String, ByVal Actual As Double, ByVal Expected As Double, _
                          ByVal Tolerance As Double, Optional ByVal Relative As Boolean = False)
    'Abs: |actual - expected| <= tol. Rel: <= tol x max(1, |expected|)
    '(docs/methodology/TEST_CASES.md, tolerances). An injected case compares
    'with expected + 1, so the real comparison path must report the failure.
    Dim Limit As Double
    If mInjectActive Then Expected = Expected + 1#
    Limit = Tolerance
    If Relative Then
        If Abs(Expected) > 1# Then Limit = Tolerance * Abs(Expected)
    End If
    If Not (Abs(Actual - Expected) <= Limit) Then
        AddFailure Label & ": got " & CStr(Actual) & ", expected " & CStr(Expected) & _
                   " within " & CStr(Limit)
    End If
End Sub

Public Sub TEST_CheckTrue(ByVal Label As String, ByVal Condition As Boolean)
    If mInjectActive Then Condition = Not Condition
    If Not Condition Then AddFailure Label
End Sub

'------------------------------------------------------------------------------
' Internals
'------------------------------------------------------------------------------

Private Sub RunOne(ByRef Out() As Variant, ByVal Row As Long)
    mFailures = ""
    mInjectActive = CBool(Out(Row, 3))
    On Error GoTo Errored
    RunCase CStr(Out(Row, 1))
    On Error GoTo 0
    mInjectActive = False
    If Len(mFailures) = 0 Then
        Out(Row, 2) = "PASS"
    Else
        Out(Row, 2) = "FAIL"
        Out(Row, 4) = mFailures
    End If
    If Out(Row, 3) Then Out(Row, 4) = "INJECTED: " & Out(Row, 4)
    Exit Sub
Errored:
    mInjectActive = False
    Out(Row, 2) = "ERROR"
    Out(Row, 4) = "VBA error " & Err.Number & ": " & Err.Description
End Sub

Private Sub Report(ByVal Summary As String)
    'Show the outcome to the operator; a harness failure is never silent.
    If Left$(Summary, 6) = "FAILED" Then
        MsgBox Summary, vbCritical, "TEST_Harness"
    Else
        MsgBox Summary, vbInformation, "TEST_Harness"
    End If
End Sub

Private Sub MarkFailed(ByVal Text As String)
    'Replace an earlier CURRENT status where the sheet can still be written;
    'the status cell itself may be what failed, so ignore a second error here.
    On Error Resume Next
    ThisWorkbook.Names("Tests_Status").RefersToRange.Value = Text
End Sub

Private Sub AddFailure(ByVal Text As String)
    If Len(mFailures) > 0 Then mFailures = mFailures & "; "
    mFailures = mFailures & Text
End Sub

Private Sub CaseHarness()
    'The checks must detect a mismatch: run one failing check in isolation and
    'confirm it was recorded, then restore the state of the real case.
    Dim Saved As String, Detected As Boolean, Inject As Boolean
    Saved = mFailures
    Inject = mInjectActive
    mInjectActive = False
    mFailures = ""
    TEST_CheckNear "probe", 1#, 2#, 0.5
    Detected = (Len(mFailures) > 0)
    mFailures = Saved
    mInjectActive = Inject
    TEST_CheckTrue "a failing check is recorded", Detected
    TEST_CheckNear "an equal value passes", 0.25, 0.25, 0#
End Sub

Private Function SummaryLine(ByVal Results As Variant, ByVal InjectCase As String) As String
    Dim I As Long, Passed As Long, Total As Long
    Total = UBound(Results, 1)
    For I = 1 To Total
        If Results(I, 2) = "PASS" Then Passed = Passed + 1
    Next I
    SummaryLine = Passed & " of " & Total & " PASS"
    If Len(InjectCase) > 0 Then SummaryLine = SummaryLine & " (injected failure in " & InjectCase & ")"
End Function

Private Sub WriteResults(ByVal Results As Variant, ByVal Status As String)
    Dim Header As Range, LastRow As Long
    Set Header = ThisWorkbook.Names("Tests_Cases").RefersToRange
    With Header.Worksheet
        LastRow = .Cells(.Rows.Count, Header.Column).End(xlUp).Row
        If LastRow > Header.Row Then
            .Range(Header.Offset(1, 0), .Cells(LastRow, Header.Column + COLS - 1)).ClearContents
        End If
    End With
    Header.Offset(1, 0).Resize(UBound(Results, 1), COLS).Value = Results
    ThisWorkbook.Names("Tests_Status").RefersToRange.Value = Status
End Sub
