<#
.SYNOPSIS
Export every VBA component and reference of a saved workbook into a new folder.

.DESCRIPTION
Opens the workbook read-only with macros disabled, exports each VBA component
(standard modules as .bas, class and document modules as .cls) and writes the
names of the VBA project references to references.json. The workbook is closed
without saving. Compare the folder with a build manifest using
`python tools/components.py compare`. This is stage 6 of docs/EXCEL_EVIDENCE.md.

.REQUIREMENTS
Windows desktop Excel. Exporting needs "Trust access to the VBA project object
model". This script never changes that or any other Trust Center setting; if
access is refused it stops, and the evidence record states whether the
operator enabled the setting for the export and turned it off afterwards.

.EXAMPLE
powershell.exe -NoProfile -File .\tools\Export-Workbook.ps1 -WorkbookPath C:\Work\prepay-test.xlsm -OutputFolder C:\Work\export
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$WorkbookPath,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$OutputFolder
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$WorkbookPath = [System.IO.Path]::GetFullPath($WorkbookPath)
$OutputFolder = [System.IO.Path]::GetFullPath($OutputFolder)
if (-not (Test-Path -LiteralPath $WorkbookPath -PathType Leaf)) { throw "Workbook not found: $WorkbookPath" }
if (Test-Path -LiteralPath $OutputFolder) {
    if (@(Get-ChildItem -LiteralPath $OutputFolder -Force).Count -gt 0) { throw "OutputFolder must be new or empty: $OutputFolder" }
} else {
    New-Item -ItemType Directory -Path $OutputFolder | Out-Null
}

# vbext_ComponentType: 1 standard, 2 class, 3 form, 100 document.
$Extensions = @{ 1 = '.bas'; 2 = '.cls'; 3 = '.frm'; 100 = '.cls' }
$Utf8 = New-Object System.Text.UTF8Encoding $false
$Excel = $null
$Book = $null
try {
    $Excel = New-Object -ComObject Excel.Application
    $Excel.Visible = $false
    $Excel.DisplayAlerts = $false
    $Excel.AutomationSecurity = 3    # msoAutomationSecurityForceDisable: no macro runs
    $Book = $Excel.Workbooks.Open($WorkbookPath, 0, $true)    # UpdateLinks 0, ReadOnly
    try {
        $Project = $Book.VBProject
        $null = $Project.VBComponents.Count
    } catch {
        throw 'Excel refused access to the VBA project. "Trust access to the VBA project object model" is off; ' +
              'this script does not change it.'
    }
    foreach ($Component in $Project.VBComponents) {
        $Extension = $Extensions[[int]$Component.Type]
        if ($null -eq $Extension) { throw "Unsupported component type $($Component.Type): $($Component.Name)" }
        $Component.Export((Join-Path $OutputFolder ($Component.Name + $Extension)))
    }
    $References = @(foreach ($Reference in $Project.References) { [string]$Reference.Name })
    $Json = ConvertTo-Json -InputObject $References
    [System.IO.File]::WriteAllText((Join-Path $OutputFolder 'references.json'), $Json, $Utf8)
    Write-Host ("Exported {0} components and {1} references to {2}" -f $Project.VBComponents.Count, $References.Count, $OutputFolder)
}
finally {
    if ($null -ne $Book) { $Book.Close($false) | Out-Null; [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($Book) }
    if ($null -ne $Excel) { $Excel.Quit(); [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($Excel) }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
