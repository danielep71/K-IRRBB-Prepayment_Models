Attribute VB_Name = "CORE_Calibrate"
'==============================================================================
' MODULE: CORE_Calibrate
'------------------------------------------------------------------------------
' PURPOSE
'   Fit the S-curve of each segment (CPR min, CPR max, slope, midpoint) to
'   the observations on History by weighted least squares, with a
'   Nelder-Mead search on transformed parameters that keep 0 <= CPR min
'   <= CPR max <= 1 and slope > 0; write the fit to Calibration and, on
'   request, copy the fitted values to Segments.
'
' PUBLIC SURFACE
'   None outside this VBA project (Option Private Module). M_Main calls
'   Calibrate and ApplySegmentFits.
'
' DEPENDENCIES
'   CORE_Config, CORE_Util, CORE_Prepay (Logistic, SCurveCPR).
'
' STATE OWNERSHIP
'   No module state. Reads History and Segments, writes Calibration (and
'   Segments in ApplySegmentFits).
'
' ERROR POLICY
'   Invalid History rows are skipped and counted in the status line; a
'   segment with fewer than MIN_CAL_OBS observations is reported, not
'   fitted. A broken workbook raises from CORE_Util.
'
' REFERENCE
'   tools/reference_model.py calibrate and nelder_mead: the same start,
'   steps (0.5, 0.5, 0.25, 0.005), coefficients (1, 2, 0.5, 0.5),
'   termination test and one restart from the first optimum.
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
' MODULE CONSTANTS
'------------------------------------------------------------------------------
        Private Const DIMS          As Long = 4      'Parameters fitted
        Private Const STATUS_OK     As String = "CONVERGED"
        Private Const STATUS_MAXIT  As String = "MAX ITERATIONS"


'
'------------------------------------------------------------------------------
'
'                                 CALIBRATION
'
'------------------------------------------------------------------------------
'

Public Function Calibrate( _
    ByRef StatusLine As String) _
    As Long
'
'==============================================================================
'                                  Calibrate
'------------------------------------------------------------------------------
' PURPOSE
'   Fit every segment of Segments that has observations on History and
'   write the Calibration sheet.
'
' RETURNS
'   The number of segments fitted. StatusLine: summary for C4.
'
' UPDATED
'   2026-10-20
'==============================================================================
'

'------------------------------------------------------------------------------
' DECLARE
'------------------------------------------------------------------------------
    Dim SegIds()       As String       'Segment IDs in Segments order
    Dim SegCount       As Long         'Segments
    Dim Hist           As Variant      'History block
    Dim HistRows       As Long         'History rows read
    Dim RowOk()        As Boolean      'History row valid
    Dim Skipped        As Long         'Invalid History rows
    Dim FirstSkip      As String       'First invalid row and reason
    Dim Xs()           As Double       'Incentives of one segment
    Dim Ys()           As Double       'Observed CPR
    Dim Ws()           As Double       'Weights
    Dim n              As Long         'Observations of one segment
    Dim g              As Long         'Segment
    Dim r              As Long         'History row
    Dim Fitted         As Long         'Segments fitted
    Dim Out()          As Variant      'Calibration rows
    Dim OutRows        As Long         'Calibration rows written
    Dim Curve()        As Variant      'Curve grid
    Dim CurveCols      As Long         'Curve columns used
    Dim Fit(1 To 9)    As Variant      'Result of one fit
    Dim i              As Long         'Grid point
    Dim Sheet          As Worksheet    'Calibration
    Dim FirstRow       As Long         'First data row
    Dim Reason         As String       'Why a History row is invalid
    Dim HistFirst      As Long         'First History data row

'------------------------------------------------------------------------------
' READ
'------------------------------------------------------------------------------
        SegCount = ReadSegmentIds(SegIds)
        HistFirst = NamedCell(NM_HISTORY).Row + 1
        HistRows = LastTableRow(GetSheet(SH_HISTORY), HistFirst, HS_NCOLS) - HistFirst + 1
        If HistRows > 0 Then
            Hist = ReadTable(GetSheet(SH_HISTORY), HistFirst, HistFirst + HistRows - 1, HS_NCOLS)
            ReDim RowOk(1 To HistRows)
            For r = 1 To HistRows
                Reason = HistoryProblem(Hist, r)
                RowOk(r) = (Len(Reason) = 0)
                If Not RowOk(r) And Not RowIsBlank(Hist, r, HS_NCOLS) Then
                    Skipped = Skipped + 1
                    If Len(FirstSkip) = 0 Then FirstSkip = "row " & (HistFirst + r - 1) & ": " & Reason
                End If
            Next r
        End If

'------------------------------------------------------------------------------
' FIT EVERY SEGMENT WITH OBSERVATIONS
'------------------------------------------------------------------------------
        If SegCount > 0 Then ReDim Out(1 To SegCount, 1 To CB_NCOLS)
        ReDim Curve(1 To CC_POINTS, 1 To CC_SERIES + 1)
        For i = 1 To CC_POINTS
            Curve(i, 1) = CC_FROM + CC_STEP * (i - 1)
        Next i
        For g = 1 To SegCount
            n = 0
            If HistRows > 0 Then
                ReDim Xs(1 To HistRows)
                ReDim Ys(1 To HistRows)
                ReDim Ws(1 To HistRows)
                For r = 1 To HistRows
                    If RowOk(r) Then
                        If TextValue(Hist(r, HS_SEG)) = SegIds(g) Then
                            n = n + 1
                            Xs(n) = CDbl(Hist(r, HS_INCENTIVE))
                            Ys(n) = CDbl(Hist(r, HS_CPR))
                            Ws(n) = CDbl(Hist(r, HS_WEIGHT))
                        End If
                    End If
                Next r
            End If
            If n > 0 And OutRows < CB_MAX_ROWS Then
                OutRows = OutRows + 1
                Out(OutRows, 1) = SegIds(g)
                Out(OutRows, 2) = n
                If n < MIN_CAL_OBS Then
                    Out(OutRows, 10) = "TOO FEW OBSERVATIONS (minimum " & MIN_CAL_OBS & ")"
                Else
                    FitSegment Xs, Ys, Ws, n, Fit
                    Out(OutRows, 3) = Fit(1)
                    Out(OutRows, 4) = Fit(2)
                    Out(OutRows, 5) = Fit(3)
                    Out(OutRows, 6) = Fit(4)
                    Out(OutRows, 7) = Fit(5)
                    Out(OutRows, 8) = Fit(6)
                    Out(OutRows, 9) = Fit(7)
                    Out(OutRows, 10) = Fit(8)
                    Fitted = Fitted + 1
                    If CurveCols < CC_SERIES Then
                        CurveCols = CurveCols + 1
                        For i = 1 To CC_POINTS
                            Curve(i, CurveCols + 1) = SCurveCPR(CDbl(Curve(i, 1)), CDbl(Fit(1)), CDbl(Fit(2)), _
                                                                CDbl(Fit(3)), CDbl(Fit(4)))
                        Next i
                    End If
                End If
            End If
        Next g

'------------------------------------------------------------------------------
' WRITE
'------------------------------------------------------------------------------
        Set Sheet = GetSheet(SH_CALIB)
        FirstRow = NamedCell(NM_CALIB).Row + 1
        ClearTable Sheet, FirstRow, CB_NCOLS, CB_MAX_ROWS
        If OutRows > 0 Then
            WriteTable Sheet, FirstRow, Out, OutRows, CB_NCOLS
            FormatColumn Sheet, FirstRow, OutRows, 2, "0"
            FormatColumn Sheet, FirstRow, OutRows, 3, "0.0000%"
            FormatColumn Sheet, FirstRow, OutRows, 4, "0.0000%"
            FormatColumn Sheet, FirstRow, OutRows, 5, "0.000"
            FormatColumn Sheet, FirstRow, OutRows, 6, "0.0000%"
            FormatColumn Sheet, FirstRow, OutRows, 7, "0.0000%"
            FormatColumn Sheet, FirstRow, OutRows, 8, "0.0000"
            FormatColumn Sheet, FirstRow, OutRows, 9, "0"
        End If
        WriteCurveGrid Sheet, Out, OutRows, Curve, CurveCols
        ShowFittedSeries Sheet, CurveCols
        StatusLine = "Calibrated " & Format$(Now, "yyyy-mm-dd hh:mm:ss") & " | " & Fitted & " segments fitted | " & _
                     Skipped & " History rows skipped"
        If Skipped > 0 Then StatusLine = StatusLine & " (first: " & FirstSkip & ")"
        Sheet.Range(STATUS_CELL).Value = StatusLine
        Calibrate = Fitted

End Function


Private Sub WriteCurveGrid( _
    ByVal Sheet As Worksheet, _
    ByRef Out() As Variant, _
    ByVal OutRows As Long, _
    ByRef Curve() As Variant, _
    ByVal CurveCols As Long)
'
'==============================================================================
'                                WriteCurveGrid
'------------------------------------------------------------------------------
' PURPOSE
'   Write the fitted CPR on the incentive grid, one column per fitted
'   segment, with the segment IDs as headers (read by the chart).
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim HeaderRow      As Long      'Header row of the grid
    Dim c              As Long      'Series column
    Dim r              As Long      'Calibration row
    Dim Headers()      As Variant   'Headers

        HeaderRow = NamedCell(NM_CALCURVE).Row
        Sheet.Range(Sheet.Cells(HeaderRow, TableCol(2)), Sheet.Cells(HeaderRow, TableCol(CC_SERIES + 1))).ClearContents
        ClearTable Sheet, HeaderRow + 1, CC_SERIES + 1
        ReDim Headers(1 To 1, 1 To CC_SERIES)
        c = 0
        For r = 1 To OutRows
            If Not IsEmpty(Out(r, 3)) And c < CC_SERIES Then
                c = c + 1
                Headers(1, c) = Out(r, 1)
            End If
        Next r
        If c > 0 Then
            Sheet.Range(Sheet.Cells(HeaderRow, TableCol(2)), Sheet.Cells(HeaderRow, TableCol(CC_SERIES + 1))).Value = Headers
        End If
        WriteTable Sheet, HeaderRow + 1, Curve, CC_POINTS, CurveCols + 1
        FormatColumn Sheet, HeaderRow + 1, CC_POINTS, 1, "0.00%"
        For c = 2 To CurveCols + 1
            FormatColumn Sheet, HeaderRow + 1, CC_POINTS, c, "0.00%"
        Next c

End Sub


Private Sub ShowFittedSeries( _
    ByVal Sheet As Worksheet, _
    ByVal SeriesCount As Long)
'
'==============================================================================
'                               ShowFittedSeries
'------------------------------------------------------------------------------
' PURPOSE
'   Show only the chart series that hold a fitted curve, so that the
'   legend does not list the empty columns of the grid. The series are
'   filtered, not deleted, so the next calibration can show them again.
'
' ERROR POLICY
'   Cosmetic and best effort: on a host without Chart.FullSeriesCollection
'   or IsFiltered (Excel 2010, the headless test host) every series stays
'   visible and the calibration result is unchanged.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Shown          As Object    'Chart of the sheet
    Dim i              As Long      'Series

        On Error GoTo Done
        If Sheet.ChartObjects.Count = 0 Then Exit Sub
        Set Shown = Sheet.ChartObjects(1).Chart
        For i = 1 To Shown.FullSeriesCollection.Count
            Shown.FullSeriesCollection(i).IsFiltered = (i > SeriesCount)
        Next i
Done:

End Sub


Private Function HistoryProblem( _
    ByRef Hist As Variant, _
    ByVal RowIndex As Long) _
    As String
'
'==============================================================================
'                                HistoryProblem
'------------------------------------------------------------------------------
' PURPOSE
'   Why a History row cannot be used; "" when it can.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        If RowIsBlank(Hist, RowIndex, HS_NCOLS) Then
            HistoryProblem = "blank"
        ElseIf Len(TextValue(Hist(RowIndex, HS_SEG))) = 0 Then
            HistoryProblem = "SegmentID is blank"
        ElseIf Not IsNumberValue(Hist(RowIndex, HS_INCENTIVE)) Then
            HistoryProblem = "incentive is not a number"
        ElseIf Not IsNumberValue(Hist(RowIndex, HS_CPR)) Then
            HistoryProblem = "observed CPR is not a number"
        ElseIf Hist(RowIndex, HS_CPR) < 0 Or Hist(RowIndex, HS_CPR) > 1 Then
            HistoryProblem = "observed CPR outside 0 to 1"
        ElseIf Not IsNumberValue(Hist(RowIndex, HS_WEIGHT)) Then
            HistoryProblem = "weight is not a number"
        ElseIf Hist(RowIndex, HS_WEIGHT) <= 0 Then
            HistoryProblem = "weight must be > 0"
        Else
            HistoryProblem = ""
        End If

End Function


Private Function ReadSegmentIds( _
    ByRef SegIds() As String) _
    As Long
'
'==============================================================================
'                                ReadSegmentIds
'------------------------------------------------------------------------------
' PURPOSE
'   Read the non-blank, distinct SegmentIDs of Segments, in sheet order.
'
' RETURNS
'   The number of IDs.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Sheet          As Worksheet    'Segments
    Dim FirstRow       As Long         'First data row
    Dim LastRow        As Long         'Last data row
    Dim Block          As Variant      'Values
    Dim r              As Long         'Row
    Dim i              As Long         'Earlier ID
    Dim n              As Long         'IDs read
    Dim Id             As String       'One ID
    Dim Known          As Boolean      'ID already read

        Set Sheet = GetSheet(SH_SEGMENTS)
        FirstRow = NamedCell(NM_SEGMENTS).Row + 1
        LastRow = LastTableRow(Sheet, FirstRow, 1)
        ReadSegmentIds = 0
        If LastRow < FirstRow Then Exit Function
        Block = ReadTable(Sheet, FirstRow, LastRow, 1)
        ReDim SegIds(1 To LastRow - FirstRow + 1)
        For r = 1 To LastRow - FirstRow + 1
            Id = TextValue(Block(r, 1))
            If Len(Id) > 0 Then
                Known = False
                For i = 1 To n
                    If SegIds(i) = Id Then Known = True
                Next i
                If Not Known Then
                    n = n + 1
                    SegIds(n) = Id
                End If
            End If
        Next r
        ReadSegmentIds = n

End Function


'
'------------------------------------------------------------------------------
'
'                                   FITTING
'
'------------------------------------------------------------------------------
'

Public Sub FitSegment( _
    ByRef Xs() As Double, _
    ByRef Ys() As Double, _
    ByRef Ws() As Double, _
    ByVal n As Long, _
    ByRef Fit() As Variant)
'
'==============================================================================
'                                  FitSegment
'------------------------------------------------------------------------------
' PURPOSE
'   Fit the S-curve to n weighted observations.
'
' INPUTS
'   Xs: incentives, decimal. Ys: observed annual CPR, 0 to 1. Ws: weights,
'   > 0. n >= 1.
'
' RETURNS
'   Fit(1 To 8): CPR min, CPR max, slope, midpoint, weighted RMSE,
'   R-squared (Empty when the observations do not vary), iterations of
'   both searches, status.
'
' REFERENCE
'   tools/reference_model.py calibrate.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim X0(0 To DIMS - 1)   As Double    'Start
    Dim Steps(0 To DIMS - 1) As Double   'Initial simplex steps
    Dim Best(0 To DIMS - 1) As Double    'Optimum
    Dim BestValue      As Double         'Objective at the optimum
    Dim Iter1          As Long           'Iterations, first search
    Dim Iter2          As Long           'Iterations, restart
    Dim Ok1            As Boolean        'First search converged
    Dim Ok2            As Boolean        'Restart converged
    Dim YMin           As Double         'Lowest observation, bounded
    Dim YMax           As Double         'Highest observation, bounded
    Dim SumXW          As Double         'Sum x x w
    Dim SumW           As Double         'Sum w
    Dim SumYW          As Double         'Sum y x w
    Dim Sst            As Double         'Weighted total sum of squares / sum w
    Dim YBar           As Double         'Weighted mean observation
    Dim CprMin         As Double         'Fitted parameters
    Dim CprMax         As Double
    Dim Slope          As Double
    Dim Midpoint       As Double
    Dim i              As Long           'Observation
    Dim d              As Long           'Dimension

    'Start: CPR min and max from the observed range, slope 100, midpoint
    'at the weighted mean incentive.
        YMin = Ys(1)
        YMax = Ys(1)
        For i = 2 To n
            If Ys(i) < YMin Then YMin = Ys(i)
            If Ys(i) > YMax Then YMax = Ys(i)
        Next i
        If YMin < 0.001 Then YMin = 0.001
        If YMin > 0.95 Then YMin = 0.95
        If YMax > 0.999 Then YMax = 0.999
        If YMax < YMin + 0.01 Then YMax = YMin + 0.01
        For i = 1 To n
            SumXW = SumXW + Xs(i) * Ws(i)
            SumW = SumW + Ws(i)
        Next i
        X0(0) = Log(YMin / (1# - YMin))
        X0(1) = Log(((YMax - YMin) / (1# - YMin)) / (1# - (YMax - YMin) / (1# - YMin)))
        X0(2) = Log(NM_START_SLOPE)
        X0(3) = SumXW / SumW
        Steps(0) = 0.5: Steps(1) = 0.5: Steps(2) = 0.25: Steps(3) = 0.005

    'Search, then restart once from the optimum.
        NelderMead X0, Steps, Xs, Ys, Ws, n, Best, BestValue, Iter1, Ok1
        For d = 0 To DIMS - 1
            X0(d) = Best(d)
        Next d
        NelderMead X0, Steps, Xs, Ys, Ws, n, Best, BestValue, Iter2, Ok2
        Unpack Best, CprMin, CprMax, Slope, Midpoint

    'Fit statistics.
        For i = 1 To n
            SumYW = SumYW + Ys(i) * Ws(i)
        Next i
        YBar = SumYW / SumW
        For i = 1 To n
            Sst = Sst + Ws(i) * (Ys(i) - YBar) ^ 2
        Next i
        Sst = Sst / SumW
        Fit(1) = CprMin
        Fit(2) = CprMax
        Fit(3) = Slope
        Fit(4) = Midpoint
        Fit(5) = Sqr(BestValue)
        If Sst > 0# Then Fit(6) = 1# - BestValue / Sst Else Fit(6) = Empty
        Fit(7) = Iter1 + Iter2
        If Ok1 And Ok2 Then Fit(8) = STATUS_OK Else Fit(8) = STATUS_MAXIT

End Sub


Private Sub Unpack( _
    ByRef Theta() As Double, _
    ByRef CprMin As Double, _
    ByRef CprMax As Double, _
    ByRef Slope As Double, _
    ByRef Midpoint As Double)
'
'==============================================================================
'                                    Unpack
'------------------------------------------------------------------------------
' PURPOSE
'   Map the unconstrained search vector to the S-curve parameters:
'   CPR min = L(a), CPR max = CPR min + (1 - CPR min) x L(b), slope =
'   exp(c), midpoint = d.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
        CprMin = Logistic(Theta(0))
        CprMax = CprMin + (1# - CprMin) * Logistic(Theta(1))
        Slope = Exp(Theta(2))
        Midpoint = Theta(3)

End Sub


Private Function Objective( _
    ByRef Theta() As Double, _
    ByRef Xs() As Double, _
    ByRef Ys() As Double, _
    ByRef Ws() As Double, _
    ByVal n As Long) _
    As Double
'
'==============================================================================
'                                  Objective
'------------------------------------------------------------------------------
' PURPOSE
'   Weighted mean squared error of the S-curve: sum w (y - f(x))^2 / sum w.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim CprMin         As Double    'Parameters
    Dim CprMax         As Double
    Dim Slope          As Double
    Dim Midpoint       As Double
    Dim Sse            As Double    'Weighted sum of squared errors
    Dim SumW           As Double    'Sum of weights
    Dim E              As Double    'Residual
    Dim i              As Long      'Observation

        Unpack Theta, CprMin, CprMax, Slope, Midpoint
        For i = 1 To n
            E = Ys(i) - SCurveCPR(Xs(i), CprMin, CprMax, Slope, Midpoint)
            Sse = Sse + Ws(i) * E * E
            SumW = SumW + Ws(i)
        Next i
        Objective = Sse / SumW

End Function


Private Sub NelderMead( _
    ByRef X0() As Double, _
    ByRef Steps() As Double, _
    ByRef Xs() As Double, _
    ByRef Ys() As Double, _
    ByRef Ws() As Double, _
    ByVal n As Long, _
    ByRef Best() As Double, _
    ByRef BestValue As Double, _
    ByRef Iterations As Long, _
    ByRef Converged As Boolean)
'
'==============================================================================
'                                  NelderMead
'------------------------------------------------------------------------------
' PURPOSE
'   Minimise the objective from X0 with the Nelder-Mead simplex method:
'   reflection 1, expansion 2, contraction 0.5, shrink 0.5.
'
' RETURNS
'   Best and BestValue: the first vertex after the last sort. Iterations
'   performed; Converged False when NM_MAX_ITER was reached.
'
' REFERENCE
'   tools/reference_model.py nelder_mead, operation for operation.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Pts(0 To DIMS, 0 To DIMS - 1) As Double    'Simplex vertices
    Dim Vals(0 To DIMS) As Double                  'Objective at the vertices
    Dim Cen(0 To DIMS - 1) As Double               'Centroid of the best DIMS
    Dim Xr(0 To DIMS - 1) As Double                'Reflected point
    Dim Xe(0 To DIMS - 1) As Double                'Expanded point
    Dim Xc(0 To DIMS - 1) As Double                'Contracted point
    Dim Tmp(0 To DIMS - 1) As Double               'Point for the objective
    Dim Fr             As Double                   'Objective at Xr
    Dim Fe             As Double                   'Objective at Xe
    Dim Fc             As Double                   'Objective at Xc
    Dim Accept         As Boolean                  'Contraction accepted
    Dim i              As Long                     'Vertex
    Dim j              As Long                     'Vertex during the sort
    Dim d              As Long                     'Dimension
    Dim It             As Long                     'Iterations
    Dim Swap           As Double                   'Swap holder

    'Initial simplex.
        For d = 0 To DIMS - 1
            Pts(0, d) = X0(d)
        Next d
        For i = 1 To DIMS
            For d = 0 To DIMS - 1
                Pts(i, d) = X0(d)
            Next d
            Pts(i, i - 1) = Pts(i, i - 1) + Steps(i - 1)
        Next i
        For i = 0 To DIMS
            For d = 0 To DIMS - 1
                Tmp(d) = Pts(i, d)
            Next d
            Vals(i) = Objective(Tmp, Xs, Ys, Ws, n)
        Next i

        It = 0
        Do While It < NM_MAX_ITER
        'Insertion sort, ascending and stable.
            For i = 1 To DIMS
                j = i
                Do While j > 0
                    If Vals(j - 1) <= Vals(j) Then Exit Do
                    Swap = Vals(j - 1): Vals(j - 1) = Vals(j): Vals(j) = Swap
                    For d = 0 To DIMS - 1
                        Swap = Pts(j - 1, d): Pts(j - 1, d) = Pts(j, d): Pts(j, d) = Swap
                    Next d
                    j = j - 1
                Loop
            Next i
            If Vals(DIMS) - Vals(0) <= NM_TOL * (Abs(Vals(0)) + 1E-30) Then Exit Do
            It = It + 1
        'Centroid of all vertices but the worst.
            For d = 0 To DIMS - 1
                Cen(d) = 0#
                For i = 0 To DIMS - 1
                    Cen(d) = Cen(d) + Pts(i, d)
                Next i
                Cen(d) = Cen(d) / DIMS
                Xr(d) = Cen(d) + 1# * (Cen(d) - Pts(DIMS, d))
            Next d
            Fr = Objective(Xr, Xs, Ys, Ws, n)
            If Fr < Vals(0) Then
                For d = 0 To DIMS - 1
                    Xe(d) = Cen(d) + 2# * (Xr(d) - Cen(d))
                Next d
                Fe = Objective(Xe, Xs, Ys, Ws, n)
                If Fe < Fr Then
                    For d = 0 To DIMS - 1
                        Pts(DIMS, d) = Xe(d)
                    Next d
                    Vals(DIMS) = Fe
                Else
                    For d = 0 To DIMS - 1
                        Pts(DIMS, d) = Xr(d)
                    Next d
                    Vals(DIMS) = Fr
                End If
            ElseIf Fr < Vals(DIMS - 1) Then
                For d = 0 To DIMS - 1
                    Pts(DIMS, d) = Xr(d)
                Next d
                Vals(DIMS) = Fr
            Else
                If Fr < Vals(DIMS) Then
                    For d = 0 To DIMS - 1
                        Xc(d) = Cen(d) + 0.5 * (Xr(d) - Cen(d))
                    Next d
                    Fc = Objective(Xc, Xs, Ys, Ws, n)
                    Accept = (Fc <= Fr)
                Else
                    For d = 0 To DIMS - 1
                        Xc(d) = Cen(d) + 0.5 * (Pts(DIMS, d) - Cen(d))
                    Next d
                    Fc = Objective(Xc, Xs, Ys, Ws, n)
                    Accept = (Fc < Vals(DIMS))
                End If
                If Accept Then
                    For d = 0 To DIMS - 1
                        Pts(DIMS, d) = Xc(d)
                    Next d
                    Vals(DIMS) = Fc
                Else
                    For i = 1 To DIMS
                        For d = 0 To DIMS - 1
                            Pts(i, d) = Pts(0, d) + 0.5 * (Pts(i, d) - Pts(0, d))
                            Tmp(d) = Pts(i, d)
                        Next d
                        Vals(i) = Objective(Tmp, Xs, Ys, Ws, n)
                    Next i
                End If
            End If
        Loop
        For d = 0 To DIMS - 1
            Best(d) = Pts(0, d)
        Next d
        BestValue = Vals(0)
        Iterations = It
        Converged = (It < NM_MAX_ITER)

End Sub


'
'------------------------------------------------------------------------------
'
'                                    APPLY
'
'------------------------------------------------------------------------------
'

Public Function ApplySegmentFits( _
    ByRef StatusLine As String) _
    As Long
'
'==============================================================================
'                               ApplySegmentFits
'------------------------------------------------------------------------------
' PURPOSE
'   Copy CPR min, CPR max, slope and midpoint of every CONVERGED row of
'   Calibration to the matching segment on Segments.
'
' RETURNS
'   The number of segments updated. StatusLine: summary for C4.
'
' UPDATED
'   2026-10-20
'==============================================================================
'
    Dim Cal            As Worksheet    'Calibration
    Dim Seg            As Worksheet    'Segments
    Dim CalFirst       As Long         'First Calibration row
    Dim CalLast        As Long         'Last Calibration row
    Dim SegFirst       As Long         'First Segments row
    Dim SegLast        As Long         'Last Segments row
    Dim CalBlock       As Variant      'Calibration values
    Dim SegBlock       As Variant      'Segment IDs
    Dim r              As Long         'Calibration row
    Dim g              As Long         'Segment row
    Dim Updated        As Long         'Segments updated
    Dim Values(1 To 1, 1 To 4) As Variant    'Fitted values

        Set Cal = GetSheet(SH_CALIB)
        Set Seg = GetSheet(SH_SEGMENTS)
        CalFirst = NamedCell(NM_CALIB).Row + 1
        CalLast = LastTableRow(Cal, CalFirst, CB_NCOLS)
        If CalLast > CalFirst + CB_MAX_ROWS - 1 Then CalLast = CalFirst + CB_MAX_ROWS - 1
        SegFirst = NamedCell(NM_SEGMENTS).Row + 1
        SegLast = LastTableRow(Seg, SegFirst, 1)
        If CalLast >= CalFirst And SegLast >= SegFirst Then
            CalBlock = ReadTable(Cal, CalFirst, CalLast, CB_NCOLS)
            SegBlock = ReadTable(Seg, SegFirst, SegLast, 1)
            For r = 1 To CalLast - CalFirst + 1
                If TextValue(CalBlock(r, 10)) = STATUS_OK Then
                    For g = 1 To SegLast - SegFirst + 1
                        If TextValue(SegBlock(g, 1)) = TextValue(CalBlock(r, 1)) Then
                            Values(1, 1) = CalBlock(r, 3)
                            Values(1, 2) = CalBlock(r, 4)
                            Values(1, 3) = CalBlock(r, 5)
                            Values(1, 4) = CalBlock(r, 6)
                            Seg.Range(Seg.Cells(SegFirst + g - 1, TableCol(SG_CPRMIN)), _
                                      Seg.Cells(SegFirst + g - 1, TableCol(SG_MID))).Value = Values
                            Updated = Updated + 1
                            Exit For
                        End If
                    Next g
                End If
            Next r
        End If
        StatusLine = "Applied " & Format$(Now, "yyyy-mm-dd hh:mm:ss") & " | " & Updated & _
                     " segments updated on Segments; press Run model to use them."
        Cal.Range(STATUS_CELL).Value = StatusLine
        ApplySegmentFits = Updated

End Function
