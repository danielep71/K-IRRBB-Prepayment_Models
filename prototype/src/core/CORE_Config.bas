Attribute VB_Name = "CORE_Config"
'==============================================================================
' MODULE: CORE_Config
'------------------------------------------------------------------------------
' PURPOSE
'   Hold every layout constant the prepayment engine depends on: sheet
'   names, the workbook names of the table headers, the column of each
'   input and output field, parameter codes, scenario and code lists,
'   severity labels and the error numbers raised by the macros. When a
'   sheet layout changes, it changes here, in tools/build_template.py and
'   nowhere else.
'
' PUBLIC SURFACE
'   None outside this VBA project. The constants are Public for in-project
'   use; Option Private Module keeps them off the external surface.
'
' DEPENDENCIES
'   None. Every value is a literal.
'
' STATE OWNERSHIP
'   Constants only; no state.
'
' ERROR POLICY
'   Not applicable.
'
' COMPATIBILITY
'   Excel VBA, Windows 64-bit primary; no references beyond the defaults.
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
    'Require explicit declarations; keep the constants inside this project.
    Option Explicit
    Option Private Module

'------------------------------------------------------------------------------
' PRODUCT
'------------------------------------------------------------------------------
        Public Const PRODUCT_NAME   As String = "K-PREPAY"     'Message-box title
        Public Const PRODUCT_VER    As String = "0.1.0"        'Prototype version

'------------------------------------------------------------------------------
' SHEET NAMES
'------------------------------------------------------------------------------
    'Worksheet tab names, as the engine looks them up in ThisWorkbook.
        Public Const SH_PARAMS      As String = "Params"           'Parameters, multipliers, seasonality
        Public Const SH_CURVE       As String = "Curve"            'Risk-free zero curve
        Public Const SH_SEGMENTS    As String = "Segments"         'Prepayment parameters per segment
        Public Const SH_LOANS       As String = "Loans"            'Loan inputs
        Public Const SH_HISTORY     As String = "History"          'Observations for calibration
        Public Const SH_RESULTS     As String = "Results"          'Scenario, summary and segment tables
        Public Const SH_CASHFLOWS   As String = "CashFlows"        'Monthly aggregated cash flows
        Public Const SH_GAP         As String = "Gap"              'BCBS time buckets
        Public Const SH_CURVES      As String = "ScenarioCurves"   'Shocked zero curves
        Public Const SH_LOANCALC    As String = "LoanCalc"         'One row per loan
        Public Const SH_CHECKS      As String = "Checks"           'Errors, warnings, information
        Public Const SH_CALIB       As String = "Calibration"      'Fitted S-curves
        Public Const SH_TESTS       As String = "Tests"            'Reference tests

'------------------------------------------------------------------------------
' COMMON LAYOUT
'------------------------------------------------------------------------------
    'Every table starts in column C, under a workbook name on its first
    'header cell; data start on the next row. Column numbers below count
    'from the first table column; CORE_Util.TableCol adds COL_OFFSET.
        Public Const COL_OFFSET       As Long = 2            'Margin columns A:B left of every table
        Public Const STATUS_CELL      As String = "C4"       'Run status line on output sheets
        Public Const NM_PRM_CODE      As String = "Params_Code"
        Public Const NM_PRM_VALUE     As String = "Params_Value"
        Public Const NM_GAMMA         As String = "Gamma_Table"
        Public Const NM_SEASON        As String = "Seasonality_Table"
        Public Const NM_CURVE         As String = "Curve_Header"
        Public Const NM_SEGMENTS      As String = "Segments_Header"
        Public Const NM_LOANS         As String = "Loans_Header"
        Public Const NM_HISTORY       As String = "History_Header"
        Public Const NM_RESULTS       As String = "Results_Header"
        Public Const NM_SUMMARY       As String = "Summary_Header"
        Public Const NM_SEGRES        As String = "SegResults_Header"
        Public Const NM_CASHFLOWS     As String = "CashFlows_Header"
        Public Const NM_GAP           As String = "Gap_Header"
        Public Const NM_CURVES        As String = "Curves_Header"
        Public Const NM_LOANCALC      As String = "LoanCalc_Header"
        Public Const NM_CHECKS        As String = "Checks_Header"
        Public Const NM_CALIB         As String = "Calibration_Header"
        Public Const NM_CALCURVE      As String = "CalCurve_Header"
        Public Const NM_TESTS         As String = "Tests_Header"

'------------------------------------------------------------------------------
' PARAMETER CODES
'------------------------------------------------------------------------------
    'Each parameter is read through the workbook name equal to its code.
        Public Const PRM_ASOF         As String = "AsOfDate"
        Public Const PRM_CCY          As String = "ReportingCcy"
        Public Const PRM_MODE         As String = "PrepayMode"
        Public Const PRM_PARALLEL     As String = "ShockParallel"
        Public Const PRM_SHORT        As String = "ShockShort"
        Public Const PRM_LONG         As String = "ShockLong"
        Public Const PRM_DECAY        As String = "ShockDecay"
        Public Const PRM_FLOOR        As String = "ApplyFloor"
        Public Const PRM_FLOORSTART   As String = "FloorStart"
        Public Const PRM_FLOORSLOPE   As String = "FloorSlope"
        Public Const PRM_MAXMONTHS    As String = "MaxProjectionMonths"
        Public Const PRM_TIER1        As String = "Tier1Capital"
        Public Const PRM_OUTLIER      As String = "OutlierThreshold"

    'Prepayment modes.
        Public Const MODE_BEHAVIOURAL As String = "BEHAVIOURAL"    'S-curve in every scenario
        Public Const MODE_BCBS_SA     As String = "BCBS_SA"        'Shocked CPR = gamma x base CPR

'------------------------------------------------------------------------------
' SCENARIOS
'------------------------------------------------------------------------------
    'Scenario indices; BASE is projected first because BCBS_SA scales its
    'CPR path. The order is the order of every output table.
        Public Const SCEN_COUNT       As Long = 8
        Public Const SC_CONTRACT      As Long = 1    'No prepayment, base curve
        Public Const SC_BASE          As Long = 2    'Behavioural, base curve
        Public Const SC_PAR_UP        As Long = 3
        Public Const SC_PAR_DOWN      As Long = 4
        Public Const SC_STEEPENER     As Long = 5
        Public Const SC_FLATTENER     As Long = 6
        Public Const SC_SHORT_UP      As Long = 7
        Public Const SC_SHORT_DOWN    As Long = 8
        Public Const SC_FIRST_SHOCK   As Long = 3
        Public Const SCEN_CODES       As String = "CONTRACT,BASE,PAR_UP,PAR_DOWN,STEEPENER,FLATTENER,SHORT_UP,SHORT_DOWN"

    'BCBS d368 Annex 2 shape coefficients.
        Public Const STEEP_SHORT      As Double = -0.65
        Public Const STEEP_LONG       As Double = 0.9
        Public Const FLAT_SHORT       As Double = 0.8
        Public Const FLAT_LONG        As Double = -0.6

'------------------------------------------------------------------------------
' TIME BUCKETS (BCBS d368 Table 1)
'------------------------------------------------------------------------------
        Public Const BUCKET_COUNT     As Long = 19
        Public Const BUCKET_LABELS    As String = "O/N,>O/N-1M,1M-3M,3M-6M,6M-9M,9M-1Y,1Y-1.5Y,1.5Y-2Y,2Y-3Y,3Y-4Y,4Y-5Y,5Y-6Y,6Y-7Y,7Y-8Y,8Y-9Y,9Y-10Y,10Y-15Y,15Y-20Y,>20Y"
        Public Const BUCKET_MIDPOINTS As String = "0.0028,0.0417,0.1667,0.375,0.625,0.875,1.25,1.75,2.5,3.5,4.5,5.5,6.5,7.5,8.5,9.5,12.5,17.5,25"
        Public Const BUCKET_EPS       As Double = 0.000000001    'Upper bound inclusive within 1e-9 years

'------------------------------------------------------------------------------
' INPUT TABLES
'------------------------------------------------------------------------------
    'Curve.
        Public Const CV_TENOR         As Long = 1
        Public Const CV_RATE          As Long = 2
        Public Const CV_NCOLS         As Long = 3

    'Segments.
        Public Const SG_ID            As Long = 1
        Public Const SG_DESC          As Long = 2
        Public Const SG_CPRMIN        As Long = 3
        Public Const SG_CPRMAX        As Long = 4
        Public Const SG_SLOPE         As Long = 5
        Public Const SG_MID           As Long = 6
        Public Const SG_RAMP          As Long = 7
        Public Const SG_BURNOUT       As Long = 8
        Public Const SG_MARGIN        As Long = 9
        Public Const SG_FLOATCPR      As Long = 10
        Public Const SG_SEASONAL      As Long = 11
        Public Const SG_NCOLS         As Long = 11

    'Loans.
        Public Const LN_ID            As Long = 1
        Public Const LN_SEG           As Long = 2
        Public Const LN_RATETYPE      As Long = 3
        Public Const LN_CCY           As Long = 4
        Public Const LN_BALANCE       As Long = 5
        Public Const LN_RATE          As Long = 6
        Public Const LN_ORIG          As Long = 7
        Public Const LN_MAT           As Long = 8
        Public Const LN_AMORT         As Long = 9
        Public Const LN_FREQ          As Long = 10
        Public Const LN_RESET         As Long = 11
        Public Const LN_PENALTY       As Long = 12
        Public Const LN_NCOLS         As Long = 12

    'History.
        Public Const HS_MONTH         As Long = 1
        Public Const HS_SEG           As Long = 2
        Public Const HS_INCENTIVE     As Long = 3
        Public Const HS_CPR           As Long = 4
        Public Const HS_WEIGHT        As Long = 5
        Public Const HS_NCOLS         As Long = 5

    'Codes.
        Public Const AM_ANNUITY       As Long = 1
        Public Const AM_LINEAR        As Long = 2
        Public Const AM_BULLET        As Long = 3

'------------------------------------------------------------------------------
' OUTPUT TABLES
'------------------------------------------------------------------------------
        Public Const RS_NCOLS         As Long = 10    'Results: scenario table
        Public Const SM_NCOLS         As Long = 3     'Results: summary table
        Public Const SM_ROWS          As Long = 10    'Results: summary measures
        Public Const SR_NCOLS         As Long = 12    'Results: segment table
        Public Const CF_NCOLS         As Long = 30    'CashFlows
        Public Const GP_NCOLS         As Long = 13    'Gap
        Public Const SCV_NCOLS        As Long = 9     'ScenarioCurves
        Public Const LC_NCOLS         As Long = 19    'LoanCalc
        Public Const CK_NCOLS         As Long = 5     'Checks
        Public Const CB_NCOLS         As Long = 10    'Calibration
        Public Const CB_MAX_ROWS      As Long = 20    'Calibration rows above the curve grid
        Public Const CC_POINTS        As Long = 33    'Calibration curve points
        Public Const CC_SERIES        As Long = 8     'Calibration curve columns
        Public Const CC_FROM          As Double = -0.03     'First incentive of the curve grid
        Public Const CC_STEP          As Double = 0.0025    'Step of the curve grid
        Public Const TS_NCOLS         As Long = 12    'Tests

    'Fields of the monthly aggregation array of CORE_Engine.ProjectBook.
        Public Const AG_SCHED         As Long = 1    'Scheduled principal
        Public Const AG_PREP          As Long = 2    'Prepayment
        Public Const AG_REPR          As Long = 3    'Repricing principal (FLOAT at reset)
        Public Const AG_INTR          As Long = 4    'Interest paid
        Public Const AG_CF            As Long = 5    'Total cash flow
        Public Const AG_BAL           As Long = 6    'Balance at the end of the month
        Public Const AG_CPRW          As Long = 7    'CPR x balance at the start of the month
        Public Const AG_BALW          As Long = 8    'Balance at the start of the month
        Public Const AG_PV            As Long = 9    'Discounted cash flow
        Public Const AGG_FIELDS       As Long = 9

'------------------------------------------------------------------------------
' VALIDATION DOMAINS
'------------------------------------------------------------------------------
        Public Const RATE_MIN         As Double = -0.05    'Lowest client rate accepted
        Public Const RATE_MAX         As Double = 1        'Highest client rate accepted
        Public Const SEASON_TOL       As Double = 0.000001 'Tolerance on the seasonality average
        Public Const MIN_CAL_OBS      As Long = 8          'Fewest observations to calibrate

'------------------------------------------------------------------------------
' CALIBRATION
'------------------------------------------------------------------------------
        Public Const NM_MAX_ITER      As Long = 4000
        Public Const NM_TOL           As Double = 0.0000000000001    'Relative spread of the simplex values
        Public Const NM_START_SLOPE   As Double = 100

'------------------------------------------------------------------------------
' SEVERITIES
'------------------------------------------------------------------------------
        Public Const SEV_ERROR        As String = "ERROR"
        Public Const SEV_WARNING      As String = "WARNING"
        Public Const SEV_INFO         As String = "INFO"

'------------------------------------------------------------------------------
' ERROR NUMBERS
'------------------------------------------------------------------------------
    'vbObjectError + 2048 to + 4095, as in the K-SACCR house style.
        Public Const ERR_BASE            As Long = vbObjectError + 2048
        Public Const ERR_MISSING_SHEET   As Long = vbObjectError + 2049
        Public Const ERR_MISSING_NAME    As Long = vbObjectError + 2050
        Public Const ERR_RUN_ACTIVE      As Long = vbObjectError + 2051
        Public Const ERR_CLEANUP_FAILED  As Long = vbObjectError + 2052
        Public Const ERR_RECALC_PENDING  As Long = vbObjectError + 2053
        Public Const ERR_TESTS_MISSING   As Long = vbObjectError + 2054
