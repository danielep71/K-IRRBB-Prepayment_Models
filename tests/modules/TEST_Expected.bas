Attribute VB_Name = "TEST_Expected"
'==============================================================================
' MODULE: TEST_Expected
'------------------------------------------------------------------------------
' PURPOSE
'   Reads the expected files of tests/expected as flattened by
'   tools/vba_fixtures.py into the generated TEST_Fixtures module: one
'   path, kind and value per JSON node. Paths are "/" joined, for example
'   "/decimals/3/input"; the root is "".
'
' FUNCTIONS
'   TEST_Kind(CaseId, Path)          o, a, s, n, b or z; "" when absent.
'   TEST_Value(CaseId, Path)         the value text; raises when absent.
'   TEST_Count(CaseId, Path)         number of items or keys of a or o.
'   TEST_Key(CaseId, Path, Index)    the Index-th key (0-based) of an o.
'
' STATE
'   Keeps the flattened lines of the last case read.
'==============================================================================

Option Explicit
Option Private Module

Private mCase As String
Private mKinds As Collection
Private mValues As Collection

Public Function TEST_Kind(ByVal CaseId As String, ByVal Path As String) As String
    Load CaseId
    On Error Resume Next
    TEST_Kind = mKinds.Item(KeyOf(Path))
    On Error GoTo 0
End Function

Public Function TEST_Value(ByVal CaseId As String, ByVal Path As String) As String
    Load CaseId
    If Len(TEST_Kind(CaseId, Path)) = 0 Then
        Err.Raise vbObjectError + 2, "TEST_Expected", "No value at " & CaseId & Path
    End If
    TEST_Value = mValues.Item(KeyOf(Path))
End Function

Public Function TEST_Count(ByVal CaseId As String, ByVal Path As String) As Long
    Dim Kind As String
    Kind = TEST_Kind(CaseId, Path)
    If Kind <> "a" And Kind <> "o" Then
        Err.Raise vbObjectError + 3, "TEST_Expected", "Not an array or object: " & CaseId & Path
    End If
    TEST_Count = CLng(TEST_Value(CaseId, Path))
End Function

Public Function TEST_Key(ByVal CaseId As String, ByVal Path As String, ByVal Index As Long) As String
    TEST_Key = TEST_Value(CaseId, Path & "/~" & CStr(Index))
End Function

Private Sub Load(ByVal CaseId As String)
    'Parse the flattened file of CaseId once; keys are hex so that the
    'case-insensitive Collection keeps paths that differ only in case apart.
    Dim Data() As Byte, Length As Long, Lines() As String, Ascii() As Boolean
    Dim N As Long, I As Long, Parts As Variant
    If CaseId = mCase And Not mKinds Is Nothing Then Exit Sub
    Data = TEST_Fixtures.TEST_ExpectedBytes(CaseId, Length)
    N = CORE_SplitLines(Data, Length, Lines, Ascii)
    Set mKinds = New Collection
    Set mValues = New Collection
    For I = 1 To N
        Parts = Split(Lines(I), vbTab)
        mKinds.Add CStr(Parts(1)), KeyOf(CStr(Parts(0)))
        mValues.Add CStr(Parts(2)), KeyOf(CStr(Parts(0)))
    Next I
    mCase = CaseId
End Sub

Private Function KeyOf(ByVal Path As String) As String
    Dim I As Long
    KeyOf = "k"
    For I = 1 To Len(Path)
        KeyOf = KeyOf & Right$("000" & Hex$(AscW(Mid$(Path, I, 1))), 4)
    Next I
End Function
