Attribute VB_Name = "PREPAY_Dataset"
'==============================================================================
' MODULE: PREPAY_Dataset
'------------------------------------------------------------------------------
' PURPOSE
'   Supported facade for one import of docs/methodology/DATA_CONTRACT.md
'   from the bytes of its three files, and for the accepted dataset of the
'   Excel session (docs/WORKBOOK_CONTRACT.md, W7). Listed in
'   docs/PUBLIC_API.txt.
'
' ALL OR NOTHING
'   PREPAY_Import validates the import. Without error, the import becomes
'   the accepted dataset, with the size and SHA-256 of each file; with any
'   error, the accepted dataset stays as it was. Invalid data is never a
'   VBA error: it is reported as findings, read with PREPAY_ImportResult.
'
' FAILURE
'   An argument of the wrong form raises error vbObjectError + 1002 with
'   source "PREPAY_Dataset" before any validation of the data; an unknown
'   result kind raises the same error.
'
' DEPENDENCIES
'   CORE_Import, CORE_Dataset, CORE_Parse, CORE_Sha256.
'==============================================================================

Option Explicit

Private Const ERR_ARGUMENT As Long = 1002
Private Const SOURCE As String = "PREPAY_Dataset"

Public Function PREPAY_Import(ByRef LoansData() As Byte, ByVal LoansLength As Long, _
                              ByRef PanelData() As Byte, ByVal PanelLength As Long, _
                              ByRef RatesData() As Byte, ByVal RatesLength As Long, _
                              ByVal WindowStart As String, ByVal WindowEnd As String, _
                              ByVal Allowlist As String, ByVal ControlLines As Variant, _
                              ByVal RunId As String) As Long
    'Import loans.csv, loan_panel.csv and market_rates.csv from the first
    'Length bytes of each 0-based array; returns the number of errors (0:
    'accepted and committed under RunId). WindowStart and WindowEnd are month
    'ends YYYY-MM-DD, start not after end; Allowlist is comma-separated ISO
    'currency codes; ControlLines is Empty when there is no Controls_Totals
    'table, else a 1-based array of its lines, header first, fields joined
    'with commas.
    Dim Start As Date, Finish As Date, Codes As Variant, Errors As Long
    CheckBytes LoansData, LoansLength, "LoansData"
    CheckBytes PanelData, PanelLength, "PanelData"
    CheckBytes RatesData, RatesLength, "RatesData"
    Start = MonthEndArgument(WindowStart, "WindowStart")
    Finish = MonthEndArgument(WindowEnd, "WindowEnd")
    If Finish < Start Then Fail "WindowEnd must not be before WindowStart"
    Codes = Currencies(Allowlist)
    If Not IsEmpty(ControlLines) Then CheckLines ControlLines
    If Len(RunId) = 0 Then Fail "RunId must not be empty"
    If IsEmpty(ControlLines) Then
        Errors = CORE_ReadImport(LoansData, LoansLength, PanelData, PanelLength, RatesData, RatesLength, _
                                 Start, Finish, Codes)
    Else
        Errors = CORE_ReadImport(LoansData, LoansLength, PanelData, PanelLength, RatesData, RatesLength, _
                                 Start, Finish, Codes, ControlLines)
    End If
    If Errors = 0 Then
        CORE_DatasetCommit RunId, Array(LoansLength, PanelLength, RatesLength), _
            Array(CORE_Sha256Hex(LoansData, LoansLength), CORE_Sha256Hex(PanelData, PanelLength), _
                  CORE_Sha256Hex(RatesData, RatesLength))
    End If
    PREPAY_Import = Errors
End Function

Public Function PREPAY_ImportResult(ByVal Kind As String) As Variant
    'The findings and results of the last import, accepted or not: errors,
    'warnings, gaps, missing, differences, counts, loan_months, outcomes,
    'totals or comparisons, as listed in CORE_Import.
    Select Case Kind
        Case "errors", "warnings", "gaps", "missing", "differences", "counts", "loan_months", "outcomes", _
             "totals", "comparisons"
            PREPAY_ImportResult = CORE_ImportResult(Kind)
        Case Else
            Fail "Unknown import result: " & Kind
    End Select
End Function

Public Function PREPAY_DatasetRunId() As String
    'The run ID of the accepted dataset; "" when no import has been accepted
    'in this Excel session.
    PREPAY_DatasetRunId = CORE_DatasetRunId()
End Function

Public Function PREPAY_DatasetResult(ByVal Kind As String) As Variant
    'A result of the accepted dataset: counts, outcomes, loan_outcomes,
    'totals, comparisons, warnings, gaps or loan_months, as listed in
    'CORE_Dataset; Empty when no import has been accepted.
    Select Case Kind
        Case "counts", "outcomes", "loan_outcomes", "totals", "comparisons", "warnings", "gaps", "loan_months"
            PREPAY_DatasetResult = CORE_DatasetResult(Kind)
        Case Else
            Fail "Unknown dataset result: " & Kind
    End Select
End Function

Private Sub CheckBytes(ByRef Data() As Byte, ByVal Length As Long, ByVal Name As String)
    'A 0-based array holding at least Length bytes.
    Dim Lower As Long, Upper As Long
    On Error GoTo Unallocated
    Lower = LBound(Data)
    Upper = UBound(Data)
    On Error GoTo 0
    If Lower <> 0 Or Length < 0 Or Length > Upper + 1 Then
        Fail Name & " must be a 0-based Byte array of at least " & CStr(Length) & " bytes"
    End If
    Exit Sub
Unallocated:
    Fail Name & " must be an allocated Byte array"
End Sub

Private Function MonthEndArgument(ByVal Text As String, ByVal Name As String) As Date
    Dim D As Date
    If Not CORE_ParseDate(Text, D) Then Fail Name & " must be a date YYYY-MM-DD: " & Text
    If Not CORE_IsMonthEnd(D) Then Fail Name & " must be a month end: " & Text
    MonthEndArgument = D
End Function

Private Function Currencies(ByVal Allowlist As String) As Variant
    'The comma-separated codes as a 0-based array; spaces around a code are
    'ignored.
    Dim Parts As Variant, I As Long
    Parts = Split(Allowlist, ",")
    If UBound(Parts) < 0 Then Fail "Allowlist must name at least one currency"
    For I = 0 To UBound(Parts)
        Parts(I) = Trim$(Parts(I))
        If Not CORE_IsCurrency(CStr(Parts(I))) Then Fail "Allowlist must hold ISO 4217 codes: " & Allowlist
    Next I
    Currencies = Parts
End Function

Private Sub CheckLines(ByVal Lines As Variant)
    Dim I As Long
    If Not IsArray(Lines) Then Fail "ControlLines must be Empty or an array of lines"
    For I = LBound(Lines) To UBound(Lines)
        If VarType(Lines(I)) <> vbString Then Fail "ControlLines must hold text lines"
    Next I
End Sub

Private Sub Fail(ByVal Message As String)
    Err.Raise vbObjectError + ERR_ARGUMENT, SOURCE, Message
End Sub
