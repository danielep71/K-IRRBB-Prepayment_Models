Attribute VB_Name = "CORE_Sha256"
'==============================================================================
' MODULE: CORE_Sha256
'------------------------------------------------------------------------------
' PURPOSE
'   SHA-256 (FIPS 180-4, sections 4.1.2, 4.2.2, 5.1.1, 6.2) of a byte array,
'   for the SHA-256 fingerprint of each input file in the lineage of
'   docs/methodology/DATA_CONTRACT.md. Written from the standard; pure VBA,
'   no operating-system or COM call (decision of 2026-10-28, #42).
'
' ARITHMETIC
'   A 32-bit word is held in a Long with its bit pattern; And, Or, Xor and Not
'   are bitwise on Long. Addition modulo 2^32 adds the 16-bit halves
'   separately, and the shifts mask before they multiply or divide, so no
'   intermediate value overflows a Long. Only the bit length of the message
'   uses a Double, which is exact below 2^53.
'
' PERFORMANCE
'   Not measured in Excel.
'
' DEPENDENCIES
'   None. Arrays and scalars only; no workbook, UI, file or COM access.
'==============================================================================

Option Explicit
Option Private Module

Private mPow(0 To 30) As Long
Private mK(0 To 63) As Long
Private mReady As Boolean

Public Function CORE_Sha256Hex(ByRef Data() As Byte, ByVal Length As Long) As String
    'Lower-case hex SHA-256 of the first Length bytes of Data (0-based).
    Dim Block() As Byte, Total As Long, I As Long, Bits As Double
    Dim H(0 To 7) As Long, W(0 To 63) As Long
    Dim A As Long, B As Long, C As Long, D As Long, E As Long, F As Long, G As Long, HH As Long
    Dim T1 As Long, T2 As Long, Offset As Long, J As Long
    If Not mReady Then Prepare
    'Padding (5.1.1): 0x80, zeros, then the bit length as 64-bit big endian.
    Total = ((Length + 8) \ 64 + 1) * 64
    ReDim Block(0 To Total - 1)
    For I = 0 To Length - 1
        Block(I) = Data(I)
    Next I
    Block(Length) = &H80
    Bits = CDbl(Length) * 8#
    For I = 0 To 7
        Block(Total - 1 - I) = CByte(Bits - Int(Bits / 256#) * 256#)
        Bits = Int(Bits / 256#)
    Next I
    'Initial hash value (5.3.3).
    H(0) = &H6A09E667: H(1) = &HBB67AE85: H(2) = &H3C6EF372: H(3) = &HA54FF53A
    H(4) = &H510E527F: H(5) = &H9B05688C: H(6) = &H1F83D9AB: H(7) = &H5BE0CD19
    For Offset = 0 To Total - 1 Step 64
        For J = 0 To 15
            W(J) = Word(Block, Offset + 4 * J)
        Next J
        For J = 16 To 63
            W(J) = Add4(SmallSigma1(W(J - 2)), W(J - 7), SmallSigma0(W(J - 15)), W(J - 16))
        Next J
        A = H(0): B = H(1): C = H(2): D = H(3): E = H(4): F = H(5): G = H(6): HH = H(7)
        For J = 0 To 63
            T1 = Add4(HH, BigSigma1(E), (E And F) Xor ((Not E) And G), Add2(mK(J), W(J)))
            T2 = Add2(BigSigma0(A), (A And B) Xor (A And C) Xor (B And C))
            HH = G: G = F: F = E
            E = Add2(D, T1)
            D = C: C = B: B = A
            A = Add2(T1, T2)
        Next J
        H(0) = Add2(H(0), A): H(1) = Add2(H(1), B): H(2) = Add2(H(2), C): H(3) = Add2(H(3), D)
        H(4) = Add2(H(4), E): H(5) = Add2(H(5), F): H(6) = Add2(H(6), G): H(7) = Add2(H(7), HH)
    Next Offset
    For I = 0 To 7
        CORE_Sha256Hex = CORE_Sha256Hex & LCase$(Right$("0000000" & Hex$(H(I)), 8))
    Next I
End Function

'------------------------------------------------------------------------------
' Functions of section 4.1.2
'------------------------------------------------------------------------------

Private Function BigSigma0(ByVal X As Long) As Long
    BigSigma0 = Rotr(X, 2) Xor Rotr(X, 13) Xor Rotr(X, 22)
End Function

Private Function BigSigma1(ByVal X As Long) As Long
    BigSigma1 = Rotr(X, 6) Xor Rotr(X, 11) Xor Rotr(X, 25)
End Function

Private Function SmallSigma0(ByVal X As Long) As Long
    SmallSigma0 = Rotr(X, 7) Xor Rotr(X, 18) Xor Shr(X, 3)
End Function

Private Function SmallSigma1(ByVal X As Long) As Long
    SmallSigma1 = Rotr(X, 17) Xor Rotr(X, 19) Xor Shr(X, 10)
End Function

'------------------------------------------------------------------------------
' 32-bit word arithmetic, on Long only
'------------------------------------------------------------------------------

Private Function Add2(ByVal X As Long, ByVal Y As Long) As Long
    'X + Y modulo 2^32: add the 16-bit halves separately so no Long overflows.
    Dim Lo As Long, Hi As Long
    Lo = (X And &HFFFF&) + (Y And &HFFFF&)
    Hi = High16(X) + High16(Y) + (Lo \ &H10000)
    Add2 = Join16(Hi, Lo)
End Function

Private Function Add4(ByVal X As Long, ByVal Y As Long, ByVal Z As Long, ByVal V As Long) As Long
    Dim Lo As Long, Hi As Long
    Lo = (X And &HFFFF&) + (Y And &HFFFF&) + (Z And &HFFFF&) + (V And &HFFFF&)
    Hi = High16(X) + High16(Y) + High16(Z) + High16(V) + (Lo \ &H10000)
    Add4 = Join16(Hi, Lo)
End Function

Private Function High16(ByVal X As Long) As Long
    'Bits 16 to 31 of X as a value in 0 to 65535.
    High16 = (X And &H7FFF0000) \ &H10000
    If X < 0 Then High16 = High16 Or &H8000&
End Function

Private Function Join16(ByVal Hi As Long, ByVal Lo As Long) As Long
    'The word whose high half is Hi mod 2^16 and low half is Lo mod 2^16.
    Join16 = ((Hi And &H7FFF&) * &H10000) Or (Lo And &HFFFF&)
    If (Hi And &H8000&) <> 0 Then Join16 = Join16 Or &H80000000
End Function

Private Function Shr(ByVal X As Long, ByVal N As Long) As Long
    'Logical right shift by N in 1 to 31.
    If X >= 0 Then
        Shr = X \ mPow(N)
    Else
        Shr = ((X And &H7FFFFFFF) \ mPow(N)) Or mPow(31 - N)
    End If
End Function

Private Function Rotr(ByVal X As Long, ByVal N As Long) As Long
    'Right rotation by N in 2 to 31, in one procedure for speed: bits N to 30
    'move down by N, bits 0 to N - 2 move up by 32 - N, and the sign bit and
    'bit N - 1 land on bits 31 - N and 31.
    Rotr = ((X And &H7FFFFFFF) \ mPow(N)) Or ((X And (mPow(N - 1) - 1)) * mPow(32 - N))
    If X < 0 Then Rotr = Rotr Or mPow(31 - N)
    If (X And mPow(N - 1)) <> 0 Then Rotr = Rotr Or &H80000000
End Function

Private Function Word(ByRef Block() As Byte, ByVal At As Long) As Long
    'Big-endian 32-bit word at byte offset At.
    Word = Join16(Block(At) * &H100& + Block(At + 1), Block(At + 2) * &H100& + Block(At + 3))
End Function

Private Sub Prepare()
    'Powers of two and the 64 round constants of section 4.2.2.
    Dim I As Long, K As Variant
    mPow(0) = 1
    For I = 1 To 30
        mPow(I) = mPow(I - 1) * 2
    Next I
    K = Array(&H428A2F98, &H71374491, &HB5C0FBCF, &HE9B5DBA5, &H3956C25B, &H59F111F1, &H923F82A4, &HAB1C5ED5, _
              &HD807AA98, &H12835B01, &H243185BE, &H550C7DC3, &H72BE5D74, &H80DEB1FE, &H9BDC06A7, &HC19BF174, _
              &HE49B69C1, &HEFBE4786, &HFC19DC6, &H240CA1CC, &H2DE92C6F, &H4A7484AA, &H5CB0A9DC, &H76F988DA, _
              &H983E5152, &HA831C66D, &HB00327C8, &HBF597FC7, &HC6E00BF3, &HD5A79147, &H6CA6351, &H14292967, _
              &H27B70A85, &H2E1B2138, &H4D2C6DFC, &H53380D13, &H650A7354, &H766A0ABB, &H81C2C92E, &H92722C85, _
              &HA2BFE8A1, &HA81A664B, &HC24B8B70, &HC76C51A3, &HD192E819, &HD6990624, &HF40E3585, &H106AA070, _
              &H19A4C116, &H1E376C08, &H2748774C, &H34B0BCB5, &H391C0CB3, &H4ED8AA4A, &H5B9CCA4F, &H682E6FF3, _
              &H748F82EE, &H78A5636F, &H84C87814, &H8CC70208, &H90BEFFFA, &HA4506CEB, &HBEF9A3F7, &HC67178F2)
    For I = 0 To 63
        mK(I) = K(I)
    Next I
    mReady = True
End Sub
