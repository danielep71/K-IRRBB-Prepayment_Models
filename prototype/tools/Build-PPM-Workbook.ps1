<#
.SYNOPSIS
Build the K-PREPAY macro-enabled workbook from the template and the VBA source.

.DESCRIPTION
Copies src\workbook\PPM_Template.xlsx, imports the standard modules of src\
(and, in Development mode, tests\modules\) into it through Excel, and saves
the result as an .xlsm. The template and the source files are not changed.

- Production: CORE_*, PPM_Formulas and M_Main. The Run tests button reports
  that the test module is missing.
- Development: the production modules and TEST_PPM, for a workbook that runs
  the reference tests. The tests rewrite every output sheet; run them on the
  illustrative data only.

Each module is converted to CRLF line endings in a temporary folder before it
is imported, because the VBE expects CRLF.

.REQUIREMENTS
- Windows desktop Excel (Microsoft 365 or 2016 and later).
- Excel > Options > Trust Center > Macro Settings >
  "Trust access to the VBA project object model" enabled for the build.
  Where policy forbids it, import the files by hand (INSTALLATION.md).

.EXAMPLE
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Build-PPM-Workbook.ps1 -OutputPath "C:\Work\K-PREPAY.xlsm"

.EXAMPLE
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Build-PPM-Workbook.ps1 -OutputPath "C:\Work\K-PREPAY.xlsm" -Mode Production
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$OutputPath,

    [Parameter(Mandatory = $false)]
    [ValidateSet('Production', 'Development')]
    [string]$Mode = 'Development',

    [Parameter(Mandatory = $false)]
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Template = Join-Path $RepoRoot 'src\workbook\PPM_Template.xlsx'
if (-not (Test-Path -LiteralPath $Template)) { throw "Template not found: $Template" }

$OutputPath = [System.IO.Path]::GetFullPath($OutputPath)
if ([System.IO.Path]::GetExtension($OutputPath) -ne '.xlsm') { throw "OutputPath must end in .xlsm: $OutputPath" }
if ((Test-Path -LiteralPath $OutputPath) -and -not $Force) {
    throw "$OutputPath exists. Use -Force to replace it."
}

# Modules in import order: configuration first, then the engine, the facade
# and the sheet macros, then the tests.
$Modules = @(
    'src\core\CORE_Config.bas',
    'src\core\CORE_Util.bas',
    'src\core\CORE_Curve.bas',
    'src\core\CORE_Prepay.bas',
    'src\core\CORE_Engine.bas',
    'src\core\CORE_Calibrate.bas',
    'src\modules\PPM_Formulas.bas',
    'src\workbook\M_Main.bas'
)
if ($Mode -eq 'Development') { $Modules += 'tests\modules\TEST_PPM.bas' }

$Staging = Join-Path ([System.IO.Path]::GetTempPath()) ('ppm-build-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $Staging | Out-Null
$Excel = $null
$Book = $null
try {
    # CRLF copies of the modules.
    $Staged = @()
    foreach ($Relative in $Modules) {
        $Source = Join-Path $RepoRoot $Relative
        if (-not (Test-Path -LiteralPath $Source)) { throw "Module not found: $Source" }
        $Text = [System.IO.File]::ReadAllText($Source, [System.Text.Encoding]::GetEncoding(1252))
        $Text = ($Text -replace "`r`n", "`n") -replace "`n", "`r`n"
        $Target = Join-Path $Staging (Split-Path -Leaf $Source)
        [System.IO.File]::WriteAllText($Target, $Text, [System.Text.Encoding]::GetEncoding(1252))
        $Staged += $Target
    }
    $WorkingCopy = Join-Path $Staging 'PPM_Template.xlsx'
    Copy-Item -LiteralPath $Template -Destination $WorkingCopy

    $Excel = New-Object -ComObject Excel.Application
    $Excel.Visible = $false
    $Excel.DisplayAlerts = $false
    $Excel.AutomationSecurity = 3    # msoAutomationSecurityForceDisable: no macro runs during the build
    $Book = $Excel.Workbooks.Open($WorkingCopy)
    try {
        $null = $Book.VBProject.VBComponents.Count
    } catch {
        throw 'Excel refused access to the VBA project. Enable "Trust access to the VBA project object model" ' +
              '(Trust Center > Macro Settings) for the build, or import the modules by hand (INSTALLATION.md).'
    }
    foreach ($File in $Staged) {
        $null = $Book.VBProject.VBComponents.Import($File)
        Write-Host ('Imported ' + (Split-Path -Leaf $File))
    }
    $Excel.CalculateFull()    # evaluate the PPM_* worksheet functions on Tests with the modules present
    if (Test-Path -LiteralPath $OutputPath) { Remove-Item -LiteralPath $OutputPath }
    $Book.SaveAs($OutputPath, 52)    # xlOpenXMLWorkbookMacroEnabled
    Write-Host "Saved $OutputPath ($Mode). Open it, enable macros, then press Run model on Results."
}
finally {
    if ($null -ne $Book) { $Book.Close($false) | Out-Null; [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($Book) }
    if ($null -ne $Excel) { $Excel.Quit(); [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($Excel) }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    Remove-Item -LiteralPath $Staging -Recurse -Force -ErrorAction SilentlyContinue
}
