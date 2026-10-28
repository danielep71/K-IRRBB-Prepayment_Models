Attribute VB_Name = "CORE_Dataset"
'==============================================================================
' MODULE: CORE_Dataset
'------------------------------------------------------------------------------
' PURPOSE
'   The accepted dataset of the Excel session (docs/WORKBOOK_CONTRACT.md,
'   W7): the results of the last accepted import, kept in memory until the
'   next accepted import. Only an import without error is committed, so a
'   rejected import leaves the accepted dataset unchanged (data contract,
'   all-or-nothing import; DATA-REJECT-01).
'
' USAGE
'   CORE_DatasetCommit copies the results of the last CORE_ReadImport, with
'   the run ID and the size and SHA-256 of each file. CORE_DatasetRunId is
'   "" until a dataset is committed. CORE_DatasetResult returns, as a
'   1-based (n x k) array or Empty:
'     counts         file, size_bytes, sha256, rows_read, rows_accepted,
'                    rows_outside_window, loans (table Import_Counts)
'     outcomes       as_of_date (t-1), segment, currency, outcome,
'                    loan_months, sum of the balances at t-1, by key
'                    (table Import_Outcomes, W12)
'     loan_outcomes, totals, comparisons, warnings, gaps, loan_months
'                    as CORE_ImportResult ("outcomes" for loan_outcomes)
'
' DEPENDENCIES
'   CORE_Import, CORE_Parse. Arrays and scalars only; no workbook, UI, file
'   or COM access.
'==============================================================================

Option Explicit
Option Private Module

Private Const KINDS As String = "|counts|outcomes|loan_outcomes|totals|comparisons|warnings|gaps|loan_months|"

Private mRunId As String
Private mResults(1 To 8) As Variant    'by the position of the kind in KINDS

Public Sub CORE_DatasetCommit(ByVal RunId As String, ByVal Sizes As Variant, ByVal Hashes As Variant)
    'Sizes and Hashes are 0-based arrays for loans.csv, loan_panel.csv and
    'market_rates.csv. Raises when the last import has an error. Every
    'result is built before the first one is replaced.
    Dim Results(1 To 8) As Variant, I As Long
    If Not IsEmpty(CORE_ImportResult("errors")) Then
        Err.Raise vbObjectError + 1301, "CORE_Dataset", "Only an import without error can be committed"
    End If
    Results(1) = Counts(Sizes, Hashes)
    Results(2) = Summary(CORE_ImportResult("outcomes"))
    Results(3) = CORE_ImportResult("outcomes")
    Results(4) = CORE_ImportResult("totals")
    Results(5) = CORE_ImportResult("comparisons")
    Results(6) = CORE_ImportResult("warnings")
    Results(7) = CORE_ImportResult("gaps")
    Results(8) = CORE_ImportResult("loan_months")
    For I = 1 To 8
        mResults(I) = Results(I)
    Next I
    mRunId = RunId
End Sub

Public Function CORE_DatasetRunId() As String
    CORE_DatasetRunId = mRunId
End Function

Public Function CORE_DatasetResult(ByVal Kind As String) As Variant
    'Empty until a dataset is committed.
    Dim At As Long
    At = InStr(1, KINDS, "|" & Kind & "|", vbBinaryCompare)
    If Len(Kind) = 0 Or InStr(1, Kind, "|") > 0 Or At = 0 Then
        Err.Raise vbObjectError + 1302, "CORE_Dataset", "Unknown result: " & Kind
    End If
    'The number of separators up to the kind is its position.
    CORE_DatasetResult = mResults(UBound(Split(Left$(KINDS, At), "|")))
End Function

Private Function Counts(ByVal Sizes As Variant, ByVal Hashes As Variant) As Variant
    'The import counts with the size and SHA-256 of each file inserted.
    Dim Table As Variant, Out() As Variant, I As Long
    Table = CORE_ImportResult("counts")
    ReDim Out(1 To 3, 1 To 7)
    For I = 1 To 3
        Out(I, 1) = Table(I, 1)
        Out(I, 2) = CStr(Sizes(I - 1))
        Out(I, 3) = Hashes(I - 1)
        Out(I, 4) = Table(I, 2)
        Out(I, 5) = Table(I, 3)
        Out(I, 6) = Table(I, 4)
        Out(I, 7) = Table(I, 5)
    Next I
    Counts = Out
End Function

Private Function Summary(ByVal Outcomes As Variant) As Variant
    'Loan-months and the sum of their balances at t-1 per t-1, segment,
    'currency and outcome, in key order.
    Dim Index As Collection, Keys() As String, N As Long, I As Long, K As String, T As Long
    Dim Count() As Long, Balance() As Variant, Value As Variant, Order As Variant, Out() As Variant, Parts As Variant
    Summary = Empty    'explicit, as in CORE_Import
    If IsEmpty(Outcomes) Then Exit Function
    Set Index = New Collection
    ReDim Keys(1 To UBound(Outcomes, 1))
    ReDim Count(1 To UBound(Outcomes, 1))
    ReDim Balance(1 To UBound(Outcomes, 1))
    For I = 1 To UBound(Outcomes, 1)
        K = Outcomes(I, 2) & vbTab & Outcomes(I, 4) & vbTab & Outcomes(I, 5) & vbTab & Outcomes(I, 3)
        T = Position(Index, K)
        If T = 0 Then
            N = N + 1
            Keys(N) = K
            Balance(N) = CDec(0)
            Index.Add N, HexKey(K)
            T = N
        End If
        If Not CORE_ParseDecimal(CStr(Outcomes(I, 6)), 8, Value) Then
            Err.Raise vbObjectError + 1303, "CORE_Dataset", "Not a balance: " & Outcomes(I, 6)
        End If
        Count(T) = Count(T) + 1
        Balance(T) = Balance(T) + Value
    Next I
    Order = CORE_SortedOrder(Keys, N)
    ReDim Out(1 To N, 1 To 6)
    For I = 1 To N
        T = Order(I)
        Parts = Split(Keys(T), vbTab)
        Out(I, 1) = Parts(0)
        Out(I, 2) = Parts(1)
        Out(I, 3) = Parts(2)
        Out(I, 4) = Parts(3)
        Out(I, 5) = CStr(Count(T))
        Out(I, 6) = CORE_DecimalText(Balance(T))
    Next I
    Summary = Out
End Function

Private Function Position(ByVal Index As Collection, ByVal Key As String) As Long
    On Error Resume Next
    Position = Index.Item(HexKey(Key))
    On Error GoTo 0
End Function

Private Function HexKey(ByVal Text As String) As String
    'A Collection key for case-sensitive text, since Collection keys ignore case.
    Dim I As Long
    HexKey = "k"
    For I = 1 To Len(Text)
        HexKey = HexKey & Right$("000" & Hex$(AscW(Mid$(Text, I, 1))), 4)
    Next I
End Function
