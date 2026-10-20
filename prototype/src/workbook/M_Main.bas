Attribute VB_Name = "M_Main"
'==============================================================================
' MODULE: M_Main
'------------------------------------------------------------------------------
' PURPOSE
'   Provide the macros behind the sheet buttons, run each operation with
'   Excel prepared for speed, put Excel back exactly as it was, and report
'   the outcome to the user.
'
' PUBLIC SURFACE
'   RunModel: validate the inputs, run the model, write every output.
'   ValidateInputs: validate only; findings go to Checks.
'   ClearOutputs: empty the model outputs.
'   RunCalibration: fit the S-curves to History (Calibration sheet).
'   ApplyCalibration: copy the converged fits to Segments.
'   RunTests: run the reference tests (needs the TEST_PPM module of a
'   development workbook).
'   RunModel_Silent: RunModel for automation; returns the status line
'   and raises errors instead of showing them.
'
' DEPENDENCIES
'   CORE_Engine, CORE_Calibrate, CORE_Util, CORE_Config; TEST_PPM through
'   Application.Run, so that a production workbook compiles without it.
'
' STATE OWNERSHIP
'   Each operation captures calculation mode, events and screen updating,
'   changes them for the run and restores the captured values on success
'   and on failure. Owns gSilent (messages to the Immediate window and
'   errors raised to the caller) and the re-entry flag mRunning.
'
' ERROR POLICY
'   The primary error is copied before cleanup. Each setting is restored
'   by its own helper, so one failed restoration does not stop the
'   others, and a cleanup failure is reported separately from the primary
'   error. Input problems are not VBA errors: they are on Checks.
'
' KNOWN DEVIATION
'   Standard module in src/workbook, as M_Main in K-SACCR.
'
' COMPATIBILITY
'   Excel VBA; no references beyond the defaults.
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
    'The macros must stay visible to the sheet buttons: not private.
    Option Explicit

'------------------------------------------------------------------------------
' MODULE CONSTANTS
'------------------------------------------------------------------------------
        Private Const OP_RUN        As Long = 1    'Run the model
        Private Const OP_VALIDATE   As Long = 2    'Validate only
        Private Const OP_CLEAR      As Long = 3    'Clear the outputs
        Private Const OP_CALIBRATE  As Long = 4    'Fit the S-curves
        Private Const OP_APPLY      As Long = 5    'Copy the fits to Segments
        Private Const OP_TESTS      As Long = 6    'Reference tests

'------------------------------------------------------------------------------
' MODULE STATE
'------------------------------------------------------------------------------
        Public gSilent      As Boolean    'Silent mode for automation and tests
        Public gLastMessage As String     'The last message shown or printed
        Private mRunning    As Boolean    'True while an operation is in progress


'
'------------------------------------------------------------------------------
'
'                                BUTTON MACROS
'
'------------------------------------------------------------------------------
'

Public Sub RunModel()
'
'==============================================================================
'                                   RunModel
'------------------------------------------------------------------------------
' PURPOSE
'   Run the model and write every output sheet (Run model button).
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        ExecuteOperation OP_RUN

End Sub


Public Sub ValidateInputs()
'
'==============================================================================
'                                ValidateInputs
'------------------------------------------------------------------------------
' PURPOSE
'   Validate the inputs and write the findings to Checks only.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        ExecuteOperation OP_VALIDATE

End Sub


Public Sub ClearOutputs()
'
'==============================================================================
'                                 ClearOutputs
'------------------------------------------------------------------------------
' PURPOSE
'   Clear the model output sheets.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        ExecuteOperation OP_CLEAR

End Sub


Public Sub RunCalibration()
'
'==============================================================================
'                                RunCalibration
'------------------------------------------------------------------------------
' PURPOSE
'   Fit the S-curve of every segment with History observations.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        ExecuteOperation OP_CALIBRATE

End Sub


Public Sub ApplyCalibration()
'
'==============================================================================
'                               ApplyCalibration
'------------------------------------------------------------------------------
' PURPOSE
'   Copy the converged fits of Calibration to Segments, after asking.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        If Not gSilent Then
            If MsgBox("Overwrite CPR min, CPR max, slope and midpoint on Segments with the converged fits of " & _
                      "Calibration?", vbQuestion + vbOKCancel, PRODUCT_NAME) <> vbOK Then Exit Sub
        End If
        ExecuteOperation OP_APPLY

End Sub


Public Sub RunTests()
'
'==============================================================================
'                                   RunTests
'------------------------------------------------------------------------------
' PURPOSE
'   Run the reference tests of the Tests sheet.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        ExecuteOperation OP_TESTS

End Sub


Public Function RunModel_Silent() As String
'
'==============================================================================
'                               RunModel_Silent
'------------------------------------------------------------------------------
' PURPOSE
'   RunModel without message boxes, for automation.
'
' RETURNS
'   The status line of the run.
'
' ERROR POLICY
'   Raises the primary error to the caller.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim SavedSilent    As Boolean    'gSilent before the call

        SavedSilent = gSilent
        gSilent = True
        On Error GoTo Failed
        RunModel_Silent = ExecuteOperation(OP_RUN)
        gSilent = SavedSilent
        Exit Function
Failed:
        gSilent = SavedSilent
        Err.Raise Err.Number, Err.Source, Err.Description

End Function


'
'------------------------------------------------------------------------------
'
'                                  OPERATION
'
'------------------------------------------------------------------------------
'

Private Function ExecuteOperation( _
    ByVal Operation As Long) _
    As String
'
'==============================================================================
'                               ExecuteOperation
'------------------------------------------------------------------------------
' PURPOSE
'   Run one operation with Excel prepared for speed, restore Excel, then
'   report the outcome.
'
' RETURNS
'   The status line of the operation; empty when it failed.
'
' STATE OWNERSHIP
'   Captures calculation mode, events and screen updating before changing
'   them and restores the captured values on every path. Clears mRunning
'   before reporting.
'
' ERROR POLICY
'   K-SACCR pattern (M_Main.ExecuteOperation): primary error copied before
'   cleanup and reported (or raised in silent mode) after it; a cleanup
'   failure is reported with it, or on its own.
'
' UPDATED
'   2026-10-20
'==============================================================================
'

'------------------------------------------------------------------------------
' DECLARE
'------------------------------------------------------------------------------
    Dim SavedCalculation   As XlCalculation    'Calculation mode before the operation
    Dim SavedEvents        As Boolean          'EnableEvents before the operation
    Dim SavedScreen        As Boolean          'ScreenUpdating before the operation
    Dim StateCaptured      As Boolean          'True once all three were read
    Dim Completed          As Boolean          'The operation completed
    Dim StatusLine         As String           'Outcome line
    Dim ErrorNumber        As Long             'Primary error number; 0 for none
    Dim ErrorSource        As String           'Primary error source
    Dim ErrorDescription   As String           'Primary error description
    Dim CleanupDetails     As String           'Restoration failures

'------------------------------------------------------------------------------
' REFUSE RE-ENTRY
'------------------------------------------------------------------------------
        If mRunning Then
            ReportFailure ERR_RUN_ACTIVE, "M_Main.ExecuteOperation", "An operation is already running.", ""
            Exit Function
        End If
        mRunning = True
        On Error GoTo Failed

'------------------------------------------------------------------------------
' CAPTURE AND PREPARE EXCEL
'------------------------------------------------------------------------------
        SavedCalculation = Application.Calculation
        SavedEvents = Application.EnableEvents
        SavedScreen = Application.ScreenUpdating
        StateCaptured = True
        Application.ScreenUpdating = False
        Application.EnableEvents = False
        Application.Calculation = xlCalculationManual

'------------------------------------------------------------------------------
' BRING FORMULA INPUTS UP TO DATE AND RUN
'------------------------------------------------------------------------------
    'A formula input whose precedents changed would otherwise still hold
    'its old value in manual calculation.
        If Operation <> OP_CLEAR Then
            Application.Calculate
            If RecalcPending() Then
                Err.Raise ERR_RECALC_PENDING, "M_Main.ExecuteOperation", _
                          "Excel did not finish recalculating the inputs, so the operation was not started."
            End If
        End If
        Select Case Operation
            Case OP_RUN
                Completed = CORE_Engine.Calculate(True, StatusLine)
            Case OP_VALIDATE
                Completed = CORE_Engine.Calculate(False, StatusLine)
            Case OP_CLEAR
                StatusLine = "Outputs cleared " & Format$(Now, "yyyy-mm-dd hh:mm:ss")
                CORE_Engine.ClearModelOutputs StatusLine
                Completed = True
            Case OP_CALIBRATE
                CORE_Calibrate.Calibrate StatusLine
                Completed = True
            Case OP_APPLY
                CORE_Calibrate.ApplySegmentFits StatusLine
                Completed = True
            Case OP_TESTS
                StatusLine = RunTestModule()
                Completed = True
        End Select

'------------------------------------------------------------------------------
' RESTORE EXCEL AND REPORT
'------------------------------------------------------------------------------
CleanUp:
        On Error GoTo 0
        If StateCaptured Then CleanupDetails = RestoreSettings(SavedCalculation, SavedEvents, SavedScreen)
        mRunning = False
        If ErrorNumber <> 0 Then
            ReportFailure ErrorNumber, ErrorSource, ErrorDescription, CleanupDetails
        Else
            If Len(CleanupDetails) > 0 Then
                ReportFailure ERR_CLEANUP_FAILED, "M_Main.ExecuteOperation", _
                              "The operation completed but Excel settings were not all restored.", CleanupDetails
            Else
                ReportOutcome Completed, StatusLine
            End If
            ExecuteOperation = StatusLine
        End If
        Exit Function

'------------------------------------------------------------------------------
' HANDLE ERROR
'------------------------------------------------------------------------------
Failed:
        ErrorNumber = Err.Number
        ErrorSource = Err.Source
        ErrorDescription = Err.Description
        Resume CleanUp

End Function


Private Function RecalcPending() As Boolean
'
'==============================================================================
'                                RecalcPending
'------------------------------------------------------------------------------
' PURPOSE
'   True when Excel has not finished recalculating.
'
' ERROR POLICY
'   A host without Application.CalculationState (the headless test host,
'   tools/run_vba_headless.py) counts as finished; Excel always has it.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        On Error GoTo Unsupported
        RecalcPending = (Application.CalculationState <> xlDone)
        Exit Function
Unsupported:
        RecalcPending = False

End Function


Private Function RunTestModule() As String
'
'==============================================================================
'                                RunTestModule
'------------------------------------------------------------------------------
' PURPOSE
'   Call TEST_PPM.RunReferenceTests by name, so that a production
'   workbook without the test module still compiles.
'
' ERROR POLICY
'   Raises ERR_TESTS_MISSING when the module is missing or the tests
'   fail, with the original error text appended.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        On Error GoTo Missing
        RunTestModule = Application.Run("TEST_PPM.RunReferenceTests")
        Exit Function
Missing:
        Err.Raise ERR_TESTS_MISSING, "M_Main.RunTestModule", _
                  "The tests did not complete. If TEST_PPM is not in the workbook, import " & _
                  "tests/modules/TEST_PPM.bas (development workbook). Detail: " & Err.Description

End Function


'
'------------------------------------------------------------------------------
'
'                                  REPORTING
'
'------------------------------------------------------------------------------
'

Private Sub ReportOutcome( _
    ByVal Completed As Boolean, _
    ByVal StatusLine As String)
'
'==============================================================================
'                                ReportOutcome
'------------------------------------------------------------------------------
' PURPOSE
'   Tell the user how the operation ended.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        gLastMessage = StatusLine
        If gSilent Then
            Debug.Print PRODUCT_NAME & ": " & StatusLine
        ElseIf Completed Then
            MsgBox StatusLine, vbInformation, PRODUCT_NAME
        Else
            MsgBox StatusLine, vbExclamation, PRODUCT_NAME
        End If

End Sub


Private Sub ReportFailure( _
    ByVal ErrorNumber As Long, _
    ByVal ErrorSource As String, _
    ByVal ErrorDescription As String, _
    ByVal CleanupDetails As String)
'
'==============================================================================
'                                ReportFailure
'------------------------------------------------------------------------------
' PURPOSE
'   Show (or raise, in silent mode) a failed operation.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Message        As String    'Text shown

        Message = ErrorDescription & vbCrLf & "Source: " & ErrorSource
        If Len(CleanupDetails) > 0 Then Message = Message & vbCrLf & "Excel settings not restored: " & CleanupDetails
        gLastMessage = Message
        If gSilent Then
            Err.Raise ErrorNumber, ErrorSource, Message
        Else
            MsgBox Message, vbCritical, PRODUCT_NAME
        End If

End Sub


'
'------------------------------------------------------------------------------
'
'                               EXCEL SETTINGS
'
'------------------------------------------------------------------------------
'

Private Function RestoreSettings( _
    ByVal SavedCalculation As XlCalculation, _
    ByVal SavedEvents As Boolean, _
    ByVal SavedScreen As Boolean) _
    As String
'
'==============================================================================
'                               RestoreSettings
'------------------------------------------------------------------------------
' PURPOSE
'   Restore the three captured settings, each independently.
'
' RETURNS
'   The failures, separated by "; "; empty when all three were restored.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Details        As String    'Collected failures

        Details = AppendDetail(Details, RestoreCalculation(SavedCalculation))
        Details = AppendDetail(Details, RestoreEvents(SavedEvents))
        Details = AppendDetail(Details, RestoreScreenUpdating(SavedScreen))
        RestoreSettings = Details

End Function


Private Function RestoreCalculation( _
    ByVal SavedValue As XlCalculation) _
    As String
'
'==============================================================================
'                              RestoreCalculation
'------------------------------------------------------------------------------
' PURPOSE
'   Set the calculation mode back and check that it took effect.
'
' RETURNS
'   Empty on success; otherwise what failed.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        On Error GoTo Failed
        Application.Calculation = SavedValue
        If Application.Calculation <> SavedValue Then RestoreCalculation = "Calculation: restored value does not match"
        Exit Function
Failed:
        RestoreCalculation = "Calculation: " & CStr(Err.Number) & " / " & Err.Description

End Function


Private Function RestoreEvents( _
    ByVal SavedValue As Boolean) _
    As String
'
'==============================================================================
'                                RestoreEvents
'------------------------------------------------------------------------------
' PURPOSE
'   Set EnableEvents back and check that it took effect.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        On Error GoTo Failed
        Application.EnableEvents = SavedValue
        If Application.EnableEvents <> SavedValue Then RestoreEvents = "EnableEvents: restored value does not match"
        Exit Function
Failed:
        RestoreEvents = "EnableEvents: " & CStr(Err.Number) & " / " & Err.Description

End Function


Private Function RestoreScreenUpdating( _
    ByVal SavedValue As Boolean) _
    As String
'
'==============================================================================
'                            RestoreScreenUpdating
'------------------------------------------------------------------------------
' PURPOSE
'   Set ScreenUpdating back.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        On Error GoTo Failed
        Application.ScreenUpdating = SavedValue
        Exit Function
Failed:
        RestoreScreenUpdating = "ScreenUpdating: " & CStr(Err.Number) & " / " & Err.Description

End Function
