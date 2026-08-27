param(
    [string]$DatabasePath = "data/raw/KSSL/MIR Spectra_Access_Portable.accdb",
    [string]$OutputDirectory = "outputs/tables/kssl_neon_linkage"
)

$ErrorActionPreference = "Stop"
$db = (Resolve-Path -LiteralPath $DatabasePath).Path
$out = Join-Path (Get-Location) $OutputDirectory
New-Item -ItemType Directory -Path $out -Force | Out-Null
$cn = New-Object System.Data.OleDb.OleDbConnection(
    "Provider=Microsoft.ACE.OLEDB.12.0;Data Source=$db;Mode=Read;"
)
$cn.Open()

function Export-Query([string]$Name, [string]$Sql) {
    $cmd = $cn.CreateCommand()
    $cmd.CommandText = $Sql
    $adapter = New-Object System.Data.OleDb.OleDbDataAdapter($cmd)
    $table = New-Object System.Data.DataTable
    [void]$adapter.Fill($table)
    $table | Export-Csv -LiteralPath (Join-Path $out "$Name.csv") -NoTypeInformation -Encoding utf8
    Write-Output "$Name`: $($table.Rows.Count) rows"
}

$neon = @"
(UCASE(project.project_source) LIKE '%NEON%'
 OR UCASE(project.lab_proj_name) LIKE '%NEON%'
 OR UCASE(project.submit_proj_name) LIKE '%NEON%'
 OR UCASE(project.proj_note) LIKE '%NEON%')
"@

try {
    Export-Query "pedon_site_project_identifiers" @"
SELECT DISTINCT p.lims_pedon_id, p.natural_key AS lims_pedon_natural_key,
 p.user_pedon_id, p.observation_date_id, p.pedon_unit, p.pedon_status,
 p.part_size_cntrl_depth_to_top, p.part_size_cntrl_depth_to_bot,
 s.lims_site_id, s.user_site_id, s.horizontal_datum_name,
 s.latitude_degrees, s.latitude_minutes, s.latitude_seconds, s.latitude_direction,
 s.longitude_degrees, s.longitude_minutes, s.longitude_seconds, s.longitude_direction,
 s.latitude_std_decimal_degrees, s.longitude_std_decimal_degrees,
 project.proj_id, project.lab_proj_name, project.submit_proj_name,
 project.project_source, project.proj_type, project.proj_status, project.fiscal_year,
 project.proj_submit_date_id, project.proj_export_date_id, project.proj_due_date_id,
 project.proj_est_comp_date_id, project.project_folder_path, project.proj_note
FROM (((project INNER JOIN layer l ON project.proj_id=l.proj_id)
 INNER JOIN lims_pedon p ON l.lims_pedon_id=p.lims_pedon_id)
 INNER JOIN lims_site s ON p.lims_site_id=s.lims_site_id)
WHERE $neon
"@

    Export-Query "site_area_identifiers" @"
SELECT DISTINCT l.lims_pedon_id, s.lims_site_id, a.area_id, a.area_type,
 a.area_sub_type, a.area_code, a.area_name, a.area_abbrev, a.parent_area_id
FROM ((((project INNER JOIN layer l ON project.proj_id=l.proj_id)
 INNER JOIN lims_site s ON l.lims_site_id=s.lims_site_id)
 INNER JOIN site_area_overlap o ON s.lims_site_id=o.lims_site_id)
 INNER JOIN area a ON o.area_id=a.area_id)
WHERE $neon
"@

    Export-Query "taxonomy_history_full" @"
SELECT DISTINCT l.lims_pedon_id, t.lims_pedon_tax_hist_id, t.taxonomic_edition,
 t.taxonomic_classification_date_id, t.taxonomic_classification_type,
 t.taxon_name, t.taxon_kind, t.series_status, t.taxonomic_classification_name,
 t.taxonomic_order, t.taxonomic_suborder, t.taxonomic_great_group,
 t.taxonomic_subgroup, t.taxonomic_family_particle_size,
 t.taxonomic_family_part_size_mod, t.taxonomic_family_c_e_act_class,
 t.taxonomic_family_reaction, t.taxonomic_family_temp_class,
 t.taxonomic_family_haht_mat_class, t.taxonomic_moisture_subclass,
 t.taxonomic_temp_regime
FROM ((project INNER JOIN layer l ON project.proj_id=l.proj_id)
 INNER JOIN lims_ped_tax_hist t ON l.lims_pedon_id=t.lims_pedon_id)
WHERE $neon
"@
}
finally {
    $cn.Close()
}
