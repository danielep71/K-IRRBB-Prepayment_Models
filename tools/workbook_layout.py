"""Workbook layout of docs/WORKBOOK_CONTRACT.md as data; shared by the build tools."""
from __future__ import annotations

from dataclasses import dataclass, field

PRODUCTION = 'production'
TEST = 'test'
BUILDS = (PRODUCTION, TEST)

SEGMENTS = ('MTG_FIX', 'MTG_RST', 'MTG_FLT', 'CON_FIX', 'SME_FIX')
STATUS_VALUES = ('CURRENT', 'STALE', 'FAILED')
RUN_NAMES = ('Run_Status', 'Run_ID', 'Run_Operation', 'Run_Timestamp', 'Run_Commit')


@dataclass(frozen=True)
class Setting:
    code: str
    description: str
    unit: str
    contract: str
    default: str = ''
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class Table:
    name: str
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class Sheet:
    tab: str
    code_name: str
    role: str
    tables: tuple[Table, ...] = field(default_factory=tuple)
    test_only: bool = False

    @property
    def has_status(self) -> bool:
        return self.role not in ('Reference', 'Input')


RUN_SETTINGS = (
    Setting('as_of_date', 'Projection start and BASE curve date; a month end inside the data window',
            'ISO date', 'Model contracts, scenarios'),
    Setting('data_window_start', 'First month end of the data window', 'ISO date', 'Data contract, point in time'),
    Setting('data_window_end', 'Last month end of the data window', 'ISO date', 'Data contract, point in time'),
    Setting('estimation_start', 'First month end of the estimation window', 'ISO date', 'Model contracts, common rules'),
    Setting('estimation_end', 'Last month end of the estimation window', 'ISO date', 'Model contracts, common rules'),
    Setting('test_start', 'First month end of the test window, or empty', 'ISO date', 'Common rules; V1'),
    Setting('test_end', 'Last month end of the test window, or empty', 'ISO date', 'Common rules; V1'),
    Setting('segment_list', 'Comma-separated subset of the D2 segment codes', 'Codes', 'D2'),
    Setting('currency_allowlist', 'Comma-separated ISO 4217 codes', 'Codes', 'Data contract, E07'),
    Setting('refi_curve_series', 'Par swap rate_id values, at least one per currency', 'rate_id list', 'M3'),
    Setting('discount_curve_series', 'Continuously compounded zero-rate rate_id values', 'rate_id list', 'M13'),
    Setting('discount_curve_convention', 'Discount curve convention; any other value rejects the run', 'Code',
            'M13', 'ZERO_CC', ('ZERO_CC',)),
    Setting('reneg_inclusion', 'RENEG in the SMM numerator and denominator', 'Code', 'D4', 'EXCLUDE',
            ('EXCLUDE', 'INCLUDE')),
    Setting('standardised_layer', 'Add the standardised-multiplier CPR layer', 'Y/N', 'M15', 'N', ('Y', 'N')),
    Setting('tier1_amount', 'Tier 1 capital for the dEVE / Tier 1 ratio', 'Currency units', 'D10'),
    Setting('tier1_currency', 'Currency of the Tier 1 amount', 'ISO 4217', 'D10'),
    Setting('timely_reporting_attested', 'Events and flows reported by the month end in which they occur',
            'Y/N', 'Data contract, lineage', 'N', ('Y', 'N')),
    Setting('calibration_run_id', 'Calibration run whose parameter sets are used; empty for the latest',
            'Run ID', 'Model contracts, parameter outputs'),
)

OPTIMISER_SETTINGS = tuple(
    Setting(code, description, unit, 'Model contracts, estimation')
    for code, description, unit in (
        ('opt_start_p1', 'Start value of p1 (c_min)', 'Decimal'),
        ('opt_start_p2', 'Start value of p2 (c_max)', 'Decimal'),
        ('opt_start_p3', 'Start value of p3 (log k)', 'Decimal'),
        ('opt_start_p4', 'Start value of p4 (x0)', 'Decimal'),
        ('opt_initial_step', 'Initial simplex step', 'Decimal'),
        ('opt_tolerance', 'Convergence tolerance', 'Decimal'),
        ('opt_max_iterations', 'Iteration limit', 'Integer'),
        ('opt_restarts', 'Number of restarts', 'Integer'),
    )
)

SETTING_HEADERS = ('Code', 'Description', 'Value', 'Unit', 'Contract')
RECON_MEASURES = (
    'loans', 'balance', 'scheduled_principal', 'prepaid_partial', 'prepaid_full', 'other_change',
    'full_count', 'full_balance', 'maturity_count', 'maturity_balance', 'default_count', 'default_balance',
    'reneg_count', 'reneg_balance', 'sale_count', 'sale_balance',
)
KEY = ('as_of_date', 'segment', 'currency')
RESULT_KEY = ('parameter_set_id', 'segment', 'currency', 'layer', 'scenario')

SHEETS = (
    Sheet('README', 'shReadme', 'Reference'),
    Sheet('Settings', 'shSettings', 'Input', (
        Table('Settings_Run', SETTING_HEADERS),
        Table('Settings_Optimiser', SETTING_HEADERS),
    )),
    Sheet('Assumptions', 'shAssumptions', 'Input', (
        Table('Assumptions_Segments',
              ('segment', 'margin', 'a_ramp', 'burnout_b', *(f'season_{m:02d}' for m in range(1, 13)),
               'source_note'),
              tuple((code,) for code in SEGMENTS)),
    )),
    Sheet('Scenarios', 'shScenarios', 'Input', (
        Table('Scenarios_Shocks', ('currency', 'parallel', 'short', 'long', 'status_note')),
        Table('Scenarios_User', ('scenario_id', 'currency', 'type', 'size', 'ramp_months')),
    )),
    Sheet('Controls', 'shControls', 'Input', (
        Table('Controls_Totals', (*KEY, *RECON_MEASURES)),
    )),
    Sheet('Import', 'shImport', 'Output', (
        Table('Import_Lineage', ('item', 'value')),
        Table('Import_Counts', ('file', 'size_bytes', 'sha256', 'rows_read', 'rows_accepted',
                                'rows_outside_window', 'loans')),
    )),
    Sheet('Findings', 'shFindings', 'Diagnostics', (
        Table('Findings_Summary', ('code', 'severity', 'count')),
        Table('Findings_Rows', ('code', 'file', 'line', 'key', 'message')),
    )),
    Sheet('Reconciliation', 'shReconciliation', 'Output', (
        Table('Reconciliation_Totals', (*KEY, *RECON_MEASURES)),
        Table('Reconciliation_Controls', (*KEY, 'measure', 'control', 'computed', 'difference', 'outcome')),
    )),
    Sheet('Parameters', 'shParameters', 'Parameters', (
        Table('Parameters_Sets', ('parameter_set_id', 'calibration_run_id', 'model', 'model_version', 'segment',
                                  'currency', 'data_window_start', 'data_window_end', 'estimation_start',
                                  'estimation_end', 'test_start', 'test_end', 'input_fingerprints',
                                  'settings_fingerprint', 'created', 'commit')),
        Table('Parameters_Values', ('parameter_set_id', 'name', 'value', 'unit', 'layer')),
    )),
    Sheet('Calibration', 'shCalibration', 'Diagnostics', (
        Table('Calibration_Optimiser', ('parameter_set_id', 'segment', 'currency', 'model', 'outcome', 'reason',
                                        'iterations', 'objective', 'weighted_r2')),
        Table('Calibration_Buckets', ('parameter_set_id', 'segment', 'currency', 'bucket_lower_bp',
                                      'observed_smm', 'fitted_smm', 'observed_cpr', 'fitted_cpr', 'exposure')),
        Table('Calibration_Residuals', ('parameter_set_id', 'segment', 'currency', 'dimension', 'value',
                                        'residual_smm', 'exposure')),
    )),
    Sheet('Backtest', 'shBacktest', 'Diagnostics', (
        Table('Backtest_Scores', ('parameter_set_id', 'model', 'segment', 'currency', 'origin', 'horizon',
                                  'classification', 'bias', 'mae', 'cumulative_error')),
        Table('Backtest_Outcome', ('segment', 'currency', 'incomplete_pairs', 'zero_realised_pairs',
                                   'smm_criterion', 'cumulative_criterion', 'outcome')),
    )),
    Sheet('CashFlows', 'shCashFlows', 'Output', (
        Table('CashFlows_Table', (*RESULT_KEY, 'month', 'opening', 'interest', 'scheduled', 'prepaid',
                                  'repricing', 'closing', 'smm', 'cpr')),
    )),
    Sheet('EVE', 'shEVE', 'Output', (
        Table('EVE_Scenarios', (*RESULT_KEY, 'pv', 'delta_eve')),
        Table('EVE_Summary', ('currency', 'layer', 'worst_scenario', 'worst_delta_eve', 'tier1_amount',
                              'tier1_currency', 'ratio', 'indicator', 'label')),
    )),
    Sheet('Gap', 'shGap', 'Output', (
        Table('Gap_Table', (*RESULT_KEY, 'bucket', 'bucket_label', 'principal', 'conservation_difference')),
    )),
    Sheet('Measures', 'shMeasures', 'Output', (
        Table('Measures_Table', (*RESULT_KEY, 'weighted_average_repricing_time', 'effective_duration',
                                 'projected_cpr_12m', 'projected_cpr_projection')),
    )),
    Sheet('Log', 'shLog', 'Diagnostics', (
        Table('Log_Runs', ('run_id', 'operation', 'started', 'finished', 'outcome', 'calibration_run_id',
                           'excel_state_restored', 'first_error')),
    )),
    Sheet('Tests', 'shTests', 'Test build', (
        Table('Tests_Cases', ('case_id', 'outcome', 'injected', 'message')),
    ), test_only=True),
)


def sheets_for(build: str) -> tuple[Sheet, ...]:
    """Sheets of a build, in tab order."""
    if build not in BUILDS:
        raise ValueError(f'unknown build {build!r}; expected one of {BUILDS}')
    return tuple(s for s in SHEETS if build == TEST or not s.test_only)


def document_modules(build: str) -> tuple[str, ...]:
    """VBA document modules of a build: ThisWorkbook and one per sheet."""
    return ('ThisWorkbook', *(s.code_name for s in sheets_for(build)))


def defined_names(build: str) -> tuple[str, ...]:
    """Every workbook-scoped name the template defines for a build."""
    names: list[str] = []
    for sheet in sheets_for(build):
        if sheet.has_status:
            names.append(f'{sheet.tab}_Status')
        names.extend(t.name for t in sheet.tables)
    names.extend(f'cfg_{s.code}' for s in (*RUN_SETTINGS, *OPTIMISER_SETTINGS))
    names.extend(RUN_NAMES)
    names.append('Build_Commit')
    return tuple(names)
