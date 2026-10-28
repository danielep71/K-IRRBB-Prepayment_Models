Attribute VB_Name = "CORE_Csv"
'==============================================================================
' MODULE: CORE_Csv
'------------------------------------------------------------------------------
' PURPOSE
'   Splits the bytes of an input file into lines and fields, following the
'   file format of docs/methodology/DATA_CONTRACT.md: ASCII text, LF or CRLF
'   line endings, comma separator, no quoting.
'
' LINES
'   Lines end at LF; one CR immediately before the LF, or at the end of the
'   last line, is dropped. A final LF ends the last line, so it adds no empty
'   line; an empty file has no lines. A line with a byte above 127 is not
'   ASCII (error E01); its text maps each byte to the character with that
'   code, so it never depends on the host code page.
'
' DEPENDENCIES
'   None. Arrays and scalars only; no workbook, UI, file or COM access.
'==============================================================================

Option Explicit
Option Private Module

Public Function CORE_SplitLines(ByRef Data() As Byte, ByVal Length As Long, _
                                ByRef Lines() As String, ByRef Ascii() As Boolean) As Long
    'Split the first Length bytes of Data (0-based) into lines. Returns the
    'number of lines N; when N > 0, Lines and Ascii are resized to 1 To N.
    Dim Count As Long, I As Long, Start As Long, StopAt As Long, N As Long
    For I = 0 To Length - 1
        If Data(I) = 10 Then Count = Count + 1
    Next I
    If Length > 0 Then
        If Data(Length - 1) <> 10 Then Count = Count + 1
    End If
    CORE_SplitLines = Count
    If Count = 0 Then Exit Function
    ReDim Lines(1 To Count)
    ReDim Ascii(1 To Count)
    Start = 0
    For I = 0 To Length
        If I = Length Then
            If Start = Length Then Exit For    'the final LF already ended the last line
            StopAt = Length
        ElseIf Data(I) = 10 Then
            StopAt = I
        Else
            StopAt = -1
        End If
        If StopAt >= 0 Then
            N = N + 1
            If StopAt > Start Then
                If Data(StopAt - 1) = 13 Then StopAt = StopAt - 1
            End If
            Lines(N) = LineText(Data, Start, StopAt, Ascii(N))
            Start = I + 1
        End If
    Next I
End Function

Public Function CORE_SplitFields(ByVal Line As String) As Variant
    'The comma-separated fields of Line as a 0-based array; an empty line
    'has one empty field.
    CORE_SplitFields = Split(Line, ",")
    If Len(Line) = 0 Then CORE_SplitFields = Array("")
End Function

Private Function LineText(ByRef Data() As Byte, ByVal Start As Long, ByVal StopAt As Long, _
                          ByRef IsAscii As Boolean) As String
    'Bytes Start to StopAt - 1 as text, one character per byte.
    Dim I As Long, Text As String
    IsAscii = True
    If StopAt <= Start Then Exit Function
    Text = String$(StopAt - Start, " ")
    For I = Start To StopAt - 1
        If Data(I) > 127 Then IsAscii = False
        Mid$(Text, I - Start + 1, 1) = ChrW$(Data(I))
    Next I
    LineText = Text
End Function
