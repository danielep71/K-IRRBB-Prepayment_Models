Attribute VB_Name = "TEST_PPM"
'==============================================================================
' MODULE: TEST_PPM
'------------------------------------------------------------------------------
' PURPOSE
'   Reference tests: run the model and the calibration on the
'   illustrative data, read each output named on the Tests sheet by sheet,
'   key (first column of its table) and column header, and compare it with
'   the expected value computed independently by tools/reference_model.py.
'
' PUBLIC SURFACE
'   RunReferenceTests: called by M_Main.RunTests through Application.Run;
'   returns the summary line.
'
' DEPENDENCIES
'   CORE_Engine, CORE_Calibrate, CORE_Util, CORE_Config.
'
' STATE OWNERSHIP
'   Rewrites every output sheet and the Actual, difference and Result
'   columns of Tests, and recalculates Tests so that the worksheet-function
'   unit tests below the reference tests are evaluated. Run it on the illustrative data only: the expected
'   values belong to the template's inputs.
'
' ERROR POLICY
'   An output that cannot be found is a FAIL, not a VBA error. A broken
'   workbook raises from CORE_Util.
'
' NOTE
'   Not Option Private Module, unlike the K-SACCR test modules: M_Main
'   reaches it with Application.Run so that production builds can omit it.
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
    Option Explicit

'------------------------------------------------------------------------------
' MODULE CONSTANTS
'------------------------------------------------------------------------------
    'Columns of the reference-test table on Tests.
        Private Const TC_SHEET      As Long = 4
        Private Const TC_KEY        As Long = 5
        Private Const TC_COLUMN     As Long = 6
        Private Const TC_EXPECTED   As Long = 7
        Private Const TC_ACTUAL     As Long = 8
        Private Const TC_TOL        As Long = 11
        Private Const MAX_HEADER    As Long = 60    'Header cells scanned for a column


'
'------------------------------------------------------------------------------
'
'                                 TEST RUNNER
'
'------------------------------------------------------------------------------
'

Public Function RunReferenceTests() As String
'
'==============================================================================
'                              RunReferenceTests
'------------------------------------------------------------------------------
' PURPOSE
'   Run the model and the calibration, evaluate every reference test and
'   write the outcome to Tests.
'
' RETURNS
'   "Tests <time>: <passed> of <total> PASS".
'
' REFERENCE
'   PASS when |actual - expected| <= tolerance x max(|expected|, 1).
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Sheet          As Worksheet    'Tests
    Dim FirstRow       As Long         'First test row
    Dim LastRow        As Long         'Last test row
    Dim Block          As Variant      'Test definitions
    Dim Outcome()      As Variant      'Actual, abs. diff, rel. diff, (tolerance), result
    Dim r              As Long         'Test
    Dim Actual         As Variant      'Value read
    Dim Expected       As Double       'Expected value
    Dim Tolerance      As Double       'Relative tolerance
    Dim AbsDiff        As Double       'Absolute difference
    Dim Scale1         As Double       'max(|expected|, 1)
    Dim Passed         As Long         'Tests passed
    Dim Total          As Long         'Tests run
    Dim RunLine        As String       'Status of the model run
    Dim SummaryLine    As String       'Summary

        CORE_Engine.Calculate True, RunLine
        CORE_Calibrate.Calibrate SummaryLine
        Set Sheet = GetSheet(SH_TESTS)
        FirstRow = NamedCell(NM_TESTS).Row + 1
        LastRow = FirstRow - 1
        Do While Not IsBlankValue(Sheet.Cells(LastRow + 1, TableCol(1)).Value2)
            LastRow = LastRow + 1
        Loop
        If LastRow < FirstRow Then
            RunReferenceTests = "No reference test is defined."
            Exit Function
        End If
        Block = ReadTable(Sheet, FirstRow, LastRow, TS_NCOLS)
        Total = LastRow - FirstRow + 1
        ReDim Outcome(1 To Total, 1 To 5)
        For r = 1 To Total
            Actual = LookupOutput(CStr(Block(r, TC_SHEET)), CStr(Block(r, TC_KEY)), CStr(Block(r, TC_COLUMN)))
            Expected = CDbl(Block(r, TC_EXPECTED))
            Tolerance = CDbl(Block(r, TC_TOL))
            Outcome(r, 4) = Block(r, TC_TOL)
            If IsNumberValue(Actual) Then
                AbsDiff = Abs(CDbl(Actual) - Expected)
                Scale1 = Abs(Expected)
                If Scale1 < 1# Then Scale1 = 1#
                Outcome(r, 1) = Actual
                Outcome(r, 2) = AbsDiff
                If Abs(Expected) > 0# Then Outcome(r, 3) = AbsDiff / Abs(Expected) Else Outcome(r, 3) = AbsDiff
                If AbsDiff <= Tolerance * Scale1 Then
                    Outcome(r, 5) = "PASS"
                    Passed = Passed + 1
                Else
                    Outcome(r, 5) = "FAIL"
                End If
            Else
                Outcome(r, 1) = "not found"
                Outcome(r, 5) = "FAIL"
            End If
        Next r
        WriteTable Sheet, FirstRow, Outcome, Total, 5, TC_ACTUAL
        Sheet.Calculate
        SummaryLine = "Tests " & Format$(Now, "yyyy-mm-dd hh:mm:ss") & ": " & Passed & " of " & Total & " PASS | " & RunLine
        Sheet.Range(STATUS_CELL).Value = SummaryLine
        RunReferenceTests = SummaryLine

End Function


Private Function LookupOutput( _
    ByVal SheetName As String, _
    ByVal Key As String, _
    ByVal ColumnHeader As String) _
    As Variant
'
'==============================================================================
'                                 LookupOutput
'------------------------------------------------------------------------------
' PURPOSE
'   Find an output value by sheet, key in the first column of a table and
'   column header; the first table of the sheet that has both wins, and
'   within it the first matching header.
'
' RETURNS
'   The Value2 found, or Empty.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Tables         As Variant    'Header names of the sheet's tables
    Dim t              As Long       'Table
    Dim Sheet          As Worksheet  'Output sheet
    Dim Header         As Range      'Header cell of the table
    Dim c              As Long       'Column
    Dim Col            As Long       'Matching column; 0 if none
    Dim r              As Long       'Row

        Select Case SheetName
            Case SH_RESULTS: Tables = Array(NM_RESULTS, NM_SUMMARY, NM_SEGRES)
            Case SH_LOANCALC: Tables = Array(NM_LOANCALC)
            Case SH_GAP: Tables = Array(NM_GAP)
            Case SH_CASHFLOWS: Tables = Array(NM_CASHFLOWS)
            Case SH_CALIB: Tables = Array(NM_CALIB)
            Case SH_CURVES: Tables = Array(NM_CURVES)
            Case Else
                LookupOutput = Empty
                Exit Function
        End Select
        Set Sheet = GetSheet(SheetName)
        For t = 0 To UBound(Tables)
            Set Header = NamedCell(CStr(Tables(t)))
            Col = 0
            For c = 1 To MAX_HEADER
                If UCase$(Trim$(CStr(Sheet.Cells(Header.Row, TableCol(c)).Value2))) = UCase$(Trim$(ColumnHeader)) Then
                    Col = c
                    Exit For
                End If
            Next c
            If Col > 0 Then
                r = Header.Row + 1
                Do While Not IsBlankValue(Sheet.Cells(r, TableCol(1)).Value2)
                    If UCase$(Trim$(CStr(Sheet.Cells(r, TableCol(1)).Value2))) = UCase$(Trim$(Key)) Then
                        LookupOutput = Sheet.Cells(r, TableCol(Col)).Value2
                        Exit Function
                    End If
                    r = r + 1
                Loop
            End If
        Next t
        LookupOutput = Empty

End Function
