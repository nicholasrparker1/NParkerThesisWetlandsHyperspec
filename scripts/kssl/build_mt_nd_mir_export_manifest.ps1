param(
    [string]$DatabasePath = "data/raw/KSSL/MIR Spectra_Access_Portable.accdb",
    [string]$CohortCsv = "outputs/tables/kssl_spatial_results/kssl_mt_nd_spatial_analysis_table.csv",
    [string]$OutputDirectory = "outputs/tables/kssl_mir_cohort"
)

$ErrorActionPreference = "Stop"
$db = (Resolve-Path -LiteralPath $DatabasePath).Path
$cohort = Import-Csv -LiteralPath $CohortCsv
$sampleIds = @($cohort.smp_id | ForEach-Object { [long]$_ } | Sort-Object -Unique)
$out = Join-Path (Get-Location) $OutputDirectory
New-Item -ItemType Directory -Force -Path $out | Out-Null

$connection = New-Object System.Data.OleDb.OleDbConnection(
    "Provider=Microsoft.ACE.OLEDB.12.0;Data Source=$db;Mode=Read;"
)
$connection.Open()

function Read-Query([string]$Sql) {
    $cmd = $connection.CreateCommand(); $cmd.CommandText = $Sql
    $adapter = New-Object System.Data.OleDb.OleDbDataAdapter($cmd)
    $table = New-Object System.Data.DataTable
    [void]$adapter.Fill($table)
    return $table.Rows
}

try {
    $chunks = for ($i=0; $i -lt $sampleIds.Count; $i+=100) {
        ,$sampleIds[$i..([math]::Min($i+99,$sampleIds.Count-1))]
    }
    $all = foreach ($chunk in $chunks) {
        $ids = $chunk -join ','
        Read-Query @"
SELECT x.smp_id, l.lay_id, p.lab_proj_name,
       m.mir_scan_mas_id, d.mir_scan_det_id, d.rep_num,
       d.qc_file_status, d.scan_file_status, d.scan_date,
       d.scan_path_name, d.qc_percent_similar, d.qc_hit_quality
FROM (((sample AS x
INNER JOIN layer AS l ON x.lay_id=l.lay_id)
INNER JOIN project AS p ON l.proj_id=p.proj_id)
INNER JOIN mir_scan_mas_data AS m ON x.smp_id=m.smp_id)
INNER JOIN mir_scan_det_data AS d ON m.mir_scan_mas_id=d.mir_scan_mas_id
WHERE x.smp_id IN ($ids)
ORDER BY x.smp_id, m.mir_scan_mas_id, d.rep_num
"@
    }
    $manifest = $all | ForEach-Object {
        [pscustomobject]@{
            smp_id = $_.smp_id; lay_id = $_.lay_id; lab_proj_name = $_.lab_proj_name
            mir_scan_mas_id = $_.mir_scan_mas_id; mir_scan_det_id = $_.mir_scan_det_id
            rep_num = $_.rep_num; qc_file_status = $_.qc_file_status
            scan_file_status = $_.scan_file_status; scan_date = $_.scan_date
            scan_path_name = $_.scan_path_name; qc_percent_similar = $_.qc_percent_similar
            qc_hit_quality = $_.qc_hit_quality
            expected_relative_path = Join-Path "MIR_Library" (Join-Path ([string]$_.lab_proj_name) ([string]$_.scan_path_name))
        }
    }
    $manifest | Export-Csv -LiteralPath (Join-Path $out 'mt_nd_mir_scan_manifest.csv') -NoTypeInformation -Encoding utf8

    $cohortIndex = @{}; foreach($r in $cohort){ $cohortIndex[[string]$r.smp_id]=$r }
    $sampleSummary = $manifest | Group-Object smp_id | ForEach-Object {
        $g = $_.Group; $c = $cohortIndex[[string]$_.Name]
        [pscustomobject]@{
            smp_id=[long]$_.Name; lay_id=$c.lay_id; state=$c.state
            spatial_evidence_group=$c.spatial_evidence_group
            hydric_evidence_tier=$c.hydric_evidence_tier
            master_count=($g.mir_scan_mas_id | Sort-Object -Unique).Count
            scan_count=$g.Count
            passed_scan_count=($g | Where-Object qc_file_status -eq 'Passed').Count
            project_count=($g.lab_proj_name | Sort-Object -Unique).Count
        }
    }
    $sampleSummary | Sort-Object smp_id | Export-Csv -LiteralPath (Join-Path $out 'mt_nd_mir_sample_summary.csv') -NoTypeInformation -Encoding utf8

    $idText = $sampleIds -join ','
    $sql = @"
SELECT p.lab_proj_name, x.smp_id, l.lay_id,
       m.mir_scan_mas_id, d.mir_scan_det_id, d.rep_num,
       d.qc_file_status, d.scan_file_status, d.scan_date,
       d.scan_path_name, d.qc_percent_similar, d.qc_hit_quality
FROM (((sample AS x
INNER JOIN layer AS l ON x.lay_id=l.lay_id)
INNER JOIN project AS p ON l.proj_id=p.proj_id)
INNER JOIN mir_scan_mas_data AS m ON x.smp_id=m.smp_id)
INNER JOIN mir_scan_det_data AS d ON m.mir_scan_mas_id=d.mir_scan_mas_id
WHERE x.smp_id IN ($idText)
ORDER BY p.lab_proj_name, x.smp_id, m.mir_scan_mas_id, d.rep_num;
"@
    Set-Content -LiteralPath (Join-Path $out 'Access_SQL_MT_ND_MIR_scans.txt') -Value $sql -Encoding utf8

    $projectSummary = $manifest | Group-Object lab_proj_name | ForEach-Object {
        [pscustomobject]@{
            lab_proj_name=$_.Name
            sample_count=($_.Group.smp_id | Sort-Object -Unique).Count
            scan_count=$_.Count
        }
    } | Sort-Object lab_proj_name
    $projectSummary | Export-Csv -LiteralPath (Join-Path $out 'mt_nd_mir_project_copy_list.csv') -NoTypeInformation -Encoding utf8

    Write-Output "Cohort samples: $($sampleIds.Count)"
    Write-Output "Manifest scans: $($manifest.Count)"
    Write-Output "Projects required: $($projectSummary.Count)"
}
finally { $connection.Close() }

