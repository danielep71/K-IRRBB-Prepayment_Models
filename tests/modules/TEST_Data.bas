Attribute VB_Name = "TEST_Data"
'==============================================================================
' MODULE: TEST_Data
'------------------------------------------------------------------------------
' PURPOSE
'   VBA tests of the data-contract primitives, run by TEST_Harness against
'   the committed expected files (tests/expected), which the test build
'   carries in the generated TEST_Fixtures module.
'
' CASES
'   DATA-PARSE-01  Dates, month ends, decimals (with D17) and codes of
'                  tests/expected/DATA-PARSE-01.json through CORE_Parse.
'   DATA-SHA-01    SHA-256 of the FIPS 180 examples, including one million
'                  "a", and of the three files of the fixture named in
'                  tests/expected/DATA-SHA-01.json, through CORE_Sha256.
'   UNIT-CSV-01    Line and field splitting of CORE_Csv: LF and CRLF, a
'                  final LF, an empty line, a missing final LF, a lone CR
'                  inside a line and a non-ASCII byte; not a register case.
'==============================================================================

Option Explicit
Option Private Module

Private Const PARSE As String = "DATA-PARSE-01"
Private Const SHA As String = "DATA-SHA-01"

Public Sub TEST_DataParse01()
    Dim I As Long, Path As String, Text As String, Valid As Boolean, D As Date, V As Variant
    For I = 0 To TEST_Expected.TEST_Count(PARSE, "/dates") - 1
        Path = "/dates/" & I
        Text = TEST_Expected.TEST_Value(PARSE, Path & "/input")
        Valid = (TEST_Expected.TEST_Value(PARSE, Path & "/valid") = "1")
        TEST_Harness.TEST_CheckTrue "date " & Quote(Text), CORE_ParseDate(Text, D) = Valid
    Next I
    For I = 0 To TEST_Expected.TEST_Count(PARSE, "/month_ends") - 1
        Path = "/month_ends/" & I
        Text = TEST_Expected.TEST_Value(PARSE, Path & "/input")
        Valid = (TEST_Expected.TEST_Value(PARSE, Path & "/valid") = "1")
        TEST_Harness.TEST_CheckTrue "date " & Quote(Text) & " parses", CORE_ParseDate(Text, D)
        TEST_Harness.TEST_CheckTrue "month end " & Quote(Text), CORE_IsMonthEnd(D) = Valid
    Next I
    For I = 0 To TEST_Expected.TEST_Count(PARSE, "/decimals") - 1
        Path = "/decimals/" & I
        Text = TEST_Expected.TEST_Value(PARSE, Path & "/input")
        If TEST_Expected.TEST_Kind(PARSE, Path & "/value") = "z" Then
            TEST_Harness.TEST_CheckTrue "decimal " & Quote(Text) & " rejected", _
                Not CORE_ParseDecimal(Text, CLng(TEST_Expected.TEST_Value(PARSE, Path & "/places")), V)
        ElseIf CORE_ParseDecimal(Text, CLng(TEST_Expected.TEST_Value(PARSE, Path & "/places")), V) Then
            TEST_Harness.TEST_CheckEqual "decimal " & Quote(Text), CORE_DecimalText(V), _
                TEST_Expected.TEST_Value(PARSE, Path & "/value")
            TEST_Harness.TEST_CheckTrue "decimal " & Quote(Text) & " is a Decimal", VarType(V) = vbDecimal
        Else
            TEST_Harness.TEST_CheckTrue "decimal " & Quote(Text) & " accepted", False
        End If
    Next I
    For I = 0 To TEST_Expected.TEST_Count(PARSE, "/codes") - 1
        Path = "/codes/" & I
        Text = TEST_Expected.TEST_Value(PARSE, Path & "/input")
        Valid = (TEST_Expected.TEST_Value(PARSE, Path & "/valid") = "1")
        TEST_Harness.TEST_CheckTrue "code " & Quote(Text), _
            CORE_IsCode(TEST_Expected.TEST_Value(PARSE, Path & "/set"), Text) = Valid
    Next I
End Sub

Public Sub TEST_DataSha01()
    Dim I As Long, Path As String, Data() As Byte, Length As Long, Fixture As String, Name As String
    For I = 0 To TEST_Expected.TEST_Count(SHA, "/messages") - 1
        Path = "/messages/" & I
        Data = Repeated(TEST_Expected.TEST_Value(SHA, Path & "/text"), _
                        CLng(TEST_Expected.TEST_Value(SHA, Path & "/repeat")), Length)
        TEST_Harness.TEST_CheckEqual "SHA-256 of message " & I, CORE_Sha256Hex(Data, Length), _
            TEST_Expected.TEST_Value(SHA, Path & "/sha256")
    Next I
    Fixture = TEST_Expected.TEST_Value(SHA, "/fixture")
    For I = 0 To TEST_Expected.TEST_Count(SHA, "/files") - 1
        Name = TEST_Expected.TEST_Key(SHA, "/files", I)
        Data = TEST_Fixtures.TEST_FixtureBytes(Fixture & "/" & Name, Length)
        TEST_Harness.TEST_CheckEqual "SHA-256 of " & Name, CORE_Sha256Hex(Data, Length), _
            TEST_Expected.TEST_Value(SHA, "/files/" & Name)
    Next I
End Sub

Public Sub TEST_UnitCsv01()
    Dim Data() As Byte, Length As Long, Lines() As String, Ascii() As Boolean, N As Long, F As Variant
    Data = Repeated("a,b" & vbLf & "c" & vbCrLf & vbLf & "d" & vbCr & "e" & vbCr, 1, Length)
    N = CORE_SplitLines(Data, Length, Lines, Ascii)
    TEST_Harness.TEST_CheckEqual "line count", CStr(N), "4"
    If N = 4 Then
        TEST_Harness.TEST_CheckEqual "LF line", Lines(1), "a,b"
        TEST_Harness.TEST_CheckEqual "CRLF line", Lines(2), "c"
        TEST_Harness.TEST_CheckEqual "empty line", Lines(3), ""
        TEST_Harness.TEST_CheckEqual "lone CR kept, final CR dropped", Lines(4), "d" & vbCr & "e"
    End If
    Data = Repeated("x" & vbLf, 1, Length)
    TEST_Harness.TEST_CheckEqual "a final LF adds no line", CStr(CORE_SplitLines(Data, Length, Lines, Ascii)), "1"
    TEST_Harness.TEST_CheckEqual "no lines in an empty file", CStr(CORE_SplitLines(Data, 0, Lines, Ascii)), "0"
    Data = Repeated("ok" & vbLf & "caf?", 1, Length)
    Data(Length - 1) = 233    'e acute in Windows-1252 and ISO 8859-1
    N = CORE_SplitLines(Data, Length, Lines, Ascii)
    TEST_Harness.TEST_CheckTrue "ASCII line", Ascii(1)
    TEST_Harness.TEST_CheckTrue "non-ASCII line", Not Ascii(2)
    TEST_Harness.TEST_CheckEqual "non-ASCII byte kept as its code", CStr(AscW(Right$(Lines(2), 1))), "233"
    F = CORE_SplitFields("a,,b")
    TEST_Harness.TEST_CheckEqual "fields", CStr(UBound(F) - LBound(F) + 1) & ":" & F(1) & ":" & F(2), "3::b"
    F = CORE_SplitFields("")
    TEST_Harness.TEST_CheckEqual "an empty line has one field", CStr(UBound(F) - LBound(F) + 1), "1"
End Sub

Private Function Repeated(ByVal Text As String, ByVal Times As Long, ByRef Length As Long) As Variant
    'Text repeated Times as bytes (each character is ASCII), in a Variant.
    Dim B() As Byte, I As Long, J As Long, K As Long
    Length = Len(Text) * Times
    If Length = 0 Then
        ReDim B(0 To 0)
    Else
        ReDim B(0 To Length - 1)
    End If
    For I = 1 To Times
        For J = 1 To Len(Text)
            B(K) = AscW(Mid$(Text, J, 1))
            K = K + 1
        Next J
    Next I
    Repeated = B
End Function

Private Function Quote(ByVal Text As String) As String
    Quote = """" & Text & """"
End Function
