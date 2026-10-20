Attribute VB_Name = "CORE_Engine"
'==============================================================================
' MODULE: CORE_Engine
'------------------------------------------------------------------------------
' PURPOSE
'   Read and validate the inputs, project every loan month by month under
'   the contractual, base and six shock scenarios, discount the cash flows
'   on the scenario curves and write Results, CashFlows, Gap,
'   ScenarioCurves, LoanCalc and Checks.
'
' PUBLIC SURFACE
'   None outside this VBA project (Option Private Module). M_Main and the
'   tests call Calculate and ClearModelOutputs.
'
' DEPENDENCIES
'   CORE_Config (layout), CORE_Util (sheets, checks, calendar), CORE_Curve
'   (zero rates, shocks, lower bound), CORE_Prepay (CPR and SMM).
'
' STATE OWNERSHIP
'   No module state: each run builds its data from the sheets. Reads the
'   input sheets and writes the output sheets of ThisWorkbook; never
'   changes Excel application settings (M_Main owns them).
'
' ERROR POLICY
'   Input problems are not VBA errors: they are listed on Checks. A loan
'   or segment with an ERROR is excluded; a problem in the parameters or
'   the curve stops the run with the outputs cleared. A broken workbook
'   (missing sheet or name) raises from CORE_Util and propagates.
'
' REFERENCE
'   tools/reference_model.py is the executable specification; every
'   arithmetic step below follows it in the same order. BCBS d368
'   para 124 and Table 3 (prepayment, gamma), Annex 2 (shocks);
'   Reg. (EU) 2024/856 Art. 3 (EVE assumptions, lower bound) and Annex.
'
' COMPATIBILITY
'   Excel VBA; no references beyond the defaults. No function returns a
'   typed array and no Range.End is used, so the module also runs in the
'   headless test host.
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

'------------------------------------------------------------------------------
' MODULE TYPES
'------------------------------------------------------------------------------
    'Run parameters read from Params.
        Public Type PpmParams
            AsOfDate        As Date       'Reporting date
            Ccy             As String     'Reporting currency, upper case
            Mode            As String     'MODE_BEHAVIOURAL or MODE_BCBS_SA
            ShockParallel   As Double     'Decimal
            ShockShort      As Double     'Decimal
            ShockLong       As Double     'Decimal
            Decay           As Double     'Years
            ApplyFloor      As Boolean    'Apply the post-shock lower bound
            FloorStart      As Double     'Decimal at 0 years
            FloorSlope      As Double     'Decimal per year
            MaxMonths       As Long       'Longest remaining maturity, months
            Tier1           As Double     'Reporting currency
            Outlier         As Double     'Decimal share of Tier 1
        End Type

    'One prepayment segment.
        Public Type PpmSegment
            Id              As String     'SegmentID, upper case
            CprMin          As Double     'Annual CPR, decimal
            CprMax          As Double     'Annual CPR, decimal
            Slope           As Double     'Per unit of incentive
            Midpoint        As Double     'Incentive, decimal
            RampMonths      As Long       'Seasoning ramp, months
            Burnout         As Double     'Burnout speed, >= 0
            Margin          As Double     'Refinancing margin, decimal
            FloatCpr        As Double     'Annual CPR of floating-rate loans
            Seasonal        As Boolean    'Apply the seasonality
            Valid           As Boolean    'False when the row has an ERROR
            SheetRow        As Long       'Row on Segments
        End Type

    'One loan.
        Public Type PpmLoan
            Id              As String     'LoanID as entered
            SegmentText     As String     'SegmentID as entered
            SegmentIndex    As Long       'Index in the segment array; 0 if none
            IsFloat         As Boolean    'FLOAT: reprices at the reset date
            Balance         As Double     'Outstanding principal
            Rate            As Double     'Client rate, decimal
            AmortCode       As Long       'AM_ANNUITY, AM_LINEAR or AM_BULLET
            Frequency       As Long       'Months between payments
            Penalty         As Double     'Share of the prepaid amount
            RemMonths       As Long       'Months to maturity, started month = 1
            AgeMonths       As Long       'Completed months since origination
            EndMonths       As Long       'Months with cash flows (reset or maturity)
            Used            As Boolean    'Included in the run
            Messages        As String     'Findings for LoanCalc
            SheetRow        As Long       'Row on Loans
        End Type


'
'------------------------------------------------------------------------------
'
'                                     RUN
'
'------------------------------------------------------------------------------
'

Public Function Calculate( _
    ByVal WriteOutputs As Boolean, _
    ByRef StatusLine As String) _
    As Boolean
'
'==============================================================================
'                                  Calculate
'------------------------------------------------------------------------------
' PURPOSE
'   Validate the inputs and, when WriteOutputs is True, run the model and
'   write every output sheet.
'
' INPUTS
'   WriteOutputs: True for a run, False to validate only (Checks only).
'
' RETURNS
'   True when the run (or validation) completed with at least one loan
'   used; False when it stopped. StatusLine: the summary written to C4 of
'   the output sheets.
'
' ERROR POLICY
'   Input findings go to Checks. A broken workbook raises and propagates.
'
' UPDATED
'   2026-10-20
'==============================================================================
'

'------------------------------------------------------------------------------
' DECLARE
'------------------------------------------------------------------------------
    Dim Checks         As Collection     'Findings of this run
    Dim Prm            As PpmParams      'Parameters
    Dim Tenors()       As Double         'Curve tenors, years
    Dim Rates()        As Double         'Curve zero rates
    Dim PointCount     As Long           'Curve points
    Dim Gamma(1 To SCEN_COUNT) As Double 'CPR multipliers by scenario
    Dim Season(1 To 12) As Double        'Seasonality by calendar month
    Dim Segs()         As PpmSegment     'Segments
    Dim SegCount       As Long           'Segments read
    Dim Loans()        As PpmLoan        'Loans
    Dim LoanCount      As Long           'Loan rows read
    Dim UsedCount      As Long           'Loans used
    Dim Stopped        As Boolean        'A fatal input problem was found
    Dim StartTime      As Double         'Timer at the start
    Dim ErrorCount     As Long           'ERROR findings
    Dim WarningCount   As Long           'WARNING findings

'------------------------------------------------------------------------------
' READ AND VALIDATE
'------------------------------------------------------------------------------
        StartTime = Timer
        Set Checks = New Collection
        Stopped = Not ReadParams(Checks, Prm)
        If Not ReadCurve(Checks, Tenors, Rates, PointCount) Then Stopped = True
        If Not ReadGamma(Checks, Gamma) Then Stopped = True
        If Not ReadSeasonality(Checks, Season) Then Stopped = True
        SegCount = ReadSegments(Checks, Segs)
        If Not Stopped Then
            LoanCount = ReadLoans(Checks, Prm, Segs, SegCount, Loans, UsedCount)
            If UsedCount = 0 Then
                AddCheck Checks, SEV_ERROR, SH_LOANS, 0, "", "No loan can be used: the run stops."
                Stopped = True
            End If
        End If
        ErrorCount = CountChecks(Checks, SEV_ERROR)
        WarningCount = CountChecks(Checks, SEV_WARNING)

'------------------------------------------------------------------------------
' STOP, VALIDATE ONLY OR RUN
'------------------------------------------------------------------------------
        If Stopped Then
            StatusLine = "Run stopped " & Format$(Now, "yyyy-mm-dd hh:mm:ss") & ": " & ErrorCount & _
                         " errors; see Checks."
            If WriteOutputs Then ClearModelOutputs StatusLine
            WriteChecks Checks, StatusLine
            Calculate = False
            Exit Function
        End If
        If Not WriteOutputs Then
            StatusLine = "Inputs validated " & Format$(Now, "yyyy-mm-dd hh:mm:ss") & " | " & UsedCount & " of " & _
                         LoanCount & " loans usable | " & ErrorCount & " errors, " & WarningCount & " warnings"
            WriteChecks Checks, StatusLine
            Calculate = True
            Exit Function
        End If
        ProjectBook Prm, Tenors, Rates, PointCount, Gamma, Season, Segs, SegCount, Loans, LoanCount, UsedCount
        StatusLine = "Run " & Format$(Now, "yyyy-mm-dd hh:mm:ss") & " | " & Prm.Mode & " | " & UsedCount & " of " & _
                     LoanCount & " loans used | " & ErrorCount & " errors, " & WarningCount & " warnings | " & _
                     Format$(Timer - StartTime, "0.0") & " s"
        WriteStatus StatusLine
        WriteChecks Checks, StatusLine
        Calculate = True

End Function


Public Sub ClearModelOutputs( _
    ByVal StatusLine As String)
'
'==============================================================================
'                              ClearModelOutputs
'------------------------------------------------------------------------------
' PURPOSE
'   Clear every model output table (not Checks, Calibration or Tests) and
'   write the status line.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Sheet          As Worksheet    'Results

        Set Sheet = GetSheet(SH_RESULTS)
        ClearTable Sheet, NamedCell(NM_RESULTS).Row + 1, RS_NCOLS, SCEN_COUNT
        ClearTable Sheet, NamedCell(NM_SUMMARY).Row + 1, SM_NCOLS, SM_ROWS
        ClearTable Sheet, NamedCell(NM_SEGRES).Row + 1, SR_NCOLS
        ClearTable GetSheet(SH_CASHFLOWS), NamedCell(NM_CASHFLOWS).Row + 1, CF_NCOLS
        ClearTable GetSheet(SH_GAP), NamedCell(NM_GAP).Row + 1, GP_NCOLS
        ClearTable GetSheet(SH_CURVES), NamedCell(NM_CURVES).Row + 1, SCV_NCOLS
        ClearTable GetSheet(SH_LOANCALC), NamedCell(NM_LOANCALC).Row + 1, LC_NCOLS
        WriteStatus StatusLine

End Sub


Private Sub WriteStatus( _
    ByVal StatusLine As String)
'
'==============================================================================
'                                 WriteStatus
'------------------------------------------------------------------------------
' PURPOSE
'   Write the status line to C4 of the model output sheets.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        GetSheet(SH_RESULTS).Range(STATUS_CELL).Value = StatusLine
        GetSheet(SH_CASHFLOWS).Range(STATUS_CELL).Value = StatusLine
        GetSheet(SH_GAP).Range(STATUS_CELL).Value = StatusLine
        GetSheet(SH_CURVES).Range(STATUS_CELL).Value = StatusLine
        GetSheet(SH_LOANCALC).Range(STATUS_CELL).Value = StatusLine

End Sub


'
'------------------------------------------------------------------------------
'
'                                INPUT READING
'
'------------------------------------------------------------------------------
'

Private Function ReadParams( _
    ByVal Checks As Collection, _
    ByRef Prm As PpmParams) _
    As Boolean
'
'==============================================================================
'                                  ReadParams
'------------------------------------------------------------------------------
' PURPOSE
'   Read and validate the parameters on Params.
'
' RETURNS
'   True when every parameter is valid; each invalid one is an ERROR.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Ok             As Boolean    'No invalid parameter so far
    Dim Value          As Variant    'Parameter value
    Dim Text           As String     'Parameter as text

        Ok = True
        Value = ParamValue(PRM_ASOF)
        If IsNumberValue(Value) And Not IsError(Value) Then
            If Value >= 1 Then Prm.AsOfDate = CDate(Value) Else Ok = BadParam(Checks, PRM_ASOF, "a date")
        Else
            Ok = BadParam(Checks, PRM_ASOF, "a date")
        End If
        Text = TextValue(ParamValue(PRM_CCY))
        If Len(Text) = 3 Then Prm.Ccy = Text Else Ok = BadParam(Checks, PRM_CCY, "a three-letter code")
        Text = TextValue(ParamValue(PRM_MODE))
        If Text = MODE_BEHAVIOURAL Or Text = MODE_BCBS_SA Then
            Prm.Mode = Text
        Else
            Ok = BadParam(Checks, PRM_MODE, MODE_BEHAVIOURAL & " or " & MODE_BCBS_SA)
        End If
        If Not NumberParam(Checks, PRM_PARALLEL, 0, 1, Prm.ShockParallel) Then Ok = False
        If Prm.ShockParallel = 0# Then Ok = BadParam(Checks, PRM_PARALLEL, "strictly greater than zero")
        If Not NumberParam(Checks, PRM_SHORT, 0, 1, Prm.ShockShort) Then Ok = False
        If Not NumberParam(Checks, PRM_LONG, 0, 1, Prm.ShockLong) Then Ok = False
        If Not NumberParam(Checks, PRM_DECAY, 0.000001, 1000, Prm.Decay) Then Ok = False
        Text = TextValue(ParamValue(PRM_FLOOR))
        If Text = "Y" Or Text = "TRUE" Then
            Prm.ApplyFloor = True
        ElseIf Text = "N" Or Text = "FALSE" Then
            Prm.ApplyFloor = False
        Else
            Ok = BadParam(Checks, PRM_FLOOR, "Y or N")
        End If
        If Not NumberParam(Checks, PRM_FLOORSTART, -1, 1, Prm.FloorStart) Then Ok = False
        If Not NumberParam(Checks, PRM_FLOORSLOPE, 0, 1, Prm.FloorSlope) Then Ok = False
        Value = ParamValue(PRM_MAXMONTHS)
        If IsNumberValue(Value) Then
            If Value >= 1 And Value <= 1200 And Value = Int(Value) Then
                Prm.MaxMonths = CLng(Value)
            Else
                Ok = BadParam(Checks, PRM_MAXMONTHS, "a whole number from 1 to 1200")
            End If
        Else
            Ok = BadParam(Checks, PRM_MAXMONTHS, "a whole number from 1 to 1200")
        End If
        If Not NumberParam(Checks, PRM_TIER1, 0.000001, 1E+300, Prm.Tier1) Then Ok = False
        If Not NumberParam(Checks, PRM_OUTLIER, 0.000001, 10, Prm.Outlier) Then Ok = False
        ReadParams = Ok

End Function


Private Function ParamValue( _
    ByVal Code As String) _
    As Variant
'
'==============================================================================
'                                  ParamValue
'------------------------------------------------------------------------------
' PURPOSE
'   Value2 of the cell the parameter's workbook name refers to.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        ParamValue = NamedCell(Code).Value2

End Function


Private Function NumberParam( _
    ByVal Checks As Collection, _
    ByVal Code As String, _
    ByVal Lowest As Double, _
    ByVal Highest As Double, _
    ByRef Result As Double) _
    As Boolean
'
'==============================================================================
'                                 NumberParam
'------------------------------------------------------------------------------
' PURPOSE
'   Read a numeric parameter in [Lowest, Highest].
'
' RETURNS
'   True and Result when valid; False and an ERROR otherwise.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Value          As Variant    'Cell value

        Value = ParamValue(Code)
        If IsNumberValue(Value) Then
            If Value >= Lowest And Value <= Highest Then
                Result = CDbl(Value)
                NumberParam = True
                Exit Function
            End If
        End If
        NumberParam = BadParam(Checks, Code, "a number from " & CStr(Lowest) & " to " & CStr(Highest))

End Function


Private Function BadParam( _
    ByVal Checks As Collection, _
    ByVal Code As String, _
    ByVal Expected As String) _
    As Boolean
'
'==============================================================================
'                                   BadParam
'------------------------------------------------------------------------------
' PURPOSE
'   Record an invalid parameter; always returns False.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        AddCheck Checks, SEV_ERROR, SH_PARAMS, NamedCell(Code).Row, Code, _
                 "Invalid value: expected " & Expected & ". The run stops."
        BadParam = False

End Function


Private Function ReadCurve( _
    ByVal Checks As Collection, _
    ByRef Tenors() As Double, _
    ByRef Rates() As Double, _
    ByRef PointCount As Long) _
    As Boolean
'
'==============================================================================
'                                  ReadCurve
'------------------------------------------------------------------------------
' PURPOSE
'   Read the zero curve: numeric tenor and rate on every non-blank row,
'   tenors > 0 and strictly increasing, at least one point.
'
' RETURNS
'   True when the curve is valid; False with ERRORs otherwise.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Sheet          As Worksheet    'Curve sheet
    Dim FirstRow       As Long         'First data row
    Dim LastRow        As Long         'Last data row
    Dim Block          As Variant      'Table values
    Dim r              As Long         'Block row
    Dim Ok             As Boolean      'No error so far

        Set Sheet = GetSheet(SH_CURVE)
        FirstRow = NamedCell(NM_CURVE).Row + 1
        LastRow = LastTableRow(Sheet, FirstRow, CV_RATE)
        Ok = True
        PointCount = 0
        If LastRow < FirstRow Then
            AddCheck Checks, SEV_ERROR, SH_CURVE, 0, "", "The curve is empty. The run stops."
            ReadCurve = False
            Exit Function
        End If
        Block = ReadTable(Sheet, FirstRow, LastRow, CV_RATE)
        ReDim Tenors(1 To LastRow - FirstRow + 1)
        ReDim Rates(1 To LastRow - FirstRow + 1)
        For r = 1 To LastRow - FirstRow + 1
            If Not RowIsBlank(Block, r, CV_RATE) Then
                If Not IsNumberValue(Block(r, CV_TENOR)) Or Not IsNumberValue(Block(r, CV_RATE)) Then
                    AddCheck Checks, SEV_ERROR, SH_CURVE, FirstRow + r - 1, "", _
                             "Tenor and zero rate must both be numbers. The run stops."
                    Ok = False
                Else
                    If Block(r, CV_TENOR) <= 0 Then
                        AddCheck Checks, SEV_ERROR, SH_CURVE, FirstRow + r - 1, "", _
                                 "Tenor must be positive. The run stops."
                        Ok = False
                    ElseIf PointCount > 0 Then
                        If Block(r, CV_TENOR) <= Tenors(PointCount) Then
                            AddCheck Checks, SEV_ERROR, SH_CURVE, FirstRow + r - 1, "", _
                                     "Tenors must be strictly increasing. The run stops."
                            Ok = False
                        End If
                    End If
                    If Ok Then
                        PointCount = PointCount + 1
                        Tenors(PointCount) = CDbl(Block(r, CV_TENOR))
                        Rates(PointCount) = CDbl(Block(r, CV_RATE))
                    End If
                End If
            End If
        Next r
        If Ok And PointCount = 0 Then
            AddCheck Checks, SEV_ERROR, SH_CURVE, 0, "", "The curve has no point. The run stops."
            Ok = False
        End If
        ReadCurve = Ok

End Function


Private Function ReadGamma( _
    ByVal Checks As Collection, _
    ByRef Gamma() As Double) _
    As Boolean
'
'==============================================================================
'                                  ReadGamma
'------------------------------------------------------------------------------
' PURPOSE
'   Read the CPR multiplier of each shock scenario from the table under
'   Gamma_Table (code in column 1, multiplier in column 3).
'
' RETURNS
'   True when all six shocks have a multiplier >= 0. CONTRACT and BASE
'   get 1.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Sheet          As Worksheet    'Params
    Dim Header         As Range        'Header cell
    Dim Block          As Variant      'Six table rows
    Dim Found(1 To SCEN_COUNT) As Boolean    'Multiplier read
    Dim r              As Long         'Block row
    Dim s              As Long         'Scenario
    Dim Ok             As Boolean      'No error so far

        Set Sheet = GetSheet(SH_PARAMS)
        Set Header = NamedCell(NM_GAMMA)
        Block = ReadTable(Sheet, Header.Row + 1, Header.Row + SCEN_COUNT - SC_FIRST_SHOCK + 1, 3)
        Gamma(SC_CONTRACT) = 1#
        Gamma(SC_BASE) = 1#
        Ok = True
        For r = 1 To SCEN_COUNT - SC_FIRST_SHOCK + 1
            s = ScenarioIndex(TextValue(Block(r, 1)))
            If s >= SC_FIRST_SHOCK Then
                If IsNumberValue(Block(r, 3)) Then
                    If Block(r, 3) >= 0 Then
                        Gamma(s) = CDbl(Block(r, 3))
                        Found(s) = True
                    End If
                End If
            End If
        Next r
        For s = SC_FIRST_SHOCK To SCEN_COUNT
            If Not Found(s) Then
                AddCheck Checks, SEV_ERROR, SH_PARAMS, Header.Row, ScenarioCode(s), _
                         "Missing or invalid CPR multiplier (number >= 0 expected). The run stops."
                Ok = False
            End If
        Next s
        ReadGamma = Ok

End Function


Private Function ReadSeasonality( _
    ByVal Checks As Collection, _
    ByRef Season() As Double) _
    As Boolean
'
'==============================================================================
'                               ReadSeasonality
'------------------------------------------------------------------------------
' PURPOSE
'   Read the twelve calendar-month multipliers (column 3 under
'   Seasonality_Table). An average other than 1 is a WARNING.
'
' RETURNS
'   True when all twelve are numbers >= 0.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Header         As Range        'Header cell
    Dim Block          As Variant      'Twelve rows
    Dim m              As Long         'Calendar month
    Dim Total          As Double       'Sum of the multipliers
    Dim Ok             As Boolean      'No error so far

        Set Header = NamedCell(NM_SEASON)
        Block = ReadTable(GetSheet(SH_PARAMS), Header.Row + 1, Header.Row + 12, 3)
        Ok = True
        For m = 1 To 12
            If IsNumberValue(Block(m, 3)) Then
                If Block(m, 3) >= 0 Then
                    Season(m) = CDbl(Block(m, 3))
                    Total = Total + Season(m)
                Else
                    Ok = False
                End If
            Else
                Ok = False
            End If
        Next m
        If Not Ok Then
            AddCheck Checks, SEV_ERROR, SH_PARAMS, Header.Row, "Seasonality", _
                     "Every monthly multiplier must be a number >= 0. The run stops."
        ElseIf Abs(Total / 12# - 1#) > SEASON_TOL Then
            AddCheck Checks, SEV_WARNING, SH_PARAMS, Header.Row, "Seasonality", _
                     "The multipliers average " & Format$(Total / 12#, "0.0000") & _
                     ", not 1: the CPR level is scaled as entered."
        End If
        ReadSeasonality = Ok

End Function


Private Function ReadSegments( _
    ByVal Checks As Collection, _
    ByRef Segs() As PpmSegment) _
    As Long
'
'==============================================================================
'                                 ReadSegments
'------------------------------------------------------------------------------
' PURPOSE
'   Read and validate the segments. A segment with an ERROR is kept with
'   Valid = False, so that its loans are excluded with a clear reason.
'
' RETURNS
'   The number of segment rows read (0 when none).
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Sheet          As Worksheet    'Segments
    Dim FirstRow       As Long         'First data row
    Dim LastRow        As Long         'Last data row
    Dim Block          As Variant      'Table values
    Dim r              As Long         'Block row
    Dim n              As Long         'Segments read
    Dim i              As Long         'Earlier segment
    Dim Problem        As String       'Findings of the row
    Dim Flag           As String       'Seasonality flag

        Set Sheet = GetSheet(SH_SEGMENTS)
        FirstRow = NamedCell(NM_SEGMENTS).Row + 1
        LastRow = LastTableRow(Sheet, FirstRow, SG_NCOLS)
        ReadSegments = 0
        If LastRow < FirstRow Then
            AddCheck Checks, SEV_ERROR, SH_SEGMENTS, 0, "", "No segment is defined."
            Exit Function
        End If
        Block = ReadTable(Sheet, FirstRow, LastRow, SG_NCOLS)
        ReDim Segs(1 To LastRow - FirstRow + 1)
        For r = 1 To LastRow - FirstRow + 1
            If Not RowIsBlank(Block, r, SG_NCOLS) Then
                n = n + 1
                Problem = ""
                With Segs(n)
                    .SheetRow = FirstRow + r - 1
                    .Id = TextValue(Block(r, SG_ID))
                    If Len(.Id) = 0 Then Problem = AppendDetail(Problem, "SegmentID is blank")
                    For i = 1 To n - 1
                        If Segs(i).Id = .Id And Len(.Id) > 0 Then
                            Problem = AppendDetail(Problem, "duplicate SegmentID")
                        End If
                    Next i
                    Problem = AppendDetail(Problem, SegNumber(Block(r, SG_CPRMIN), 0, 1, "CPR min", .CprMin))
                    Problem = AppendDetail(Problem, SegNumber(Block(r, SG_CPRMAX), 0, 1, "CPR max", .CprMax))
                    If .CprMax < .CprMin Then Problem = AppendDetail(Problem, "CPR max is below CPR min")
                    Problem = AppendDetail(Problem, SegNumber(Block(r, SG_SLOPE), 0.000001, 100000#, "Slope", .Slope))
                    Problem = AppendDetail(Problem, SegNumber(Block(r, SG_MID), -1, 1, "Midpoint", .Midpoint))
                    Problem = AppendDetail(Problem, SegWhole(Block(r, SG_RAMP), "Seasoning ramp", .RampMonths))
                    Problem = AppendDetail(Problem, SegNumber(Block(r, SG_BURNOUT), 0, 1000, "Burnout", .Burnout))
                    Problem = AppendDetail(Problem, SegNumber(Block(r, SG_MARGIN), -1, 1, "Refinancing margin", .Margin))
                    Problem = AppendDetail(Problem, SegNumber(Block(r, SG_FLOATCPR), 0, 1, "Floating-rate CPR", .FloatCpr))
                    Flag = TextValue(Block(r, SG_SEASONAL))
                    If Flag = "Y" Then
                        .Seasonal = True
                    ElseIf Flag = "N" Or Len(Flag) = 0 Then
                        .Seasonal = False
                    Else
                        Problem = AppendDetail(Problem, "Seasonality must be Y or N")
                    End If
                    .Valid = (Len(Problem) = 0)
                    If Not .Valid Then
                        AddCheck Checks, SEV_ERROR, SH_SEGMENTS, .SheetRow, .Id, _
                                 Problem & ". Loans of the segment are excluded."
                    End If
                End With
            End If
        Next r
        ReadSegments = n

End Function


Private Function SegNumber( _
    ByVal CellValue As Variant, _
    ByVal Lowest As Double, _
    ByVal Highest As Double, _
    ByVal Label As String, _
    ByRef Result As Double) _
    As String
'
'==============================================================================
'                                  SegNumber
'------------------------------------------------------------------------------
' PURPOSE
'   Read one numeric segment field in [Lowest, Highest].
'
' RETURNS
'   "" and Result when valid; the finding otherwise.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        If IsNumberValue(CellValue) Then
            If CellValue >= Lowest And CellValue <= Highest Then
                Result = CDbl(CellValue)
                SegNumber = ""
                Exit Function
            End If
        End If
        SegNumber = Label & " must be a number from " & CStr(Lowest) & " to " & CStr(Highest)

End Function


Private Function SegWhole( _
    ByVal CellValue As Variant, _
    ByVal Label As String, _
    ByRef Result As Long) _
    As String
'
'==============================================================================
'                                   SegWhole
'------------------------------------------------------------------------------
' PURPOSE
'   Read a whole number of months from 0 to 1200.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        If IsNumberValue(CellValue) Then
            If CellValue >= 0 And CellValue <= 1200 And CellValue = Int(CellValue) Then
                Result = CLng(CellValue)
                SegWhole = ""
                Exit Function
            End If
        End If
        SegWhole = Label & " must be a whole number of months from 0 to 1200"

End Function


Private Function ReadLoans( _
    ByVal Checks As Collection, _
    ByRef Prm As PpmParams, _
    ByRef Segs() As PpmSegment, _
    ByVal SegCount As Long, _
    ByRef Loans() As PpmLoan, _
    ByRef UsedCount As Long) _
    As Long
'
'==============================================================================
'                                  ReadLoans
'------------------------------------------------------------------------------
' PURPOSE
'   Read and validate every loan row; set the months of the projection.
'   A loan with an ERROR is kept with Used = False.
'
' RETURNS
'   The number of loan rows read. UsedCount: loans used.
'
' REFERENCE
'   RemMonths = MonthsUp(as-of, maturity); AgeMonths = max(0,
'   MonthsDown(origination, as-of)); EndMonths = min(RemMonths,
'   MonthsUp(as-of, reset)) for FLOAT, RemMonths for FIXED.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Sheet          As Worksheet    'Loans
    Dim FirstRow       As Long         'First data row
    Dim LastRow        As Long         'Last data row
    Dim Block          As Variant      'Table values
    Dim Seen           As Collection   'LoanIDs already read, by key
    Dim r              As Long         'Block row
    Dim n              As Long         'Loans read
    Dim s              As Long         'Segment index
    Dim Problem        As String       'ERROR findings of the row
    Dim Warn           As String       'WARNING findings of the row
    Dim Text           As String       'Field as text
    Dim Value          As Variant      'Field value
    Dim Maturity       As Date         'Maturity date
    Dim ResetMonths    As Long         'Months to the reset date
    Dim Duplicate      As Boolean      'LoanID already read

        Set Sheet = GetSheet(SH_LOANS)
        FirstRow = NamedCell(NM_LOANS).Row + 1
        LastRow = LastTableRow(Sheet, FirstRow, LN_NCOLS)
        UsedCount = 0
        ReadLoans = 0
        If LastRow < FirstRow Then Exit Function
        Block = ReadTable(Sheet, FirstRow, LastRow, LN_NCOLS)
        ReDim Loans(1 To LastRow - FirstRow + 1)
        Set Seen = New Collection
        For r = 1 To LastRow - FirstRow + 1
            If Not RowIsBlank(Block, r, LN_NCOLS) Then
                n = n + 1
                Problem = ""
                Warn = ""
                With Loans(n)
                    .SheetRow = FirstRow + r - 1
                    If Not IsError(Block(r, LN_ID)) Then .Id = Trim$(CStr(Block(r, LN_ID)))
                    If Len(.Id) = 0 Then
                        Problem = AppendDetail(Problem, "LoanID is blank")
                    Else
                        Duplicate = False
                        On Error Resume Next
                        Seen.Add .Id, "K" & UCase$(.Id)
                        Duplicate = (Err.Number <> 0)
                        On Error GoTo 0
                        If Duplicate Then Problem = AppendDetail(Problem, "duplicate LoanID (the first row is used)")
                    End If
                    'Segment
                    .SegmentText = TextValue(Block(r, LN_SEG))
                    .SegmentIndex = 0
                    For s = 1 To SegCount
                        If Segs(s).Id = .SegmentText And Len(.SegmentText) > 0 Then .SegmentIndex = s
                    Next s
                    If .SegmentIndex = 0 Then
                        Problem = AppendDetail(Problem, "unknown SegmentID '" & .SegmentText & "'")
                    ElseIf Not Segs(.SegmentIndex).Valid Then
                        Problem = AppendDetail(Problem, "segment " & .SegmentText & " has errors")
                    End If
                    'Rate type and currency
                    Text = TextValue(Block(r, LN_RATETYPE))
                    If Text = "FLOAT" Then
                        .IsFloat = True
                    ElseIf Text <> "FIXED" Then
                        Problem = AppendDetail(Problem, "rate type must be FIXED or FLOAT")
                    End If
                    If TextValue(Block(r, LN_CCY)) <> Prm.Ccy Then
                        Problem = AppendDetail(Problem, "currency is not the reporting currency " & Prm.Ccy)
                    End If
                    'Amounts and rate
                    Value = Block(r, LN_BALANCE)
                    If IsNumberValue(Value) Then
                        If Value > 0 Then .Balance = CDbl(Value) Else Problem = AppendDetail(Problem, "balance must be > 0")
                    Else
                        Problem = AppendDetail(Problem, "balance must be a number")
                    End If
                    Value = Block(r, LN_RATE)
                    If IsNumberValue(Value) Then
                        If Value >= RATE_MIN And Value <= RATE_MAX Then
                            .Rate = CDbl(Value)
                        Else
                            Problem = AppendDetail(Problem, "client rate outside " & RATE_MIN & " to " & RATE_MAX)
                        End If
                    Else
                        Problem = AppendDetail(Problem, "client rate must be a number")
                    End If
                    'Dates
                    Value = Block(r, LN_MAT)
                    If IsNumberValue(Value) And Not IsError(Value) Then
                        Maturity = CDate(Value)
                        If Maturity <= Prm.AsOfDate Then
                            Problem = AppendDetail(Problem, "maturity is not after the as-of date")
                        Else
                            .RemMonths = MonthsUp(Prm.AsOfDate, Maturity)
                            If .RemMonths > Prm.MaxMonths Then
                                Problem = AppendDetail(Problem, "remaining maturity above " & Prm.MaxMonths & " months")
                            End If
                        End If
                    Else
                        Problem = AppendDetail(Problem, "maturity date is not a date")
                    End If
                    Value = Block(r, LN_ORIG)
                    If IsNumberValue(Value) Then
                        If CDate(Value) > Prm.AsOfDate Then
                            Warn = AppendDetail(Warn, "origination after the as-of date: age 0 assumed")
                            .AgeMonths = 0
                        Else
                            .AgeMonths = MonthsDown(CDate(Value), Prm.AsOfDate)
                            If .AgeMonths < 0 Then .AgeMonths = 0
                        End If
                    Else
                        Problem = AppendDetail(Problem, "origination date is not a date")
                    End If
                    'Schedule
                    Select Case TextValue(Block(r, LN_AMORT))
                        Case "ANNUITY": .AmortCode = AM_ANNUITY
                        Case "LINEAR": .AmortCode = AM_LINEAR
                        Case "BULLET": .AmortCode = AM_BULLET
                        Case Else: Problem = AppendDetail(Problem, "amortisation must be ANNUITY, LINEAR or BULLET")
                    End Select
                    Value = Block(r, LN_FREQ)
                    If VarType(Value) = vbString Then
                        If IsNumeric(Trim$(Value)) Then Value = CDbl(Trim$(Value))
                    End If
                    If IsNumberValue(Value) Then
                        Select Case Value
                            Case 1, 2, 3, 4, 6, 12: .Frequency = CLng(Value)
                            Case Else: Problem = AppendDetail(Problem, "payment frequency must be 1, 2, 3, 4, 6 or 12 months")
                        End Select
                    Else
                        Problem = AppendDetail(Problem, "payment frequency must be 1, 2, 3, 4, 6 or 12 months")
                    End If
                    Value = Block(r, LN_PENALTY)
                    If IsBlankValue(Value) Then
                        .Penalty = 0#
                    ElseIf IsNumberValue(Value) Then
                        If Value >= 0 And Value <= 1 Then
                            .Penalty = CDbl(Value)
                        Else
                            Problem = AppendDetail(Problem, "penalty must be from 0 to 1")
                        End If
                    Else
                        Problem = AppendDetail(Problem, "penalty must be a number or blank")
                    End If
                    'Repricing
                    .EndMonths = .RemMonths
                    Value = Block(r, LN_RESET)
                    If .IsFloat Then
                        If IsNumberValue(Value) Then
                            If CDate(Value) <= Prm.AsOfDate Then
                                Problem = AppendDetail(Problem, "next reset date is not after the as-of date")
                            Else
                                ResetMonths = MonthsUp(Prm.AsOfDate, CDate(Value))
                                If ResetMonths >= .RemMonths Then
                                    Warn = AppendDetail(Warn, "reset on or after maturity: no repricing before maturity")
                                Else
                                    .EndMonths = ResetMonths
                                End If
                            End If
                        Else
                            Problem = AppendDetail(Problem, "FLOAT loan needs a next reset date")
                        End If
                    ElseIf Not IsBlankValue(Value) Then
                        Warn = AppendDetail(Warn, "reset date ignored for a FIXED loan")
                    End If
                    'Outcome
                    .Used = (Len(Problem) = 0)
                    .Messages = AppendDetail(Problem, Warn)
                    If Not .Used Then
                        AddCheck Checks, SEV_ERROR, SH_LOANS, .SheetRow, .Id, Problem & ". The loan is excluded."
                    Else
                        UsedCount = UsedCount + 1
                    End If
                    If Len(Warn) > 0 Then AddCheck Checks, SEV_WARNING, SH_LOANS, .SheetRow, .Id, Warn & "."
                End With
            End If
        Next r
        ReadLoans = n

End Function


'
'------------------------------------------------------------------------------
'
'                                  PROJECTION
'
'------------------------------------------------------------------------------
'

Private Function ProjectLoan( _
    ByVal Scenario As Long, _
    ByRef Loan As PpmLoan, _
    ByRef Seg As PpmSegment, _
    ByVal ScaleBaseCpr As Boolean, _
    ByVal Gamma As Double, _
    ByVal AsOfMonth As Long, _
    ByRef Season() As Double, _
    ByRef Zero() As Double, _
    ByRef BaseCpr() As Double, _
    ByRef Sched() As Double, _
    ByRef Prep() As Double, _
    ByRef Repr() As Double, _
    ByRef Intr() As Double, _
    ByRef BalStart() As Double, _
    ByRef BalEnd() As Double, _
    ByRef Cpr() As Double) _
    As Long
'
'==============================================================================
'                                 ProjectLoan
'------------------------------------------------------------------------------
' PURPOSE
'   Project one loan month by month under one scenario.
'
' INPUTS
'   Scenario: SC_CONTRACT ... SC_SHORT_DOWN. ScaleBaseCpr: True in
'   BCBS_SA mode for a shock scenario (CPR = min(1, Gamma x BaseCpr)).
'   AsOfMonth: calendar month of the as-of date, 1 to 12. Season: 1 to 12.
'   Zero: scenario zero rates, Zero(scenario, m) at m / 12 years.
'   BaseCpr: BASE CPR path of the loan (read when ScaleBaseCpr).
'
' RETURNS
'   The number of months written (Loan.EndMonths). The output arrays,
'   1 to at least EndMonths, receive per month: scheduled principal,
'   prepayment, repricing principal (FLOAT at reset), interest paid,
'   balance at the start and end of the month, and the annual CPR.
'
' REFERENCE
'   tools/reference_model.py project: interest accrues at rate / 12 and
'   is paid on payment months ((RemMonths - k) a multiple of the
'   frequency); the scheduled principal is computed on the balance after
'   earlier prepayments; the prepayment is SMM x the balance after the
'   scheduled principal and settles the same share of accrued interest.
'
' UPDATED
'   2026-10-20
'==============================================================================
'

'------------------------------------------------------------------------------
' DECLARE
'------------------------------------------------------------------------------
    Dim k              As Long      'Projection month
    Dim RemMonths      As Long      'Months to maturity
    Dim EndMonths      As Long      'Months with cash flows
    Dim Bal            As Double    'Balance at the start of the month
    Dim Bal1           As Double    'Balance after the scheduled principal
    Dim Accrued        As Double    'Interest accrued, not yet paid
    Dim Survival       As Double    'Share of the balance not prepaid so far
    Dim RemainingYears As Double    'Maturity left at the start of the month
    Dim Ramp           As Double    'Seasoning multiplier
    Dim SeasonMult     As Double    'Seasonality multiplier
    Dim CprK           As Double    'Annual CPR of the month
    Dim SmmK           As Double    'Monthly prepayment share
    Dim Payments       As Long      'Payments left, this one included
    Dim PeriodRate     As Double    'Rate per payment period
    Dim Principal      As Double    'Scheduled principal
    Dim InterestPaid   As Double    'Interest paid on the payment date
    Dim Prepaid        As Double    'Prepaid principal
    Dim PrepaidInt     As Double    'Interest settled with the prepayment

'------------------------------------------------------------------------------
' PROJECT
'------------------------------------------------------------------------------
        RemMonths = Loan.RemMonths
        EndMonths = Loan.EndMonths
        Bal = Loan.Balance
        Accrued = 0#
        Survival = 1#
        For k = 1 To EndMonths
            RemainingYears = (RemMonths - k + 1) / 12#
            Ramp = SeasoningRamp(Loan.AgeMonths + k, Seg.RampMonths)
            If Seg.Seasonal Then
                SeasonMult = Season(((AsOfMonth - 1 + k) Mod 12) + 1)
            Else
                SeasonMult = 1#
            End If
            If Scenario = SC_CONTRACT Then
                CprK = 0#
            ElseIf Loan.IsFloat Then
                CprK = Seg.FloatCpr * Ramp * SeasonMult
                If CprK > 1# Then CprK = 1#
            ElseIf ScaleBaseCpr Then
                CprK = Gamma * BaseCpr(k)
                If CprK > 1# Then CprK = 1#
            Else
                CprK = BehaviouralCPR(Loan.Rate, Zero(Scenario, RemMonths - k + 1), Seg.Margin, Loan.Penalty, _
                                      RemainingYears, Seg.CprMin, Seg.CprMax, Seg.Slope, Seg.Midpoint, _
                                      Seg.Burnout, Survival, Ramp, SeasonMult)
            End If
            SmmK = SmmFromCpr(CprK)
            BalStart(k) = Bal
            Cpr(k) = CprK
            Accrued = Accrued + Bal * Loan.Rate / 12#
            If k = EndMonths Then
                If Loan.IsFloat And EndMonths < RemMonths Then
                    Repr(k) = Bal
                    Sched(k) = 0#
                Else
                    Sched(k) = Bal
                    Repr(k) = 0#
                End If
                Prep(k) = 0#
                Intr(k) = Accrued
                BalEnd(k) = 0#
                Exit For
            End If
            Principal = 0#
            InterestPaid = 0#
            If ((RemMonths - k) Mod Loan.Frequency) = 0 Then
                Payments = (RemMonths - k) \ Loan.Frequency + 1
                PeriodRate = Loan.Rate * Loan.Frequency / 12#
                Select Case Loan.AmortCode
                    Case AM_ANNUITY
                        If Abs(PeriodRate) < 0.000000000001 Then
                            Principal = Bal / Payments
                        Else
                            Principal = Bal * PeriodRate / ((1# + PeriodRate) ^ Payments - 1#)
                        End If
                    Case AM_LINEAR
                        Principal = Bal / Payments
                    Case Else
                        Principal = 0#
                End Select
                InterestPaid = Accrued
                Accrued = 0#
            End If
            Bal1 = Bal - Principal
            Prepaid = SmmK * Bal1
            PrepaidInt = SmmK * Accrued
            Accrued = Accrued - PrepaidInt
            Bal = Bal1 - Prepaid
            Survival = Survival * (1# - SmmK)
            Sched(k) = Principal
            Prep(k) = Prepaid
            Repr(k) = 0#
            Intr(k) = InterestPaid + PrepaidInt
            BalEnd(k) = Bal
        Next k
        ProjectLoan = EndMonths

End Function


Private Sub ProjectBook( _
    ByRef Prm As PpmParams, _
    ByRef Tenors() As Double, _
    ByRef Rates() As Double, _
    ByVal PointCount As Long, _
    ByRef Gamma() As Double, _
    ByRef Season() As Double, _
    ByRef Segs() As PpmSegment, _
    ByVal SegCount As Long, _
    ByRef Loans() As PpmLoan, _
    ByVal LoanCount As Long, _
    ByVal UsedCount As Long)
'
'==============================================================================
'                                 ProjectBook
'------------------------------------------------------------------------------
' PURPOSE
'   Project every used loan under every scenario, aggregate by month,
'   loan and segment, and write the output sheets.
'
' REFERENCE
'   tools/reference_model.py run_book. PV_s = sum CF_s(k) x exp(-z_s(k /
'   12) x k / 12); dEVE_s = PV_s - PV_BASE; WAL = sum t x principal / sum
'   principal; CPR averages weighted by the balance at the start of the
'   month; effective duration = (PV_PAR_DOWN - PV_PAR_UP) / (2 x PV_BASE x
'   parallel shock).
'
' UPDATED
'   2026-10-20
'==============================================================================
'

'------------------------------------------------------------------------------
' DECLARE
'------------------------------------------------------------------------------
    Dim N              As Long         'Projection months
    Dim Zero()         As Double       'Zero(scenario, m): zero rate at m / 12
    Dim Df()           As Double       'Df(scenario, m): discount factor at m / 12
    Dim Agg()          As Double       'Agg(scenario, month, field)
    Dim LoanPv()       As Double       'LoanPv(loan, scenario)
    Dim LoanWal()      As Double       'LoanWal(loan, scenario)
    Dim LoanDur()      As Double       'Macaulay duration, BASE
    Dim LoanCpr12()    As Double       'Average CPR first 12 months, BASE
    Dim SegCprW()      As Double       'Segment: CPR x balance, first 12 months, BASE
    Dim SegBalW()      As Double       'Segment: balance, first 12 months, BASE
    Dim Sched()        As Double       'Projection arrays of one loan
    Dim Prep()         As Double
    Dim Repr()         As Double
    Dim Intr()         As Double
    Dim BalStart()     As Double
    Dim BalEnd()       As Double
    Dim Cpr()          As Double
    Dim BaseCpr()      As Double       'BASE CPR path of the loan
    Dim Order(1 To SCEN_COUNT) As Long 'Projection order: BASE first
    Dim i              As Long         'Loan
    Dim o              As Long         'Position in Order
    Dim s              As Long         'Scenario
    Dim k              As Long         'Month
    Dim Months         As Long         'Months of one loan
    Dim AsOfMonth      As Long         'Calendar month of the as-of date
    Dim T              As Double       'Years
    Dim Prin           As Double       'Principal of a month
    Dim CashFlow       As Double       'Cash flow of a month
    Dim Pv             As Double       'PV of one loan and scenario
    Dim WalNum         As Double       'Sum of t x principal
    Dim PrinSum        As Double       'Sum of principal
    Dim DurNum         As Double       'Sum of t x discounted cash flow
    Dim Weight12       As Double       'Balance weight, first 12 months
    Dim Cpr12          As Double       'CPR x balance, first 12 months
    Dim ScaleBase      As Boolean      'BCBS_SA scaling for this scenario

'------------------------------------------------------------------------------
' GRID OF RATES AND DISCOUNT FACTORS
'------------------------------------------------------------------------------
    'Every rate the projection needs is at a whole number of months: the
    'cash-flow times k / 12 and the remaining maturities (RemMonths - k +
    '1) / 12. One grid per scenario serves both.
        N = 1
        For i = 1 To LoanCount
            If Loans(i).Used Then
                If Loans(i).RemMonths > N Then N = Loans(i).RemMonths
            End If
        Next i
        ReDim Zero(1 To SCEN_COUNT, 1 To N)
        ReDim Df(1 To SCEN_COUNT, 1 To N)
        For s = 1 To SCEN_COUNT
            For k = 1 To N
                T = k / 12#
                Zero(s, k) = ScenarioZero(s, T, Tenors, Rates, PointCount, Prm.ShockParallel, Prm.ShockShort, _
                                          Prm.ShockLong, Prm.Decay, Prm.ApplyFloor, Prm.FloorStart, Prm.FloorSlope)
                Df(s, k) = Exp(-Zero(s, k) * T)
            Next k
        Next s

'------------------------------------------------------------------------------
' PROJECT EVERY LOAN
'------------------------------------------------------------------------------
        ReDim Agg(1 To SCEN_COUNT, 1 To N, 1 To AGG_FIELDS)
        ReDim LoanPv(1 To LoanCount, 1 To SCEN_COUNT)
        ReDim LoanWal(1 To LoanCount, 1 To SCEN_COUNT)
        ReDim LoanDur(1 To LoanCount)
        ReDim LoanCpr12(1 To LoanCount)
        ReDim SegCprW(1 To SegCount)
        ReDim SegBalW(1 To SegCount)
        ReDim Sched(1 To N)
        ReDim Prep(1 To N)
        ReDim Repr(1 To N)
        ReDim Intr(1 To N)
        ReDim BalStart(1 To N)
        ReDim BalEnd(1 To N)
        ReDim Cpr(1 To N)
        ReDim BaseCpr(1 To N)
        Order(1) = SC_BASE
        Order(2) = SC_CONTRACT
        For s = SC_FIRST_SHOCK To SCEN_COUNT
            Order(s) = s
        Next s
        AsOfMonth = Month(Prm.AsOfDate)
        For i = 1 To LoanCount
            If Loans(i).Used Then
                For o = 1 To SCEN_COUNT
                    s = Order(o)
                    ScaleBase = (Prm.Mode = MODE_BCBS_SA And s >= SC_FIRST_SHOCK)
                    Months = ProjectLoan(s, Loans(i), Segs(Loans(i).SegmentIndex), ScaleBase, Gamma(s), AsOfMonth, _
                                         Season, Zero, BaseCpr, Sched, Prep, Repr, Intr, BalStart, BalEnd, Cpr)
                    If s = SC_BASE Then
                        For k = 1 To Months
                            BaseCpr(k) = Cpr(k)
                        Next k
                    End If
                    Pv = 0#
                    WalNum = 0#
                    PrinSum = 0#
                    DurNum = 0#
                    For k = 1 To Months
                        T = k / 12#
                        Prin = Sched(k) + Prep(k) + Repr(k)
                        CashFlow = Prin + Intr(k)
                        Pv = Pv + CashFlow * Df(s, k)
                        DurNum = DurNum + T * CashFlow * Df(s, k)
                        WalNum = WalNum + T * Prin
                        PrinSum = PrinSum + Prin
                        Agg(s, k, AG_SCHED) = Agg(s, k, AG_SCHED) + Sched(k)
                        Agg(s, k, AG_PREP) = Agg(s, k, AG_PREP) + Prep(k)
                        Agg(s, k, AG_REPR) = Agg(s, k, AG_REPR) + Repr(k)
                        Agg(s, k, AG_INTR) = Agg(s, k, AG_INTR) + Intr(k)
                        Agg(s, k, AG_CF) = Agg(s, k, AG_CF) + CashFlow
                        Agg(s, k, AG_BAL) = Agg(s, k, AG_BAL) + BalEnd(k)
                        Agg(s, k, AG_CPRW) = Agg(s, k, AG_CPRW) + Cpr(k) * BalStart(k)
                        Agg(s, k, AG_BALW) = Agg(s, k, AG_BALW) + BalStart(k)
                        Agg(s, k, AG_PV) = Agg(s, k, AG_PV) + CashFlow * Df(s, k)
                    Next k
                    LoanPv(i, s) = Pv
                    If PrinSum <> 0# Then LoanWal(i, s) = WalNum / PrinSum
                    If s = SC_BASE Then
                        If Pv <> 0# Then LoanDur(i) = DurNum / Pv
                        Weight12 = 0#
                        Cpr12 = 0#
                        For k = 1 To IIf(Months < 12, Months, 12)
                            Weight12 = Weight12 + BalStart(k)
                            Cpr12 = Cpr12 + Cpr(k) * BalStart(k)
                        Next k
                        If Weight12 <> 0# Then LoanCpr12(i) = Cpr12 / Weight12
                        SegCprW(Loans(i).SegmentIndex) = SegCprW(Loans(i).SegmentIndex) + Cpr12
                        SegBalW(Loans(i).SegmentIndex) = SegBalW(Loans(i).SegmentIndex) + Weight12
                    End If
                Next o
            End If
        Next i

'------------------------------------------------------------------------------
' WRITE
'------------------------------------------------------------------------------
        WriteResults Prm, Agg, N, LoanPv, LoanWal, LoanCpr12, Segs, SegCount, SegCprW, SegBalW, Loans, LoanCount, _
                     UsedCount
        WriteCashFlows Prm, Agg, N
        WriteGap Agg, N
        WriteScenarioCurves Prm, Tenors, Rates, PointCount
        WriteLoanCalc Loans, LoanCount, Segs, LoanPv, LoanWal, LoanDur, LoanCpr12

End Sub


'
'------------------------------------------------------------------------------
'
'                                   OUTPUTS
'
'------------------------------------------------------------------------------
'

Private Sub WriteResults( _
    ByRef Prm As PpmParams, _
    ByRef Agg() As Double, _
    ByVal N As Long, _
    ByRef LoanPv() As Double, _
    ByRef LoanWal() As Double, _
    ByRef LoanCpr12() As Double, _
    ByRef Segs() As PpmSegment, _
    ByVal SegCount As Long, _
    ByRef SegCprW() As Double, _
    ByRef SegBalW() As Double, _
    ByRef Loans() As PpmLoan, _
    ByVal LoanCount As Long, _
    ByVal UsedCount As Long)
'
'==============================================================================
'                                 WriteResults
'------------------------------------------------------------------------------
' PURPOSE
'   Write the scenario table, the summary and the segment table of
'   Results.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Sheet          As Worksheet    'Results
    Dim FirstRow       As Long         'First data row of a table
    Dim Block()        As Variant      'Rows to write
    Dim Pv(1 To SCEN_COUNT) As Double  'Book PV by scenario
    Dim s              As Long         'Scenario
    Dim k              As Long         'Month
    Dim i              As Long         'Loan
    Dim g              As Long         'Segment
    Dim Row            As Long         'Output row
    Dim WalNum         As Double       'Sum t x principal
    Dim PrinSum        As Double       'Sum principal
    Dim Cw             As Double       'CPR x balance
    Dim Bw             As Double       'Balance
    Dim PrepSum        As Double       'Prepayments
    Dim IntSum         As Double       'Interest
    Dim Balance        As Double       'Outstanding balance used
    Dim Worst          As Long         'Scenario of the lowest dEVE
    Dim Seg            As Variant      'Segment sums: loans, balance, PV by scenario, WAL x balance
    Dim LoansInSeg     As Long         'Used loans in the segment
    Dim SegBal         As Double       'Balance of the segment
    Dim SegWal         As Double       'Sum WAL x balance
    Dim SegPv(1 To SCEN_COUNT) As Double    'Segment PV by scenario
    Dim Ratio          As Double       'dEVE / Tier 1 of the worst scenario

        Set Sheet = GetSheet(SH_RESULTS)

    'Scenario table.
        For i = 1 To LoanCount
            If Loans(i).Used Then
                For s = 1 To SCEN_COUNT
                    Pv(s) = Pv(s) + LoanPv(i, s)
                Next s
                Balance = Balance + Loans(i).Balance
            End If
        Next i
        ReDim Block(1 To SCEN_COUNT, 1 To RS_NCOLS)
        For s = 1 To SCEN_COUNT
            WalNum = 0#
            PrinSum = 0#
            PrepSum = 0#
            IntSum = 0#
            Cw = 0#
            Bw = 0#
            For k = 1 To N
                WalNum = WalNum + k / 12# * (Agg(s, k, AG_SCHED) + Agg(s, k, AG_PREP) + Agg(s, k, AG_REPR))
                PrinSum = PrinSum + (Agg(s, k, AG_SCHED) + Agg(s, k, AG_PREP) + Agg(s, k, AG_REPR))
                PrepSum = PrepSum + Agg(s, k, AG_PREP)
                IntSum = IntSum + Agg(s, k, AG_INTR)
            Next k
            For k = 1 To IIf(N < 12, N, 12)
                Cw = Cw + Agg(s, k, AG_CPRW)
                Bw = Bw + Agg(s, k, AG_BALW)
            Next k
            Block(s, 1) = ScenarioCode(s)
            Block(s, 2) = ScenarioDescription(s, Prm.Mode)
            Block(s, 3) = Pv(s)
            Block(s, 4) = Pv(s) - Pv(SC_BASE)
            Block(s, 5) = (Pv(s) - Pv(SC_BASE)) / Prm.Tier1
            If PrinSum <> 0# Then Block(s, 6) = WalNum / PrinSum
            If Bw <> 0# Then Block(s, 7) = Cw / Bw
            Cw = 0#
            Bw = 0#
            For k = 1 To N
                Cw = Cw + Agg(s, k, AG_CPRW)
                Bw = Bw + Agg(s, k, AG_BALW)
            Next k
            If Bw <> 0# Then Block(s, 8) = Cw / Bw
            Block(s, 9) = PrepSum
            Block(s, 10) = IntSum
        Next s
        FirstRow = NamedCell(NM_RESULTS).Row + 1
        ClearTable Sheet, FirstRow, RS_NCOLS, SCEN_COUNT
        WriteTable Sheet, FirstRow, Block, SCEN_COUNT, RS_NCOLS
        FormatColumn Sheet, FirstRow, SCEN_COUNT, 3, "#,##0"
        FormatColumn Sheet, FirstRow, SCEN_COUNT, 4, "#,##0;[Red]-#,##0"
        FormatColumn Sheet, FirstRow, SCEN_COUNT, 5, "0.00%;[Red]-0.00%"
        FormatColumn Sheet, FirstRow, SCEN_COUNT, 6, "0.000"
        FormatColumn Sheet, FirstRow, SCEN_COUNT, 7, "0.00%"
        FormatColumn Sheet, FirstRow, SCEN_COUNT, 8, "0.00%"
        FormatColumn Sheet, FirstRow, SCEN_COUNT, 9, "#,##0"
        FormatColumn Sheet, FirstRow, SCEN_COUNT, 10, "#,##0"

    'Summary.
        Worst = SC_FIRST_SHOCK
        For s = SC_FIRST_SHOCK + 1 To SCEN_COUNT
            If Pv(s) < Pv(Worst) Then Worst = s
        Next s
        Ratio = (Pv(Worst) - Pv(SC_BASE)) / Prm.Tier1
        ReDim Block(1 To SM_ROWS, 1 To SM_NCOLS)
        Block(1, 1) = "Prepayment mode": Block(1, 2) = Prm.Mode
        Block(1, 3) = IIf(Prm.Mode = MODE_BCBS_SA, "Shocked CPR = min(1, gamma x base CPR)", _
                          "S-curve re-evaluated on each scenario curve")
        Block(2, 1) = "Loans used": Block(2, 2) = UsedCount: Block(2, 3) = "of " & LoanCount & " loan rows"
        Block(3, 1) = "Loans excluded": Block(3, 2) = LoanCount - UsedCount: Block(3, 3) = "See Checks and LoanCalc"
        Block(4, 1) = "Outstanding balance (used)": Block(4, 2) = Balance: Block(4, 3) = Prm.Ccy
        Block(5, 1) = "Projection months": Block(5, 2) = N: Block(5, 3) = "Longest remaining maturity"
        Block(6, 1) = "Worst scenario": Block(6, 2) = ScenarioCode(Worst): Block(6, 3) = "Lowest PV of the six shocks"
        Block(7, 1) = "Worst dEVE": Block(7, 2) = Pv(Worst) - Pv(SC_BASE): Block(7, 3) = Prm.Ccy
        Block(8, 1) = "Worst dEVE / Tier 1": Block(8, 2) = Ratio: Block(8, 3) = "Tier 1 = " & Format$(Prm.Tier1, "#,##0")
        Block(9, 1) = "Outlier indicator"
        If -Ratio > Prm.Outlier Then
            Block(9, 2) = "ABOVE " & Format$(Prm.Outlier, "0%") & " OF TIER 1"
        Else
            Block(9, 2) = "WITHIN " & Format$(Prm.Outlier, "0%") & " OF TIER 1"
        End If
        Block(9, 3) = "Loan book only: indicative, not the bank-level supervisory outlier test"
        Block(10, 1) = "Effective duration (parallel)"
        Block(10, 2) = (Pv(SC_PAR_DOWN) - Pv(SC_PAR_UP)) / (2# * Pv(SC_BASE) * Prm.ShockParallel)
        Block(10, 3) = "Years: (PV down - PV up) / (2 x PV base x parallel shock)"
        FirstRow = NamedCell(NM_SUMMARY).Row + 1
        ClearTable Sheet, FirstRow, SM_NCOLS, SM_ROWS
        WriteTable Sheet, FirstRow, Block, SM_ROWS, SM_NCOLS
        Sheet.Cells(FirstRow + 1, TableCol(2)).Resize(2, 1).NumberFormat = "#,##0"
        Sheet.Cells(FirstRow + 3, TableCol(2)).NumberFormat = "#,##0"
        Sheet.Cells(FirstRow + 4, TableCol(2)).NumberFormat = "0"
        Sheet.Cells(FirstRow + 6, TableCol(2)).NumberFormat = "#,##0;[Red]-#,##0"
        Sheet.Cells(FirstRow + 7, TableCol(2)).NumberFormat = "0.00%;[Red]-0.00%"
        Sheet.Cells(FirstRow + 9, TableCol(2)).NumberFormat = "0.000"

    'Segment table.
        FirstRow = NamedCell(NM_SEGRES).Row + 1
        ClearTable Sheet, FirstRow, SR_NCOLS
        ReDim Block(1 To SegCount + 1, 1 To SR_NCOLS)
        Row = 0
        For g = 1 To SegCount
            LoansInSeg = 0
            SegBal = 0#
            SegWal = 0#
            For s = 1 To SCEN_COUNT
                SegPv(s) = 0#
            Next s
            For i = 1 To LoanCount
                If Loans(i).Used And Loans(i).SegmentIndex = g Then
                    LoansInSeg = LoansInSeg + 1
                    SegBal = SegBal + Loans(i).Balance
                    SegWal = SegWal + LoanWal(i, SC_BASE) * Loans(i).Balance
                    For s = 1 To SCEN_COUNT
                        SegPv(s) = SegPv(s) + LoanPv(i, s)
                    Next s
                End If
            Next i
            If LoansInSeg > 0 Then
                Row = Row + 1
                Block(Row, 1) = Segs(g).Id
                Block(Row, 2) = LoansInSeg
                Block(Row, 3) = SegBal
                Block(Row, 4) = SegPv(SC_BASE)
                For s = SC_FIRST_SHOCK To SCEN_COUNT
                    Block(Row, 5 + s - SC_FIRST_SHOCK) = SegPv(s) - SegPv(SC_BASE)
                Next s
                Block(Row, 11) = SegWal / SegBal
                If SegBalW(g) <> 0# Then Block(Row, 12) = SegCprW(g) / SegBalW(g)
            End If
        Next g
        If Row > 0 Then
            WriteTable Sheet, FirstRow, Block, Row, SR_NCOLS
            FormatColumn Sheet, FirstRow, Row, 2, "0"
            FormatColumn Sheet, FirstRow, Row, 3, "#,##0"
            FormatColumn Sheet, FirstRow, Row, 4, "#,##0"
            For s = 5 To 10
                FormatColumn Sheet, FirstRow, Row, s, "#,##0;[Red]-#,##0"
            Next s
            FormatColumn Sheet, FirstRow, Row, 11, "0.000"
            FormatColumn Sheet, FirstRow, Row, 12, "0.00%"
        End If

End Sub


Private Function ScenarioDescription( _
    ByVal Scenario As Long, _
    ByVal Mode As String) _
    As String
'
'==============================================================================
'                             ScenarioDescription
'------------------------------------------------------------------------------
' PURPOSE
'   One-line description of a scenario for Results.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Suffix         As String    'Prepayment treatment of shocks

        If Mode = MODE_BCBS_SA Then Suffix = "; CPR = gamma x base" Else Suffix = "; S-curve on shocked curve"
        Select Case Scenario
            Case SC_CONTRACT: ScenarioDescription = "Contractual: no prepayment, base curve"
            Case SC_BASE: ScenarioDescription = "Behavioural, base curve"
            Case SC_PAR_UP: ScenarioDescription = "Parallel up" & Suffix
            Case SC_PAR_DOWN: ScenarioDescription = "Parallel down" & Suffix
            Case SC_STEEPENER: ScenarioDescription = "Steepener" & Suffix
            Case SC_FLATTENER: ScenarioDescription = "Flattener" & Suffix
            Case SC_SHORT_UP: ScenarioDescription = "Short rates up" & Suffix
            Case SC_SHORT_DOWN: ScenarioDescription = "Short rates down" & Suffix
        End Select

End Function


Private Sub WriteCashFlows( _
    ByRef Prm As PpmParams, _
    ByRef Agg() As Double, _
    ByVal N As Long)
'
'==============================================================================
'                                WriteCashFlows
'------------------------------------------------------------------------------
' PURPOSE
'   Write the monthly aggregated cash flows of every scenario.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Sheet          As Worksheet    'CashFlows
    Dim FirstRow       As Long         'First data row
    Dim Block()        As Variant      'Rows to write
    Dim k              As Long         'Month
    Dim s              As Long         'Shock scenario
    Dim c              As Long         'Column

        Set Sheet = GetSheet(SH_CASHFLOWS)
        FirstRow = NamedCell(NM_CASHFLOWS).Row + 1
        ClearTable Sheet, FirstRow, CF_NCOLS
        ReDim Block(1 To N, 1 To CF_NCOLS)
        For k = 1 To N
            Block(k, 1) = k
            Block(k, 2) = AddMonths(Prm.AsOfDate, k)
            Block(k, 3) = k / 12#
            Block(k, 4) = Agg(SC_BASE, k, AG_SCHED)
            Block(k, 5) = Agg(SC_BASE, k, AG_PREP)
            Block(k, 6) = Agg(SC_BASE, k, AG_REPR)
            Block(k, 7) = Agg(SC_BASE, k, AG_INTR)
            Block(k, 8) = Agg(SC_BASE, k, AG_CF)
            Block(k, 9) = Agg(SC_BASE, k, AG_BAL)
            If Agg(SC_BASE, k, AG_BALW) <> 0# Then Block(k, 10) = Agg(SC_BASE, k, AG_CPRW) / Agg(SC_BASE, k, AG_BALW)
            Block(k, 11) = Agg(SC_CONTRACT, k, AG_CF)
            Block(k, 12) = Agg(SC_CONTRACT, k, AG_BAL)
            For s = SC_FIRST_SHOCK To SCEN_COUNT
                c = 13 + 3 * (s - SC_FIRST_SHOCK)
                Block(k, c) = Agg(s, k, AG_CF)
                Block(k, c + 1) = Agg(s, k, AG_BAL)
                If Agg(s, k, AG_BALW) <> 0# Then Block(k, c + 2) = Agg(s, k, AG_CPRW) / Agg(s, k, AG_BALW)
            Next s
        Next k
        WriteTable Sheet, FirstRow, Block, N, CF_NCOLS
        FormatColumn Sheet, FirstRow, N, 1, "0"
        FormatColumn Sheet, FirstRow, N, 2, "yyyy\-mm\-dd"
        FormatColumn Sheet, FirstRow, N, 3, "0.000"
        For c = 4 To CF_NCOLS
            FormatColumn Sheet, FirstRow, N, c, "#,##0"
        Next c
        FormatColumn Sheet, FirstRow, N, 10, "0.00%"
        For s = SC_FIRST_SHOCK To SCEN_COUNT
            FormatColumn Sheet, FirstRow, N, 15 + 3 * (s - SC_FIRST_SHOCK), "0.00%"
        Next s

End Sub


Private Sub WriteGap( _
    ByRef Agg() As Double, _
    ByVal N As Long)
'
'==============================================================================
'                                   WriteGap
'------------------------------------------------------------------------------
' PURPOSE
'   Allocate the monthly cash flows to the 19 BCBS time buckets (upper
'   bound inclusive) and write the gap table with a total row.
'
' REFERENCE
'   BCBS d368 Table 1; tools/reference_model.py bucket_of.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Sheet          As Worksheet    'Gap
    Dim FirstRow       As Long         'First data row
    Dim Block()        As Variant      'Rows to write
    Dim Upper(1 To BUCKET_COUNT) As Double    'Upper bounds, years
    Dim Sums()         As Double       'Sums(bucket, column)
    Dim k              As Long         'Month
    Dim b              As Long         'Bucket
    Dim s              As Long         'Scenario
    Dim c              As Long         'Column
    Dim T              As Double       'Years

        Upper(1) = 1# / 365#: Upper(2) = 1# / 12#: Upper(3) = 3# / 12#: Upper(4) = 6# / 12#
        Upper(5) = 9# / 12#: Upper(6) = 1#: Upper(7) = 1.5: Upper(8) = 2#: Upper(9) = 3#
        Upper(10) = 4#: Upper(11) = 5#: Upper(12) = 6#: Upper(13) = 7#: Upper(14) = 8#
        Upper(15) = 9#: Upper(16) = 10#: Upper(17) = 15#: Upper(18) = 20#: Upper(19) = 1E+300
        ReDim Sums(1 To BUCKET_COUNT + 1, 4 To GP_NCOLS)
        For k = 1 To N
            T = k / 12#
            b = BUCKET_COUNT
            For c = 1 To BUCKET_COUNT
                If T <= Upper(c) + BUCKET_EPS Then
                    b = c
                    Exit For
                End If
            Next c
            Sums(b, 4) = Sums(b, 4) + (Agg(SC_CONTRACT, k, AG_SCHED) + Agg(SC_CONTRACT, k, AG_PREP) + _
                                       Agg(SC_CONTRACT, k, AG_REPR))
            Sums(b, 5) = Sums(b, 5) + (Agg(SC_BASE, k, AG_SCHED) + Agg(SC_BASE, k, AG_PREP) + Agg(SC_BASE, k, AG_REPR))
            Sums(b, 6) = Sums(b, 6) + Agg(SC_BASE, k, AG_CF)
            Sums(b, 7) = Sums(b, 7) + Agg(SC_BASE, k, AG_PV)
            For s = SC_FIRST_SHOCK To SCEN_COUNT
                Sums(b, 8 + s - SC_FIRST_SHOCK) = Sums(b, 8 + s - SC_FIRST_SHOCK) + Agg(s, k, AG_CF)
            Next s
        Next k
        ReDim Block(1 To BUCKET_COUNT + 1, 1 To GP_NCOLS)
        For b = 1 To BUCKET_COUNT
            Block(b, 1) = ListItem(BUCKET_LABELS, b)
            If b < BUCKET_COUNT Then Block(b, 2) = Upper(b)
            Block(b, 3) = Val(ListItem(BUCKET_MIDPOINTS, b))
            For c = 4 To GP_NCOLS
                Block(b, c) = Sums(b, c)
                Sums(BUCKET_COUNT + 1, c) = Sums(BUCKET_COUNT + 1, c) + Sums(b, c)
            Next c
        Next b
        Block(BUCKET_COUNT + 1, 1) = "Total"
        For c = 4 To GP_NCOLS
            Block(BUCKET_COUNT + 1, c) = Sums(BUCKET_COUNT + 1, c)
        Next c
        Set Sheet = GetSheet(SH_GAP)
        FirstRow = NamedCell(NM_GAP).Row + 1
        ClearTable Sheet, FirstRow, GP_NCOLS
        WriteTable Sheet, FirstRow, Block, BUCKET_COUNT + 1, GP_NCOLS
        FormatColumn Sheet, FirstRow, BUCKET_COUNT, 2, "0.0000"
        FormatColumn Sheet, FirstRow, BUCKET_COUNT, 3, "0.0000"
        For c = 4 To GP_NCOLS
            FormatColumn Sheet, FirstRow, BUCKET_COUNT + 1, c, "#,##0"
        Next c
        Sheet.Range(Sheet.Cells(FirstRow + BUCKET_COUNT, TableCol(1)), _
                    Sheet.Cells(FirstRow + BUCKET_COUNT, TableCol(GP_NCOLS))).Font.Bold = True

End Sub


Private Sub WriteScenarioCurves( _
    ByRef Prm As PpmParams, _
    ByRef Tenors() As Double, _
    ByRef Rates() As Double, _
    ByVal PointCount As Long)
'
'==============================================================================
'                             WriteScenarioCurves
'------------------------------------------------------------------------------
' PURPOSE
'   Write the zero rate of every scenario and the lower bound at the BCBS
'   bucket midpoints.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Sheet          As Worksheet    'ScenarioCurves
    Dim FirstRow       As Long         'First data row
    Dim Block()        As Variant      'Rows to write
    Dim b              As Long         'Bucket
    Dim s              As Long         'Scenario
    Dim T              As Double       'Years

        ReDim Block(1 To BUCKET_COUNT, 1 To SCV_NCOLS)
        For b = 1 To BUCKET_COUNT
            T = Val(ListItem(BUCKET_MIDPOINTS, b))
            Block(b, 1) = T
            For s = SC_BASE To SCEN_COUNT
                Block(b, s) = ScenarioZero(s, T, Tenors, Rates, PointCount, Prm.ShockParallel, Prm.ShockShort, _
                                           Prm.ShockLong, Prm.Decay, Prm.ApplyFloor, Prm.FloorStart, Prm.FloorSlope)
            Next s
            Block(b, SCV_NCOLS) = LowerBound(T, BaseZero(Tenors, Rates, PointCount, T), Prm.FloorStart, Prm.FloorSlope)
        Next b
        Set Sheet = GetSheet(SH_CURVES)
        FirstRow = NamedCell(NM_CURVES).Row + 1
        ClearTable Sheet, FirstRow, SCV_NCOLS
        WriteTable Sheet, FirstRow, Block, BUCKET_COUNT, SCV_NCOLS
        FormatColumn Sheet, FirstRow, BUCKET_COUNT, 1, "0.0000"
        For s = 2 To SCV_NCOLS
            FormatColumn Sheet, FirstRow, BUCKET_COUNT, s, "0.000%"
        Next s

End Sub


Private Sub WriteLoanCalc( _
    ByRef Loans() As PpmLoan, _
    ByVal LoanCount As Long, _
    ByRef Segs() As PpmSegment, _
    ByRef LoanPv() As Double, _
    ByRef LoanWal() As Double, _
    ByRef LoanDur() As Double, _
    ByRef LoanCpr12() As Double)
'
'==============================================================================
'                                WriteLoanCalc
'------------------------------------------------------------------------------
' PURPOSE
'   Write one row per loan row: status, months, PV by scenario, WAL,
'   duration, CPR and the findings.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Sheet          As Worksheet    'LoanCalc
    Dim FirstRow       As Long         'First data row
    Dim Block()        As Variant      'Rows to write
    Dim i              As Long         'Loan
    Dim s              As Long         'Scenario
    Dim c              As Long         'Column

        Set Sheet = GetSheet(SH_LOANCALC)
        FirstRow = NamedCell(NM_LOANCALC).Row + 1
        ClearTable Sheet, FirstRow, LC_NCOLS
        If LoanCount = 0 Then Exit Sub
        ReDim Block(1 To LoanCount, 1 To LC_NCOLS)
        For i = 1 To LoanCount
            With Loans(i)
                Block(i, 1) = .Id
                Block(i, 2) = .SegmentText
                If .Used Then
                    Block(i, 3) = "USED"
                    Block(i, 4) = .RemMonths
                    Block(i, 5) = .AgeMonths
                    Block(i, 6) = .EndMonths
                    For s = 1 To SCEN_COUNT
                        Block(i, 6 + s) = LoanPv(i, s)
                    Next s
                    Block(i, 15) = LoanWal(i, SC_CONTRACT)
                    Block(i, 16) = LoanWal(i, SC_BASE)
                    Block(i, 17) = LoanDur(i)
                    Block(i, 18) = LoanCpr12(i)
                Else
                    Block(i, 3) = "EXCLUDED"
                End If
                Block(i, 19) = .Messages
            End With
        Next i
        WriteTable Sheet, FirstRow, Block, LoanCount, LC_NCOLS
        For c = 4 To 6
            FormatColumn Sheet, FirstRow, LoanCount, c, "0"
        Next c
        For c = 7 To 14
            FormatColumn Sheet, FirstRow, LoanCount, c, "#,##0.00"
        Next c
        For c = 15 To 17
            FormatColumn Sheet, FirstRow, LoanCount, c, "0.000"
        Next c
        FormatColumn Sheet, FirstRow, LoanCount, 18, "0.00%"

End Sub
