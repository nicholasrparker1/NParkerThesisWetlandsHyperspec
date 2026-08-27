param(
    [string]$DatabasePath = "data/raw/KSSL/MIR Spectra_Access_Portable.accdb",
    [string]$OutputDirectory = "outputs/tables/kssl_neon_audit"
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

function Export-Table {
    param([string]$Name, $Table)
    $path = Join-Path $out "$Name.csv"
    $Table | Export-Csv -LiteralPath $path -NoTypeInformation -Encoding utf8
    Write-Output "$Name`: $($Table.Rows.Count) rows"
}

function Get-IntegerList {
    param($Value)
    if ($null -eq $Value -or $Value -is [System.DBNull]) { return @() }
    return @([regex]::Matches([string]$Value, '\d+') | ForEach-Object { [int]$_.Value })
}

function Get-UniqueNonNullCount {
    param($Rows, [string]$Property)
    return @($Rows | ForEach-Object { $_.$Property } |
        Where-Object { $null -ne $_ -and $_ -isnot [System.DBNull] -and [string]$_ -ne '' } |
        Sort-Object -Unique).Count
}

$neonWhere = @"
(UCASE(project.project_source) LIKE '%NEON%'
 OR UCASE(project.lab_proj_name) LIKE '%NEON%'
 OR UCASE(project.submit_proj_name) LIKE '%NEON%'
 OR UCASE(project.proj_note) LIKE '%NEON%')
"@

try {
    # Preserve the relevant schema so every interpretation is auditable.
    $wantedTables = @(
        'project','layer','sample','lims_pedon','lims_site','lims_ped_tax_hist',
        'mir_scan_mas_data','mir_scan_det_data','analyte','calc','result',
        'layer_analyte','area','centroid','site_area_overlap'
    )
    $schema = $connection.GetSchema('Columns') |
        Where-Object { $wantedTables -contains $_.TABLE_NAME } |
        Sort-Object TABLE_NAME, ORDINAL_POSITION |
        Select-Object TABLE_NAME, COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH,
            NUMERIC_PRECISION, NUMERIC_SCALE, ORDINAL_POSITION
    $schema | Export-Csv (Join-Path $out 'schema_relevant_tables.csv') -NoTypeInformation -Encoding utf8

    $projects = Invoke-DataTable @"
SELECT project.proj_id, project.lab_proj_name, project.submit_proj_name,
       project.project_source, project.proj_type, project.fiscal_year,
       project.project_folder_path, project.proj_note
FROM project
WHERE $neonWhere
ORDER BY project.lab_proj_name
"@
    Export-Table 'neon_projects' $projects

    $records = Invoke-DataTable @"
SELECT project.proj_id, project.lab_proj_name, project.submit_proj_name,
       project.project_source, project.project_folder_path,
       layer.lay_id, layer.lay_type, layer.lay_field_label1,
       layer.lay_field_label2, layer.lay_field_label3,
       layer.lay_depth_to_top, layer.lay_depth_to_bottom,
       layer.horizon_designation, layer.texture_description,
       lims_pedon.lims_pedon_id, lims_pedon.user_pedon_id,
       lims_pedon.pedon_unit, lims_pedon.pedon_status,
       lims_site.lims_site_id, lims_site.user_site_id,
       lims_site.horizontal_datum_name,
       lims_site.latitude_std_decimal_degrees,
       lims_site.longitude_std_decimal_degrees,
       sample.smp_id, sample.smp_type, sample.smp_condition,
       sample.smp_status, sample.instr_id
FROM ((((project INNER JOIN layer ON project.proj_id=layer.proj_id)
LEFT JOIN lims_pedon ON layer.lims_pedon_id=lims_pedon.lims_pedon_id)
LEFT JOIN lims_site ON layer.lims_site_id=lims_site.lims_site_id)
LEFT JOIN sample ON layer.lay_id=sample.lay_id)
WHERE $neonWhere
ORDER BY project.lab_proj_name, lims_pedon.user_pedon_id,
         layer.lay_depth_to_top, layer.lay_id, sample.smp_id
"@
    Export-Table 'neon_layer_sample_inventory' $records

    $projectProfiles = foreach ($group in ($records | Group-Object proj_id)) {
        $rows = @($group.Group)
        $first = $rows[0]
        $pedons = Get-UniqueNonNullCount $rows 'lims_pedon_id'
        $sites = Get-UniqueNonNullCount $rows 'lims_site_id'
        $layers = Get-UniqueNonNullCount $rows 'lay_id'
        $samples = Get-UniqueNonNullCount $rows 'smp_id'
        $bottoms = @($rows | ForEach-Object { $_.lay_depth_to_bottom } |
            Where-Object { $null -ne $_ -and $_ -isnot [System.DBNull] -and [string]$_ -ne '' } |
            ForEach-Object { [double]$_ })
        $searchText = @(
            $first.lab_proj_name, $first.submit_proj_name,
            ($rows | ForEach-Object user_pedon_id),
            ($rows | ForEach-Object user_site_id),
            ($rows | ForEach-Object lay_field_label1),
            ($rows | ForEach-Object lay_field_label2),
            ($rows | ForEach-Object lay_field_label3)
        ) -join ' '
        $explicitMega = $searchText -match '(?i)MEGA\s*PIT|MEGAPIT'
        $towerOrCore = $searchText -match '(?i)\bTOWER\b|\bCORE\b'
        $siteC = $searchText -match '(?i)SITE[_ -]?C\b'
        $singleProfileCandidate = ($pedons -eq 1 -and $sites -eq 1 -and $layers -ge 3 -and $layers -le 20)
        [pscustomobject]@{
            proj_id = $first.proj_id
            lab_proj_name = $first.lab_proj_name
            project_focus = $first.submit_proj_name
            project_source = $first.project_source
            unique_sites = $sites
            unique_pedons = $pedons
            unique_layers = $layers
            unique_samples = $samples
            maximum_bottom_depth_cm = if ($bottoms.Count) { ($bottoms | Measure-Object -Maximum).Maximum } else { $null }
            explicit_megapit_text = [int]$explicitMega
            tower_or_core_text = [int]$towerOrCore
            site_c_text = [int]$siteC
            single_profile_candidate = [int]$singleProfileCandidate
            megapit_candidate = [int]($explicitMega -or ($singleProfileCandidate -and -not $siteC))
            candidate_basis = if ($explicitMega) { 'Explicit Megapit text' }
                elseif ($singleProfileCandidate -and $towerOrCore -and -not $siteC) { 'One pedon/site, 3-20 layers, tower/core text' }
                elseif ($singleProfileCandidate -and -not $siteC) { 'One pedon/site and 3-20 layers; external crosswalk required' }
                else { 'Not classified as a Megapit candidate' }
        }
    }
    $projectProfiles | Sort-Object lab_proj_name |
        Export-Csv (Join-Path $out 'neon_project_profiles.csv') -NoTypeInformation -Encoding utf8

    $candidateIds = @($projectProfiles | Where-Object megapit_candidate -eq 1 | ForEach-Object proj_id)
    $candidateIdSql = if ($candidateIds.Count) { $candidateIds -join ',' } else { '-1' }

    $taxonomy = Invoke-DataTable @"
SELECT project.proj_id, project.lab_proj_name, project.submit_proj_name,
       lims_pedon.lims_pedon_id, lims_pedon.user_pedon_id,
       lims_ped_tax_hist.taxonomic_classification_type,
       lims_ped_tax_hist.taxon_name, lims_ped_tax_hist.taxon_kind,
       lims_ped_tax_hist.taxonomic_classification_name,
       lims_ped_tax_hist.taxonomic_order,
       lims_ped_tax_hist.taxonomic_suborder,
       lims_ped_tax_hist.taxonomic_great_group,
       lims_ped_tax_hist.taxonomic_subgroup,
       lims_ped_tax_hist.taxonomic_family_particle_size,
       lims_ped_tax_hist.taxonomic_family_reaction,
       lims_ped_tax_hist.taxonomic_family_temp_class,
       lims_ped_tax_hist.taxonomic_moisture_subclass,
       lims_ped_tax_hist.taxonomic_temp_regime
FROM (((project INNER JOIN layer ON project.proj_id=layer.proj_id)
INNER JOIN lims_pedon ON layer.lims_pedon_id=lims_pedon.lims_pedon_id)
INNER JOIN lims_ped_tax_hist ON lims_pedon.lims_pedon_id=lims_ped_tax_hist.lims_pedon_id)
WHERE $neonWhere
GROUP BY project.proj_id, project.lab_proj_name, project.submit_proj_name,
       lims_pedon.lims_pedon_id, lims_pedon.user_pedon_id,
       lims_ped_tax_hist.taxonomic_classification_type,
       lims_ped_tax_hist.taxon_name, lims_ped_tax_hist.taxon_kind,
       lims_ped_tax_hist.taxonomic_classification_name,
       lims_ped_tax_hist.taxonomic_order,
       lims_ped_tax_hist.taxonomic_suborder,
       lims_ped_tax_hist.taxonomic_great_group,
       lims_ped_tax_hist.taxonomic_subgroup,
       lims_ped_tax_hist.taxonomic_family_particle_size,
       lims_ped_tax_hist.taxonomic_family_reaction,
       lims_ped_tax_hist.taxonomic_family_temp_class,
       lims_ped_tax_hist.taxonomic_moisture_subclass,
       lims_ped_tax_hist.taxonomic_temp_regime
ORDER BY project.lab_proj_name, lims_pedon.user_pedon_id
"@
    Export-Table 'neon_taxonomy' $taxonomy

    $mir = Invoke-DataTable @"
SELECT project.proj_id, project.lab_proj_name, project.submit_proj_name,
       layer.lay_id, lims_pedon.lims_pedon_id, lims_pedon.user_pedon_id,
       sample.smp_id, mir_scan_mas_data.mir_scan_mas_id,
       mir_scan_det_data.mir_scan_det_id, mir_scan_det_data.rep_num,
       mir_scan_det_data.scan_date, mir_scan_det_data.light_source,
       mir_scan_det_data.qc_percent_similar,
       mir_scan_det_data.qc_hit_quality,
       mir_scan_det_data.qc_file_status,
       mir_scan_det_data.scan_file_status,
       mir_scan_det_data.scan_path_name
FROM (((((project INNER JOIN layer ON project.proj_id=layer.proj_id)
LEFT JOIN lims_pedon ON layer.lims_pedon_id=lims_pedon.lims_pedon_id)
INNER JOIN sample ON layer.lay_id=sample.lay_id)
INNER JOIN mir_scan_mas_data ON sample.smp_id=mir_scan_mas_data.smp_id)
INNER JOIN mir_scan_det_data ON mir_scan_mas_data.mir_scan_mas_id=mir_scan_det_data.mir_scan_mas_id)
WHERE $neonWhere
ORDER BY project.lab_proj_name, sample.smp_id, mir_scan_det_data.rep_num
"@
    Export-Table 'neon_mir_scans' $mir

    $propertyReference = Invoke-DataTable @"
SELECT [Soil property name], [Query to use], [calc_ID], [analyte_ID],
       [master_prep_ID*], [Detection limit], [Units of measure], [Field8]
FROM [_soilPropertyReferenceTable]
ORDER BY [Soil property name]
"@

    $propertyCoverage = @()
    foreach ($row in $propertyReference.Rows) {
        $property = [string]$row.'Soil property name'
        $route = [string]$row.'Query to use'
        $analyteIds = Get-IntegerList $row.analyte_ID
        $calcIds = Get-IntegerList $row.calc_ID
        $prepIds = Get-IntegerList $row.'master_prep_ID*'
        $units = [string]$row.'Units of measure'

        if ($route -like 'Measured*' -and $analyteIds.Count -gt 0) {
            $idSql = $analyteIds -join ','
            $prepClause = if ($prepIds.Count) { " AND layer_analyte.master_prep_id IN ($($prepIds -join ','))" } else { '' }
            $baseJoin = @"
FROM ((project INNER JOIN layer ON project.proj_id=layer.proj_id)
INNER JOIN layer_analyte ON layer.lay_id=layer_analyte.lay_id)
WHERE ($neonWhere) AND layer_analyte.analyte_id IN ($idSql)$prepClause
"@
            $all = Invoke-DataTable "SELECT COUNT(*) AS result_rows, SUM(IIF(IsNumeric(layer_analyte.calc_value),1,0)) AS numeric_rows $baseJoin"
            $layers = Invoke-DataTable "SELECT COUNT(*) AS n FROM (SELECT layer.lay_id $baseJoin GROUP BY layer.lay_id) AS q"
            $candidate = Invoke-DataTable "SELECT COUNT(*) AS n FROM (SELECT layer.lay_id $baseJoin AND project.proj_id IN ($candidateIdSql) GROUP BY layer.lay_id) AS q"
            $propertyCoverage += [pscustomobject]@{
                property_name=$property; units=$units; route='measured'; ids=$idSql
                prep_ids=($prepIds -join ','); result_rows=$all.Rows[0].result_rows
                numeric_rows=$all.Rows[0].numeric_rows; neon_layers=$layers.Rows[0].n
                megapit_candidate_layers=$candidate.Rows[0].n
            }
        }
        elseif ($route -like 'Derived*' -and $calcIds.Count -gt 0) {
            $idSql = $calcIds -join ','
            $baseJoin = @"
FROM ((project INNER JOIN layer ON project.proj_id=layer.proj_id)
INNER JOIN result ON layer.lay_id=result.result_source_id)
WHERE ($neonWhere) AND result.result_type='layer' AND result.calc_id IN ($idSql)
"@
            $all = Invoke-DataTable "SELECT COUNT(*) AS result_rows, SUM(IIF(IsNumeric(result.calc_value),1,0)) AS numeric_rows $baseJoin"
            $layers = Invoke-DataTable "SELECT COUNT(*) AS n FROM (SELECT layer.lay_id $baseJoin GROUP BY layer.lay_id) AS q"
            $candidate = Invoke-DataTable "SELECT COUNT(*) AS n FROM (SELECT layer.lay_id $baseJoin AND project.proj_id IN ($candidateIdSql) GROUP BY layer.lay_id) AS q"
            $propertyCoverage += [pscustomobject]@{
                property_name=$property; units=$units; route='derived'; ids=$idSql
                prep_ids=''; result_rows=$all.Rows[0].result_rows
                numeric_rows=$all.Rows[0].numeric_rows; neon_layers=$layers.Rows[0].n
                megapit_candidate_layers=$candidate.Rows[0].n
            }
        }
    }
    $propertyCoverage | Export-Csv (Join-Path $out 'neon_property_coverage.csv') -NoTypeInformation -Encoding utf8

    # Search laboratory analyte/calculation vocabulary for requested morphology/hydric indicators.
    $terms = 'color|chroma|hue|redox|gley|mottle|drain|water table|saturation|flood|pond|mangan|alumin|iron|bulk density|carbon|nitrogen|texture|sand|silt|clay|ph'
    $analytes = Invoke-DataTable "SELECT * FROM analyte"
    $calcs = Invoke-DataTable "SELECT * FROM calc"
    $vocabularyHits = @(
        $analytes | Where-Object { (($_.analyte_name,$_.analyte_abbrev,$_.analyte_code,$_.analyte_desc,$_.analyte_note) -join ' ') -match $terms } |
            ForEach-Object { [pscustomobject]@{ source_table='analyte'; id=$_.analyte_id; name=$_.analyte_name; abbreviation=$_.analyte_abbrev; units=$_.uom_abbrev; description=$_.analyte_desc } }
        $calcs | Where-Object { (($_.calc_name,$_.calc_abbrev,$_.calc_analyte,$_.calc_desc,$_.calc_note) -join ' ') -match $terms } |
            ForEach-Object { [pscustomobject]@{ source_table='calc'; id=$_.calc_id; name=$_.calc_name; abbreviation=$_.calc_abbrev; units=$_.uom_abbrev; description=$_.calc_desc } }
    )
    $vocabularyHits | Export-Csv (Join-Path $out 'hydric_indicator_vocabulary.csv') -NoTypeInformation -Encoding utf8

    $summary = [pscustomobject]@{
        neon_projects = $projects.Rows.Count
        neon_sites = Get-UniqueNonNullCount $records 'lims_site_id'
        neon_pedons = Get-UniqueNonNullCount $records 'lims_pedon_id'
        neon_layers = Get-UniqueNonNullCount $records 'lay_id'
        neon_samples = Get-UniqueNonNullCount $records 'smp_id'
        projects_with_explicit_megapit_text = @($projectProfiles | Where-Object explicit_megapit_text -eq 1).Count
        megapit_candidate_projects = $candidateIds.Count
        megapit_candidate_pedons = Get-UniqueNonNullCount ($records | Where-Object { $candidateIds -contains [int]$_.proj_id }) 'lims_pedon_id'
        megapit_candidate_layers = Get-UniqueNonNullCount ($records | Where-Object { $candidateIds -contains [int]$_.proj_id }) 'lay_id'
        megapit_candidate_samples = Get-UniqueNonNullCount ($records | Where-Object { $candidateIds -contains [int]$_.proj_id }) 'smp_id'
        neon_samples_with_mir = Get-UniqueNonNullCount $mir 'smp_id'
        neon_mir_master_records = Get-UniqueNonNullCount $mir 'mir_scan_mas_id'
        neon_mir_scan_records = Get-UniqueNonNullCount $mir 'mir_scan_det_id'
        records_with_standard_coordinates = @($records | Where-Object {
            $null -ne $_.latitude_std_decimal_degrees -and $_.latitude_std_decimal_degrees -isnot [System.DBNull] -and
            $null -ne $_.longitude_std_decimal_degrees -and $_.longitude_std_decimal_degrees -isnot [System.DBNull]
        } | Select-Object lims_site_id -Unique).Count
    }
    $summary | Export-Csv (Join-Path $out 'neon_summary.csv') -NoTypeInformation -Encoding utf8
}
finally {
    $connection.Close()
}

