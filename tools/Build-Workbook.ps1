<#
.SYNOPSIS
Build the production or test workbook from the VBA source of the checked-out commit.

.DESCRIPTION
Stage 1 of docs/EXCEL_EVIDENCE.md. In a clean checkout, the script:
1. stages the components of HEAD (tools/components.py stage) and generates the
   macro-free template (tools/build_template.py) in a temporary folder;
2. opens the template in Excel with macros disabled and imports the staged
   components;
3. saves the workbook in the temporary folder, exports it again with
   tools/Export-Workbook.ps1 and compares the export with the manifest
   (tools/components.py compare): any missing, extra or changed component,
   code in a document module or non-default reference fails the build;
4. only then copies the workbook to OutputPath and writes OutputPath.build.json
   with the commit, build, host and comparison result.

Nothing in the checkout is changed. OutputPath must be outside the checkout or
under its ignored build\ or out\ folders. The workbook is never committed.

.REQUIREMENTS
- Windows desktop Excel; Python 3.10+ with tools/requirements-build.txt.
- Importing needs "Trust access to the VBA project object model". This script
  never changes it or any other Trust Center setting; if access is refused it
  stops, and the evidence record states whether the operator enabled the
  setting for the build and turned it off afterwards.

.EXAMPLE
powershell.exe -NoProfile -File .\tools\Build-Workbook.ps1 -Build Test -OutputPath C:\Work\prepay-test.xlsm
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Production', 'Test')]
    [string]$Build,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$OutputPath,

    [Parameter(Mandatory = $false)]
    [string]$Python = 'python',

    [Parameter(Mandatory = $false)]
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-Checked([string]$File, [string[]]$Arguments) {
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $File $($Arguments -join ' ')" }
}

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BuildName = $Build.ToLowerInvariant()

$Dirty = & git -C $RepoRoot status --porcelain --untracked-files=no
if ($LASTEXITCODE -ne 0) { throw 'git status failed' }
if ($Dirty) { throw "The checkout has uncommitted changes; build only from a clean checkout:`n$Dirty" }
$Commit = (& git -C $RepoRoot rev-parse HEAD).Trim()
if ($Commit -notmatch '^[0-9a-f]{40}$') { throw "Could not resolve HEAD: $Commit" }

$OutputPath = [System.IO.Path]::GetFullPath($OutputPath)
if ([System.IO.Path]::GetExtension($OutputPath) -ne '.xlsm') { throw "OutputPath must end in .xlsm: $OutputPath" }
$RootPrefix = [System.IO.Path]::GetFullPath($RepoRoot).TrimEnd('\') + '\'
if ($OutputPath.StartsWith($RootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    $Top = $OutputPath.Substring($RootPrefix.Length).Split('\')[0]
    if (@('build', 'out') -notcontains $Top.ToLowerInvariant()) {
        throw "OutputPath inside the checkout must be under build\ or out\: $OutputPath"
    }
}
if ((Test-Path -LiteralPath $OutputPath) -and -not $Force) { throw "$OutputPath exists. Use -Force to replace it." }

$Staging = Join-Path ([System.IO.Path]::GetTempPath()) ('prepay-build-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $Staging | Out-Null
$Stage = Join-Path $Staging 'stage'
$Template = Join-Path $Staging 'template.xlsx'
$Built = Join-Path $Staging 'workbook.xlsm'
$Export = Join-Path $Staging 'export'
$Utf8 = New-Object System.Text.UTF8Encoding $false
$Excel = $null
$Book = $null
try {
    Invoke-Checked $Python @((Join-Path $RepoRoot 'tools\components.py'), 'stage', '--build', $BuildName, '--commit', $Commit, '--out', $Stage)
    Invoke-Checked $Python @((Join-Path $RepoRoot 'tools\build_template.py'), '--build', $BuildName, '--commit', $Commit, '--output', $Template)
    $Manifest = Get-Content -LiteralPath (Join-Path $Stage 'manifest.json') -Raw | ConvertFrom-Json

    $Excel = New-Object -ComObject Excel.Application
    $Excel.Visible = $false
    $Excel.DisplayAlerts = $false
    $Excel.AutomationSecurity = 3    # msoAutomationSecurityForceDisable: no macro runs during the build
    $HostInfo = [ordered]@{
        excel_version = [string]$Excel.Version
        excel_build = [string]$Excel.Build
        operating_system = [string]$Excel.OperatingSystem
        office_platform = 'unknown'
    }
    $ClickToRun = 'HKLM:\SOFTWARE\Microsoft\Office\ClickToRun\Configuration'
    if (Test-Path -LiteralPath $ClickToRun) {
        $Platform = (Get-ItemProperty -LiteralPath $ClickToRun -ErrorAction SilentlyContinue).Platform
        if ($Platform) { $HostInfo.office_platform = [string]$Platform }
    }
    $Book = $Excel.Workbooks.Open($Template)
    try {
        $Project = $Book.VBProject
        $null = $Project.VBComponents.Count
    } catch {
        throw 'Excel refused access to the VBA project. "Trust access to the VBA project object model" is off; ' +
              'this script does not change it.'
    }
    foreach ($Component in @($Manifest.components)) {
        $File = Join-Path (Join-Path $Stage 'components') ([System.IO.Path]::GetFileName($Component.path))
        $null = $Project.VBComponents.Import($File)
        Write-Host ('Imported ' + $Component.name)
    }
    $Book.SaveAs($Built, 52)    # xlOpenXMLWorkbookMacroEnabled
    $Book.Close($false) | Out-Null
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($Book)
    $Book = $null
    $Excel.Quit()
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($Excel)
    $Excel = $null

    & (Join-Path $PSScriptRoot 'Export-Workbook.ps1') -WorkbookPath $Built -OutputFolder $Export
    # Windows PowerShell turns redirected stderr into errors under 'Stop'; capture it as text instead.
    $ErrorActionPreference = 'Continue'
    $Comparison = & $Python (Join-Path $RepoRoot 'tools\components.py') compare --manifest (Join-Path $Stage 'manifest.json') --export $Export 2>&1
    $CompareExit = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    $Comparison | ForEach-Object { Write-Host $_ }
    if ($CompareExit -ne 0) { throw 'The built workbook does not match the commit; nothing was written to OutputPath.' }

    $OutputDir = Split-Path -Parent $OutputPath
    if (-not (Test-Path -LiteralPath $OutputDir)) { New-Item -ItemType Directory -Path $OutputDir | Out-Null }
    Copy-Item -LiteralPath $Built -Destination $OutputPath -Force
    $Record = [ordered]@{
        commit = $Commit
        build = $BuildName
        output = [System.IO.Path]::GetFileName($OutputPath)
        output_sha256 = (Get-FileHash -LiteralPath $OutputPath -Algorithm SHA256).Hash.ToLowerInvariant()
        template_sha256 = (Get-FileHash -LiteralPath $Template -Algorithm SHA256).Hash.ToLowerInvariant()
        built_at = (Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz')
        host = $HostInfo
        components = @($Manifest.components)
        document_modules = @($Manifest.document_modules)
        comparison = @($Comparison | ForEach-Object { [string]$_ })
    }
    [System.IO.File]::WriteAllText($OutputPath + '.build.json', (ConvertTo-Json -InputObject $Record -Depth 5), $Utf8)
    Write-Host "Saved $OutputPath ($BuildName build of $Commit). Compile and run it per docs/EXCEL_EVIDENCE.md."
}
finally {
    if ($null -ne $Book) { $Book.Close($false) | Out-Null; [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($Book) }
    if ($null -ne $Excel) { $Excel.Quit(); [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($Excel) }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    Remove-Item -LiteralPath $Staging -Recurse -Force -ErrorAction SilentlyContinue
}
