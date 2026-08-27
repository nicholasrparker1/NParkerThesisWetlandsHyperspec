param(
    [string]$DatabasePath = "data/raw/KSSL/MIR Spectra_Access_Portable.accdb",
    [string]$OutputDirectory = "outputs/tables/kssl_audit"
)

$ErrorActionPreference = "Stop"

$db = (Resolve-Path -LiteralPath $DatabasePath).Path
$out = Join-Path (Get-Location) $OutputDirectory
New-Item -ItemType Directory -Path $out -Force | Out-Null

$connection = New-Object System.Data.OleDb.OleDbConnection(
    "Provider=Microsoft.ACE.OLEDB.12.0;Data Source=$db;Mode=Read;"
)
$connection.Open()

function Invoke-DataTable {
    param([string]$Sql)
    $command = $connection.CreateCommand()
    $command.CommandText = $Sql
    $adapter = New-Object System.Data.OleDb.OleDbDataAdapter($command)
    $table = New-Object System.Data.DataTable
    [void]$adapter.Fill($table)
    return ,$table
}

function Export-Query {
    param([string]$Name, [string]$Sql)
    $table = Invoke-DataTable -Sql $Sql
    $path = Join-Path $out "$Name.csv"
    $table | Export-Csv -LiteralPath $path -NoTypeInformation -Encoding utf8
    Write-Output "$Name`: $($table.Rows.Count) rows"
}

function Get-IntegerList {
    param($Value)
    if ($null -eq $Value -or $Value -is [System.DBNull]) { return @() }
    return @([regex]::Matches([string]$Value, '\d+') | ForEach-Object { [int]$_.Value })
}

try {
    $entityTables = @(
        '_soilPropertyReferenceTable', 'analyte', 'area', 'calc', 'centroid',
        'layer', 'layer_analyte', 'lims_ped_tax_hist', 'lims_pedon', 'lims_site',
        'mir_scan_det_data', 'mir_scan_mas_data', 'project', 'result', 'sample',
        'site_area_overlap'
    )
    $counts = foreach ($name in $entityTables) {
        $n = (Invoke-DataTable "SELECT COUNT(*) AS n FROM [$name]").Rows[0].n
        [pscustomobject]@{ table_name = $name; row_count = [long]$n }
    }
    $counts | Export-Csv (Join-Path $out 'table_counts.csv') -NoTypeInformation -Encoding utf8

    $propertyReference = Invoke-DataTable @"
SELECT [Soil property name], [Query to use], [calc_ID], [analyte_ID],
       [master_prep_ID*], [Detection limit], [Units of measure], [Field8]
FROM [_soilPropertyReferenceTable]
ORDER BY [Soil property name]
"@
    $propertyReference | Export-Csv (Join-Path $out 'property_reference.csv') -NoTypeInformation -Encoding utf8

    Export-Query 'mir_masters_per_sample' @"
SELECT q.masters_per_sample, COUNT(*) AS sample_count
FROM (
    SELECT smp_id, COUNT(*) AS masters_per_sample
    FROM mir_scan_mas_data
    GROUP BY smp_id
) AS q
GROUP BY q.masters_per_sample
ORDER BY q.masters_per_sample
"@

    Export-Query 'mir_scans_per_master' @"
SELECT q.scans_per_master, COUNT(*) AS master_count
FROM (
    SELECT mir_scan_mas_id, COUNT(*) AS scans_per_master
    FROM mir_scan_det_data
    GROUP BY mir_scan_mas_id
) AS q
GROUP BY q.scans_per_master
ORDER BY q.scans_per_master
"@

    Export-Query 'mir_replicate_numbers' @"
SELECT rep_num, COUNT(*) AS scan_count
FROM mir_scan_det_data
GROUP BY rep_num
ORDER BY rep_num
"@

    Export-Query 'mir_scan_status' @"
SELECT qc_file_status, scan_file_status, COUNT(*) AS scan_count
FROM mir_scan_det_data
GROUP BY qc_file_status, scan_file_status
ORDER BY COUNT(*) DESC
"@

    Export-Query 'mir_rescanned_samples' @"
SELECT m.smp_id, COUNT(*) AS master_count, MIN(d.scan_date) AS first_scan,
       MAX(d.scan_date) AS last_scan, COUNT(d.mir_scan_det_id) AS scan_count
FROM mir_scan_mas_data AS m LEFT JOIN mir_scan_det_data AS d
ON m.mir_scan_mas_id = d.mir_scan_mas_id
GROUP BY m.smp_id
HAVING COUNT(*) > 4
ORDER BY COUNT(*) DESC, m.smp_id
"@

    Export-Query 'sample_context_coverage' @"
SELECT COUNT(*) AS sample_rows,
       SUM(IIF(l.lay_depth_to_top IS NOT NULL,1,0)) AS with_top_depth,
       SUM(IIF(l.lay_depth_to_bottom IS NOT NULL,1,0)) AS with_bottom_depth,
       SUM(IIF(l.horizon_designation IS NOT NULL,1,0)) AS with_horizon,
       SUM(IIF(s.latitude_std_decimal_degrees IS NOT NULL AND s.longitude_std_decimal_degrees IS NOT NULL,1,0)) AS with_standard_coordinates,
       SUM(IIF(p.user_pedon_id IS NOT NULL,1,0)) AS with_user_pedon_id
FROM ((sample AS x INNER JOIN layer AS l ON x.lay_id=l.lay_id)
INNER JOIN lims_pedon AS p ON l.lims_pedon_id=p.lims_pedon_id)
INNER JOIN lims_site AS s ON l.lims_site_id=s.lims_site_id
"@

    Export-Query 'samples_per_layer' @"
SELECT q.samples_per_layer, COUNT(*) AS layer_count
FROM (SELECT lay_id, COUNT(*) AS samples_per_layer FROM sample GROUP BY lay_id) AS q
GROUP BY q.samples_per_layer
ORDER BY q.samples_per_layer
"@

    Export-Query 'site_area_overlap_multiplicity' @"
SELECT q.area_links, COUNT(*) AS site_count
FROM (SELECT lims_site_id, COUNT(*) AS area_links FROM site_area_overlap GROUP BY lims_site_id) AS q
GROUP BY q.area_links
ORDER BY q.area_links
"@

    Export-Query 'taxonomy_history_multiplicity' @"
SELECT q.taxonomy_records, COUNT(*) AS pedon_count
FROM (SELECT lims_pedon_id, COUNT(*) AS taxonomy_records FROM lims_ped_tax_hist GROUP BY lims_pedon_id) AS q
GROUP BY q.taxonomy_records
ORDER BY q.taxonomy_records
"@

    $coverage = @()
    $methodBreakdown = @()
    foreach ($row in $propertyReference.Rows) {
        $property = [string]$row.'Soil property name'
        $route = [string]$row.'Query to use'
        $analyteIds = Get-IntegerList $row.analyte_ID
        $calcIds = Get-IntegerList $row.calc_ID
        $prepIds = Get-IntegerList $row.'master_prep_ID*'

        if ($route -like 'Measured*' -and $analyteIds.Count -gt 0) {
            $idSql = $analyteIds -join ','
            $prepClause = if ($prepIds.Count) { " AND la.master_prep_id IN ($($prepIds -join ','))" } else { '' }
            $summary = Invoke-DataTable @"
SELECT COUNT(*) AS result_rows,
       SUM(IIF(IsNumeric(la.calc_value),1,0)) AS numeric_rows,
       COUNT(la.calc_value) AS nonnull_rows
FROM layer_analyte AS la
WHERE la.analyte_id IN ($idSql)$prepClause
"@
            $layers = Invoke-DataTable @"
SELECT COUNT(*) AS n FROM (
    SELECT la.lay_id FROM layer_analyte AS la
    WHERE la.analyte_id IN ($idSql)$prepClause
    GROUP BY la.lay_id
) AS q
"@
            $mirLayers = Invoke-DataTable @"
SELECT COUNT(*) AS n FROM (
    SELECT la.lay_id
    FROM ((layer_analyte AS la INNER JOIN sample AS s ON la.lay_id=s.lay_id)
    INNER JOIN mir_scan_mas_data AS m ON s.smp_id=m.smp_id)
    WHERE la.analyte_id IN ($idSql)$prepClause
    GROUP BY la.lay_id
) AS q
"@
            $coverage += [pscustomobject]@{
                property_name=$property; route='measured'; ids=$idSql
                prep_ids=($prepIds -join ','); result_rows=$summary.Rows[0].result_rows
                numeric_rows=$summary.Rows[0].numeric_rows; nonnull_rows=$summary.Rows[0].nonnull_rows
                unique_layers=$layers.Rows[0].n; layers_with_mir=$mirLayers.Rows[0].n
            }
            $methods = Invoke-DataTable @"
SELECT la.analyte_id, a.analyte_name, a.analyte_method_code, a.uom_abbrev,
       la.proced_id, la.master_prep_id, la.size_frac, la.instr_set_id,
       la.lab_id, la.reliability, COUNT(*) AS result_rows
FROM layer_analyte AS la INNER JOIN analyte AS a ON la.analyte_id=a.analyte_id
WHERE la.analyte_id IN ($idSql)$prepClause
GROUP BY la.analyte_id, a.analyte_name, a.analyte_method_code, a.uom_abbrev,
         la.proced_id, la.master_prep_id, la.size_frac, la.instr_set_id,
         la.lab_id, la.reliability
ORDER BY COUNT(*) DESC
"@
            foreach ($m in $methods.Rows) {
                $methodBreakdown += [pscustomobject]@{
                    property_name=$property; route='measured'; definition_id=$m.analyte_id
                    definition_name=$m.analyte_name; method_code=$m.analyte_method_code
                    units=$m.uom_abbrev; procedure_id=$m.proced_id; preparation_id=$m.master_prep_id
                    size_fraction=$m.size_frac; instrument_set_id=$m.instr_set_id
                    lab_id=$m.lab_id; reliability=$m.reliability; result_rows=$m.result_rows
                }
            }
        }
        elseif ($route -like 'Derived*' -and $calcIds.Count -gt 0) {
            $idSql = $calcIds -join ','
            $summary = Invoke-DataTable @"
SELECT COUNT(*) AS result_rows,
       SUM(IIF(IsNumeric(r.calc_value),1,0)) AS numeric_rows,
       COUNT(r.calc_value) AS nonnull_rows
FROM result AS r
WHERE r.result_type='layer' AND r.calc_id IN ($idSql)
"@
            $layers = Invoke-DataTable @"
SELECT COUNT(*) AS n FROM (
    SELECT r.result_source_id FROM result AS r
    WHERE r.result_type='layer' AND r.calc_id IN ($idSql)
    GROUP BY r.result_source_id
) AS q
"@
            $mirLayers = Invoke-DataTable @"
SELECT COUNT(*) AS n FROM (
    SELECT r.result_source_id
    FROM ((result AS r INNER JOIN sample AS s ON r.result_source_id=s.lay_id)
    INNER JOIN mir_scan_mas_data AS m ON s.smp_id=m.smp_id)
    WHERE r.result_type='layer' AND r.calc_id IN ($idSql)
    GROUP BY r.result_source_id
) AS q
"@
            $coverage += [pscustomobject]@{
                property_name=$property; route='derived'; ids=$idSql; prep_ids=''
                result_rows=$summary.Rows[0].result_rows; numeric_rows=$summary.Rows[0].numeric_rows
                nonnull_rows=$summary.Rows[0].nonnull_rows; unique_layers=$layers.Rows[0].n
                layers_with_mir=$mirLayers.Rows[0].n
            }
            $methods = Invoke-DataTable @"
SELECT r.calc_id, c.calc_name, c.calc_type, c.uom_abbrev, r.size_frac,
       r.lab_id, r.reliability, COUNT(*) AS result_rows
FROM result AS r INNER JOIN calc AS c ON r.calc_id=c.calc_id
WHERE r.result_type='layer' AND r.calc_id IN ($idSql)
GROUP BY r.calc_id, c.calc_name, c.calc_type, c.uom_abbrev,
         r.size_frac, r.lab_id, r.reliability
ORDER BY COUNT(*) DESC
"@
            foreach ($m in $methods.Rows) {
                $methodBreakdown += [pscustomobject]@{
                    property_name=$property; route='derived'; definition_id=$m.calc_id
                    definition_name=$m.calc_name; method_code=$m.calc_type; units=$m.uom_abbrev
                    procedure_id=''; preparation_id=''; size_fraction=$m.size_frac
                    instrument_set_id=''; lab_id=$m.lab_id; reliability=$m.reliability
                    result_rows=$m.result_rows
                }
            }
        }
    }
    $coverage | Export-Csv (Join-Path $out 'property_coverage.csv') -NoTypeInformation -Encoding utf8
    $methodBreakdown | Export-Csv (Join-Path $out 'property_method_breakdown.csv') -NoTypeInformation -Encoding utf8

    Export-Query 'project_inventory' @"
SELECT p.proj_id, p.lab_proj_name, p.submit_proj_name AS project_focus,
       p.fiscal_year, p.project_source, COUNT(l.lay_id) AS layer_count
FROM project AS p LEFT JOIN layer AS l ON p.proj_id=l.proj_id
GROUP BY p.proj_id, p.lab_proj_name, p.submit_proj_name,
         p.fiscal_year, p.project_source
ORDER BY COUNT(l.lay_id) DESC
"@
}
finally {
    $connection.Close()
}

Write-Output "Audit outputs written to $out"
