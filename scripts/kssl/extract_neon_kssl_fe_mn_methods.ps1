param(
    [string]$DatabasePath = "data/raw/KSSL/MIR Spectra_Access_Portable.accdb",
    [string]$OutputPath = "outputs/tables/kssl_neon_linkage/neon_kssl_fe_mn_measurements.csv"
)

$ErrorActionPreference = "Stop"
$db = (Resolve-Path -LiteralPath $DatabasePath).Path
$target = Join-Path (Get-Location) $OutputPath
New-Item -ItemType Directory -Path (Split-Path $target) -Force | Out-Null
$cn = New-Object System.Data.OleDb.OleDbConnection(
    "Provider=Microsoft.ACE.OLEDB.12.0;Data Source=$db;Mode=Read;"
)
$cn.Open()
try {
    $sql = @"
SELECT l.lims_pedon_id, l.lay_id, a.analyte_id, a.analyte_name,
 a.analyte_abbrev, a.analyte_method_code, a.uom_abbrev,
 la.proced_id, la.master_prep_id, la.size_frac, la.instr_set_id,
 la.calc_value, la.reliability
FROM (((project INNER JOIN layer l ON project.proj_id=l.proj_id)
 INNER JOIN layer_analyte la ON l.lay_id=la.lay_id)
 INNER JOIN analyte a ON la.analyte_id=a.analyte_id)
WHERE (UCASE(project.project_source) LIKE '%NEON%'
 OR UCASE(project.lab_proj_name) LIKE '%NEON%'
 OR UCASE(project.submit_proj_name) LIKE '%NEON%'
 OR UCASE(project.proj_note) LIKE '%NEON%')
 AND (UCASE(a.analyte_name) LIKE 'IRON,%'
 OR UCASE(a.analyte_name) LIKE 'MANGANESE,%')
"@
    $cmd = $cn.CreateCommand()
    $cmd.CommandText = $sql
    $adapter = New-Object System.Data.OleDb.OleDbDataAdapter($cmd)
    $table = New-Object System.Data.DataTable
    [void]$adapter.Fill($table)
    $table | Export-Csv -LiteralPath $target -NoTypeInformation -Encoding utf8
    Write-Output "NEON Fe/Mn measurements: $($table.Rows.Count) rows"
}
finally {
    $cn.Close()
}
