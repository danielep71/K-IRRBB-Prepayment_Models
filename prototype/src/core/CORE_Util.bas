Attribute VB_Name = "CORE_Util"
'==============================================================================
' MODULE: CORE_Util
'------------------------------------------------------------------------------
' PURPOSE
'   Provide the worksheet plumbing shared by the engine, the calibration
'   and the tests: locate sheets and tables through workbook names, read
'   and write table blocks in one operation, collect and write the Checks,
'   classify cell values, and do the whole-month calendar arithmetic of
'   the model.
'
' PUBLIC SURFACE
'   None outside this VBA project (Option Private Module).
'
' DEPENDENCIES
'   CORE_Config for sheet names, table names and severities.
'
' STATE OWNERSHIP
'   No module state. Reads and writes cells of ThisWorkbook only; never
'   changes Excel application settings.
'
' ERROR POLICY
'   A missing sheet or workbook name raises ERR_MISSING_SHEET or
'   ERR_MISSING_NAME: the workbook structure is broken, which is not an
'   input error. Everything else is contained.
'
' COMPATIBILITY
'   Excel VBA; no references beyond the defaults (no Scripting.Dictionary).
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
    Option Private Module


'
'------------------------------------------------------------------------------
'
'                              SHEETS AND TABLES
'
'------------------------------------------------------------------------------
'

Public Function GetSheet( _
    ByVal SheetName As String) _
    As Worksheet
'
'==============================================================================
'                                   GetSheet
'------------------------------------------------------------------------------
' PURPOSE
'   Return a worksheet of ThisWorkbook by tab name.
'
' ERROR POLICY
'   Raises ERR_MISSING_SHEET when the sheet does not exist.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Found          As Worksheet    'Sheet looked up

        On Error Resume Next
        Set Found = ThisWorkbook.Worksheets(SheetName)
        On Error GoTo 0
        If Found Is Nothing Then
            Err.Raise ERR_MISSING_SHEET, "CORE_Util.GetSheet", _
                      "The workbook has no sheet named '" & SheetName & "'."
        End If
        Set GetSheet = Found

End Function


Public Function NamedCell( _
    ByVal WorkbookName As String) _
    As Range
'
'==============================================================================
'                                  NamedCell
'------------------------------------------------------------------------------
' PURPOSE
'   Return the first cell of the range a workbook name refers to.
'
' ERROR POLICY
'   Raises ERR_MISSING_NAME when the name is missing or broken (#REF!).
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Target         As Range    'Range the name refers to

        On Error Resume Next
        Set Target = ThisWorkbook.Names(WorkbookName).RefersToRange
        On Error GoTo 0
        If Target Is Nothing Then
            Err.Raise ERR_MISSING_NAME, "CORE_Util.NamedCell", _
                      "The workbook name '" & WorkbookName & "' is missing or does not refer to a range."
        End If
        Set NamedCell = Target.Cells(1, 1)

End Function


Public Function TableCol( _
    ByVal TableColumn As Long) _
    As Long
'
'==============================================================================
'                                   TableCol
'------------------------------------------------------------------------------
' PURPOSE
'   Convert a table column number (1 = first table column) into a sheet
'   column number.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        TableCol = COL_OFFSET + TableColumn

End Function


Public Function LastTableRow( _
    ByVal Sheet As Worksheet, _
    ByVal FirstRow As Long, _
    ByVal ColumnCount As Long) _
    As Long
'
'==============================================================================
'                                 LastTableRow
'------------------------------------------------------------------------------
' PURPOSE
'   Return the last row holding a value in any column of a table.
'
' INPUTS
'   FirstRow: first data row. ColumnCount: table columns, >= 1.
'
' RETURNS
'   The last row with a value, or FirstRow - 1 when the table is empty.
'   Formatting alone does not count.
'
' DEPENDENCIES
'   Scans the block up to the end of the used range instead of using
'   Range.End, which needs a window: the same code then runs in the
'   headless test host (tools/run_vba_headless.py).
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim UsedLast       As Long       'Last row of the used range
    Dim Block          As Variant    'Values of the table columns
    Dim r              As Long       'Block row
    Dim c              As Long       'Block column

        LastTableRow = FirstRow - 1
        With Sheet.UsedRange
            UsedLast = .Row + .Rows.Count - 1
        End With
        If UsedLast < FirstRow Then Exit Function
        Block = ReadTable(Sheet, FirstRow, UsedLast, ColumnCount)
        For r = UsedLast - FirstRow + 1 To 1 Step -1
            For c = 1 To ColumnCount
                If IsError(Block(r, c)) Then
                    LastTableRow = FirstRow + r - 1
                    Exit Function
                End If
                If Not IsBlankValue(Block(r, c)) Then
                    LastTableRow = FirstRow + r - 1
                    Exit Function
                End If
            Next c
        Next r

End Function


Public Function ReadTable( _
    ByVal Sheet As Worksheet, _
    ByVal FirstRow As Long, _
    ByVal LastRow As Long, _
    ByVal ColumnCount As Long) _
    As Variant
'
'==============================================================================
'                                  ReadTable
'------------------------------------------------------------------------------
' PURPOSE
'   Read a table block in one operation, as Value2 (dates as serial
'   numbers, so that no locale or Date conversion is involved).
'
' RETURNS
'   A 1-based two-dimensional Variant array (rows, columns); Empty when
'   LastRow < FirstRow.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Block          As Variant    'Values read
    Dim Single1(1 To 1, 1 To 1) As Variant    'Holder for a one-cell block

        If LastRow < FirstRow Then
            ReadTable = Empty
            Exit Function
        End If
        Block = Sheet.Range(Sheet.Cells(FirstRow, TableCol(1)), _
                            Sheet.Cells(LastRow, TableCol(ColumnCount))).Value2
        If Not IsArray(Block) Then
            Single1(1, 1) = Block
            ReadTable = Single1
        Else
            ReadTable = Block
        End If

End Function


Public Sub WriteTable( _
    ByVal Sheet As Worksheet, _
    ByVal FirstRow As Long, _
    ByRef Block As Variant, _
    ByVal RowCount As Long, _
    ByVal ColumnCount As Long, _
    Optional ByVal FirstColumn As Long = 1)
'
'==============================================================================
'                                  WriteTable
'------------------------------------------------------------------------------
' PURPOSE
'   Write a 1-based two-dimensional array to a table in one operation.
'
' INPUTS
'   Block: array of at least RowCount x ColumnCount. FirstColumn: table
'   column of the first array column.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        If RowCount < 1 Or ColumnCount < 1 Then Exit Sub
        Sheet.Range(Sheet.Cells(FirstRow, TableCol(FirstColumn)), _
                    Sheet.Cells(FirstRow + RowCount - 1, TableCol(FirstColumn + ColumnCount - 1))).Value = Block

End Sub


Public Sub ClearTable( _
    ByVal Sheet As Worksheet, _
    ByVal FirstRow As Long, _
    ByVal ColumnCount As Long, _
    Optional ByVal MaxRows As Long = 0)
'
'==============================================================================
'                                  ClearTable
'------------------------------------------------------------------------------
' PURPOSE
'   Clear the values of an output table below its header, keeping the
'   formats of the template.
'
' INPUTS
'   MaxRows: rows the table may occupy when another table sits below it
'   on the same sheet (Results, Calibration); 0 = down to the last value.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim LastRow        As Long    'Last row holding a value

        If MaxRows > 0 Then
            LastRow = FirstRow + MaxRows - 1
        Else
            LastRow = LastTableRow(Sheet, FirstRow, ColumnCount)
        End If
        If LastRow >= FirstRow Then
            Sheet.Range(Sheet.Cells(FirstRow, TableCol(1)), _
                        Sheet.Cells(LastRow, TableCol(ColumnCount))).ClearContents
        End If

End Sub


Public Sub FormatColumn( _
    ByVal Sheet As Worksheet, _
    ByVal FirstRow As Long, _
    ByVal RowCount As Long, _
    ByVal TableColumn As Long, _
    ByVal NumberFormat As String)
'
'==============================================================================
'                                 FormatColumn
'------------------------------------------------------------------------------
' PURPOSE
'   Apply a number format to the written rows of one output column.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        If RowCount < 1 Then Exit Sub
        Sheet.Range(Sheet.Cells(FirstRow, TableCol(TableColumn)), _
                    Sheet.Cells(FirstRow + RowCount - 1, TableCol(TableColumn))).NumberFormat = NumberFormat

End Sub


Public Function ListItem( _
    ByVal CommaList As String, _
    ByVal Index As Long) _
    As String
'
'==============================================================================
'                                   ListItem
'------------------------------------------------------------------------------
' PURPOSE
'   Return item Index (1-based) of a comma-separated constant list.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Items          As Variant    'Split list, 0-based

        Items = Split(CommaList, ",")
        ListItem = CStr(Items(Index - 1))

End Function


Public Function ScenarioCode( _
    ByVal ScenarioIndex As Long) _
    As String
'
'==============================================================================
'                                 ScenarioCode
'------------------------------------------------------------------------------
' PURPOSE
'   Return the code of a scenario index (SC_CONTRACT ... SC_SHORT_DOWN).
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        ScenarioCode = ListItem(SCEN_CODES, ScenarioIndex)

End Function


'
'------------------------------------------------------------------------------
'
'                                    CHECKS
'
'------------------------------------------------------------------------------
'

Public Sub AddCheck( _
    ByVal Checks As Collection, _
    ByVal Severity As String, _
    ByVal SheetName As String, _
    ByVal SheetRow As Long, _
    ByVal Reference As String, _
    ByVal Message As String)
'
'==============================================================================
'                                   AddCheck
'------------------------------------------------------------------------------
' PURPOSE
'   Append one finding to the run's collection of checks.
'
' INPUTS
'   Severity: SEV_ERROR, SEV_WARNING or SEV_INFO. SheetRow: 0 when the
'   finding is not about one row.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Entry(1 To 5)  As Variant    'One Checks row

        Entry(1) = Severity
        Entry(2) = SheetName
        If SheetRow > 0 Then Entry(3) = SheetRow Else Entry(3) = Empty
        Entry(4) = Reference
        Entry(5) = Message
        Checks.Add Entry

End Sub


Public Function CountChecks( _
    ByVal Checks As Collection, _
    ByVal Severity As String) _
    As Long
'
'==============================================================================
'                                 CountChecks
'------------------------------------------------------------------------------
' PURPOSE
'   Count the checks of one severity.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim i              As Long    'Check index
    Dim Result         As Long    'Count
    Dim Entry          As Variant 'One check

        For i = 1 To Checks.Count
            Entry = Checks(i)
            If Entry(1) = Severity Then Result = Result + 1
        Next i
        CountChecks = Result

End Function


Public Sub WriteChecks( _
    ByVal Checks As Collection, _
    ByVal StatusLine As String)
'
'==============================================================================
'                                 WriteChecks
'------------------------------------------------------------------------------
' PURPOSE
'   Replace the Checks table with the collected findings and write the
'   status line.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Sheet          As Worksheet    'Checks sheet
    Dim FirstRow       As Long         'First data row
    Dim Block()        As Variant      'Rows to write
    Dim Entry          As Variant      'One check
    Dim i              As Long         'Check index
    Dim c              As Long         'Column

        Set Sheet = GetSheet(SH_CHECKS)
        FirstRow = NamedCell(NM_CHECKS).Row + 1
        ClearTable Sheet, FirstRow, CK_NCOLS
        Sheet.Range(STATUS_CELL).Value = StatusLine
        If Checks.Count = 0 Then
            Sheet.Cells(FirstRow, TableCol(1)).Value = SEV_INFO
            Sheet.Cells(FirstRow, TableCol(5)).Value = "No errors or warnings."
            Exit Sub
        End If
        ReDim Block(1 To Checks.Count, 1 To CK_NCOLS)
        For i = 1 To Checks.Count
            Entry = Checks(i)
            For c = 1 To CK_NCOLS
                Block(i, c) = Entry(c)
            Next c
        Next i
        WriteTable Sheet, FirstRow, Block, Checks.Count, CK_NCOLS

End Sub


'
'------------------------------------------------------------------------------
'
'                                CELL VALUES
'
'------------------------------------------------------------------------------
'

Public Function IsNumberValue( _
    ByVal CellValue As Variant) _
    As Boolean
'
'==============================================================================
'                                IsNumberValue
'------------------------------------------------------------------------------
' PURPOSE
'   True when a Value2 cell value is a number. Text that looks like a
'   number is not accepted: it would be read differently by locale.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        Select Case VarType(CellValue)
            Case vbDouble, vbSingle, vbInteger, vbLong, vbCurrency, vbDecimal
                IsNumberValue = True
            Case Else
                IsNumberValue = False
        End Select

End Function


Public Function IsBlankValue( _
    ByVal CellValue As Variant) _
    As Boolean
'
'==============================================================================
'                                 IsBlankValue
'------------------------------------------------------------------------------
' PURPOSE
'   True for an empty cell or one holding only spaces.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        If IsEmpty(CellValue) Then
            IsBlankValue = True
        ElseIf VarType(CellValue) = vbString Then
            IsBlankValue = (Len(Trim$(CellValue)) = 0)
        Else
            IsBlankValue = False
        End If

End Function


Public Function TextValue( _
    ByVal CellValue As Variant) _
    As String
'
'==============================================================================
'                                  TextValue
'------------------------------------------------------------------------------
' PURPOSE
'   Return a cell value as trimmed upper-case text; "" for an error value.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        If IsError(CellValue) Then
            TextValue = ""
        ElseIf IsEmpty(CellValue) Then
            TextValue = ""
        Else
            TextValue = UCase$(Trim$(CStr(CellValue)))
        End If

End Function


Public Function RowIsBlank( _
    ByRef Block As Variant, _
    ByVal RowIndex As Long, _
    ByVal ColumnCount As Long) _
    As Boolean
'
'==============================================================================
'                                  RowIsBlank
'------------------------------------------------------------------------------
' PURPOSE
'   True when every column of one row of a table block is blank.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim c              As Long    'Column

        For c = 1 To ColumnCount
            If IsError(Block(RowIndex, c)) Then Exit Function
            If Not IsBlankValue(Block(RowIndex, c)) Then Exit Function
        Next c
        RowIsBlank = True

End Function


'
'------------------------------------------------------------------------------
'
'                                   CALENDAR
'
'------------------------------------------------------------------------------
'

Public Function MonthsUp( _
    ByVal FromDate As Date, _
    ByVal ToDate As Date) _
    As Long
'
'==============================================================================
'                                   MonthsUp
'------------------------------------------------------------------------------
' PURPOSE
'   Whole months from FromDate to ToDate, a started month counting as one:
'   the number of monthly steps needed to reach ToDate.
'
' REFERENCE
'   tools/reference_model.py months_up.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Result         As Long    'Months

        Result = (Year(ToDate) - Year(FromDate)) * 12 + (Month(ToDate) - Month(FromDate))
        If Day(ToDate) > Day(FromDate) Then Result = Result + 1
        MonthsUp = Result

End Function


Public Function MonthsDown( _
    ByVal FromDate As Date, _
    ByVal ToDate As Date) _
    As Long
'
'==============================================================================
'                                  MonthsDown
'------------------------------------------------------------------------------
' PURPOSE
'   Completed whole months from FromDate to ToDate.
'
' REFERENCE
'   tools/reference_model.py months_down.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Result         As Long    'Months

        Result = (Year(ToDate) - Year(FromDate)) * 12 + (Month(ToDate) - Month(FromDate))
        If Day(ToDate) < Day(FromDate) Then Result = Result - 1
        MonthsDown = Result

End Function


Public Function AddMonths( _
    ByVal StartDate As Date, _
    ByVal MonthCount As Long) _
    As Date
'
'==============================================================================
'                                  AddMonths
'------------------------------------------------------------------------------
' PURPOSE
'   EDATE: the same day MonthCount months later, clipped to the month end.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim FirstOfMonth   As Date       'First day of the target month
    Dim LastDay        As Long       'Days in the target month

        FirstOfMonth = DateSerial(Year(StartDate), Month(StartDate) + MonthCount, 1)
        LastDay = Day(DateSerial(Year(FirstOfMonth), Month(FirstOfMonth) + 1, 0))
        If Day(StartDate) < LastDay Then
            AddMonths = DateSerial(Year(FirstOfMonth), Month(FirstOfMonth), Day(StartDate))
        Else
            AddMonths = DateSerial(Year(FirstOfMonth), Month(FirstOfMonth), LastDay)
        End If

End Function


Public Function AppendDetail( _
    ByVal Existing As String, _
    ByVal Addition As String) _
    As String
'
'==============================================================================
'                                 AppendDetail
'------------------------------------------------------------------------------
' PURPOSE
'   Join two message fragments with "; ", skipping empty ones.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        If Len(Addition) = 0 Then
            AppendDetail = Existing
        ElseIf Len(Existing) = 0 Then
            AppendDetail = Addition
        Else
            AppendDetail = Existing & "; " & Addition
        End If

End Function
