param(
    [string]$DatabasePath = "data/raw/KSSL/MIR Spectra_Access_Portable.accdb",
    [string]$OutputPath = "outputs/tables/kssl_neon_linkage/sample_date_identifiers.csv"
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
SELECT l.lims_pedon_id, x.smp_id, x.smp_submit_id, x.smp_rcvd_date_id,
 x.smp_login_date_id, x.smp_type, x.smp_condition, x.smp_status
FROM ((project INNER JOIN layer l ON project.proj_id=l.proj_id)
 INNER JOIN sample x ON l.lay_id=x.lay_id)
WHERE UCASE(project.project_source) LIKE '%NEON%'
 OR UCASE(project.lab_proj_name) LIKE '%NEON%'
 OR UCASE(project.submit_proj_name) LIKE '%NEON%'
 OR UCASE(project.proj_note) LIKE '%NEON%'
"@
    $cmd = $cn.CreateCommand()
    $cmd.CommandText = $sql
    $adapter = New-Object System.Data.OleDb.OleDbDataAdapter($cmd)
    $table = New-Object System.Data.DataTable
    [void]$adapter.Fill($table)
    $table | Export-Csv -LiteralPath $target -NoTypeInformation -Encoding utf8
    Write-Output "sample_date_identifiers: $($table.Rows.Count) rows"
}
finally {
    $cn.Close()
}
