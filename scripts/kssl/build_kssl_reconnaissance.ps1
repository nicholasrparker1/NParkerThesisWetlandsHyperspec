param(
    [string]$DatabasePath = "data/raw/KSSL/MIR Spectra_Access_Portable.accdb",
    [string]$OutputDirectory = "outputs/tables/kssl_reconnaissance"
)

$ErrorActionPreference = "Stop"
$db = (Resolve-Path -LiteralPath $DatabasePath).Path
$out = Join-Path (Get-Location) $OutputDirectory
New-Item -ItemType Directory -Path $out -Force | Out-Null
$cn = New-Object System.Data.OleDb.OleDbConnection("Provider=Microsoft.ACE.OLEDB.12.0;Data Source=$db;Mode=Read;")
$cn.Open()

function Query([string]$sql) {
    $cmd = $cn.CreateCommand(); $cmd.CommandText = $sql
    $da = New-Object System.Data.OleDb.OleDbDataAdapter($cmd)
    $dt = New-Object System.Data.DataTable; [void]$da.Fill($dt); return ,$dt
}
function Export([string]$name, $rows) {
    $rows | Export-Csv -LiteralPath (Join-Path $out "$name.csv") -NoTypeInformation -Encoding utf8
    Write-Output "$name`: $(@($rows).Count) rows"
}
function Present($v) { return ($null -ne $v -and $v -isnot [DBNull] -and [string]$v -ne '') }

try {
    $horizons = Query @"
SELECT l.lay_id, l.lims_pedon_id, p.user_pedon_id, l.lims_site_id, s.user_site_id,
       l.proj_id, j.lab_proj_name, j.submit_proj_name, j.project_source,
       l.lay_rpt_seq_num, l.lay_type, l.lay_field_label1, l.lay_field_label2,
       l.lay_field_label3, l.lay_depth_to_top, l.lay_depth_to_bottom,
       l.horizon_designation, l.horz_desgn_discontinuity, l.horz_desgn_master,
       l.horz_desgn_master_prime, l.horz_desgn_vertical_subdvn,
       l.stratified_textures_flag, l.texture_description, l.texture_desc_abbrev,
       s.latitude_std_decimal_degrees, s.longitude_std_decimal_degrees,
       s.horizontal_datum_name,
       (SELECT COUNT(*) FROM sample x WHERE x.lay_id=l.lay_id) AS sample_count,
       (SELECT COUNT(*) FROM sample x INNER JOIN mir_scan_mas_data m ON x.smp_id=m.smp_id
        WHERE x.lay_id=l.lay_id) AS mir_master_count
FROM (((layer l LEFT JOIN lims_pedon p ON l.lims_pedon_id=p.lims_pedon_id)
LEFT JOIN lims_site s ON l.lims_site_id=s.lims_site_id)
LEFT JOIN project j ON l.proj_id=j.proj_id)
ORDER BY l.lims_pedon_id, l.lay_depth_to_top, l.lay_depth_to_bottom, l.lay_rpt_seq_num, l.lay_id
"@

    $tax = Query @"
SELECT lims_pedon_id, COUNT(*) AS taxonomy_record_count,
       MAX(taxon_name) AS example_taxon_name, MAX(taxonomic_order) AS example_taxonomic_order,
       MAX(taxonomic_suborder) AS example_taxonomic_suborder,
       MAX(taxonomic_great_group) AS example_taxonomic_great_group,
       MAX(taxonomic_subgroup) AS example_taxonomic_subgroup
FROM lims_ped_tax_hist GROUP BY lims_pedon_id
"@
    $taxByPedon = @{}; foreach ($r in $tax.Rows) { $taxByPedon[[string]$r.lims_pedon_id] = $r }

    $definitions = Query "SELECT analyte_id AS definition_id, analyte_name AS definition_name, analyte_method_code AS method_code, uom_abbrev AS units, 'measured' AS route FROM analyte UNION ALL SELECT calc_id, calc_name, calc_type, uom_abbrev, 'derived' FROM calc"
    $groups = [ordered]@{
        organic_carbon='(?i)organic carbon'; total_carbon='(?i)carbon, total|total carbon';
        iron='(?i)^iron[, ]|\biron\b'; manganese='(?i)^manganese[, ]|\bmanganese\b';
        clay='(?i)^clay\b|clay, total'; sand='(?i)^sand\b|sand, total'; silt='(?i)^silt\b|silt, total';
        ph='(?i)^pH\b|soil.*pH'; cec='(?i)cation exchange capacity|^CEC\b';
        water_retention='(?i)water retention|water content'; total_nitrogen='(?i)nitrogen, total|total nitrogen'
    }
    $pedonFlags = @{}; $methodRows = @()
    foreach ($groupName in $groups.Keys) {
        $matches = @($definitions.Rows | Where-Object { [string]$_.definition_name -match $groups[$groupName] })
        foreach ($m in $matches) {
            $methodRows += [pscustomobject]@{ measurement_group=$groupName; route=$m.route; definition_id=$m.definition_id; definition_name=$m.definition_name; method_code=$m.method_code; units=$m.units }
        }
        foreach ($route in @('measured','derived')) {
            $ids = @($matches | Where-Object route -eq $route | ForEach-Object definition_id)
            if (-not $ids.Count) { continue }
            $idSql = $ids -join ','
            $sql = if ($route -eq 'measured') {
                "SELECT l.lims_pedon_id, COUNT(*) AS result_rows, COUNT(DISTINCT la.lay_id) AS layer_count FROM (layer l INNER JOIN layer_analyte la ON l.lay_id=la.lay_id) WHERE la.analyte_id IN ($idSql) AND la.calc_value IS NOT NULL GROUP BY l.lims_pedon_id"
            } else {
                "SELECT l.lims_pedon_id, COUNT(*) AS result_rows, COUNT(DISTINCT r.result_source_id) AS layer_count FROM (layer l INNER JOIN result r ON l.lay_id=r.result_source_id) WHERE r.result_type='layer' AND r.calc_id IN ($idSql) AND r.calc_value IS NOT NULL GROUP BY l.lims_pedon_id"
            }
            foreach ($r in (Query $sql).Rows) {
                $key=[string]$r.lims_pedon_id; if (-not $pedonFlags.ContainsKey($key)) { $pedonFlags[$key]=@{} }
                $pedonFlags[$key][$groupName]=1
            }
        }
    }

    $summary = @()
    foreach ($g in ($horizons.Rows | Group-Object lims_pedon_id)) {
        $rows=@($g.Group); $first=$rows[0]; $tops=@(); $bottoms=@(); $allDepths=$true; $invalid=$false
        foreach($r in $rows) {
            if ((Present $r.lay_depth_to_top) -and (Present $r.lay_depth_to_bottom)) {
                $t=[double]$r.lay_depth_to_top; $b=[double]$r.lay_depth_to_bottom; $tops+=$t; $bottoms+=$b
                if($b -le $t){$invalid=$true}
            } else {$allDepths=$false}
        }
        $ordered=@($rows | Where-Object {(Present $_.lay_depth_to_top) -and (Present $_.lay_depth_to_bottom)} | Sort-Object {[double]$_.lay_depth_to_top},{[double]$_.lay_depth_to_bottom})
        $overlap=$false; for($i=1;$i -lt $ordered.Count;$i++){if([double]$ordered[$i].lay_depth_to_top -lt [double]$ordered[$i-1].lay_depth_to_bottom){$overlap=$true}}
        $surface=if($ordered.Count){$ordered[0]}else{$null}; $key=[string]$first.lims_pedon_id
        $f=if($pedonFlags.ContainsKey($key)){$pedonFlags[$key]}else{@{}}
        $taxrow=if($taxByPedon.ContainsKey($key)){$taxByPedon[$key]}else{$null}
        $coord=($rows | Where-Object {(Present $_.latitude_std_decimal_degrees) -and (Present $_.longitude_std_decimal_degrees)} | Measure-Object).Count -gt 0
        $mirLayers=@($rows | Where-Object {[int]$_.mir_master_count -gt 0}).Count
        $summary += [pscustomobject]@{
            lims_pedon_id=$first.lims_pedon_id; user_pedon_id=$first.user_pedon_id; lims_site_id=$first.lims_site_id
            horizon_count=$rows.Count; horizons_with_both_depths=$ordered.Count; maximum_depth_cm=if($bottoms.Count){($bottoms|Measure-Object -Maximum).Maximum}else{$null}
            surface_horizon_designation=if($surface){$surface.horizon_designation}else{$null}; surface_top_cm=if($surface){$surface.lay_depth_to_top}else{$null}; surface_bottom_cm=if($surface){$surface.lay_depth_to_bottom}else{$null}
            surface_thickness_cm=if($surface){[double]$surface.lay_depth_to_bottom-[double]$surface.lay_depth_to_top}else{$null}
            has_coordinates=[int]$coord; has_taxonomy=[int]($null-ne $taxrow); has_horizon_depths=[int]($ordered.Count -gt 0)
            has_complete_depths=[int]$allDepths; has_horizon_designations=[int](($rows|Where-Object {Present $_.horizon_designation}).Count -gt 0)
            has_texture_description=[int](($rows|Where-Object {(Present $_.texture_description) -or (Present $_.texture_desc_abbrev)}).Count -gt 0)
            has_wetness_horizon_designation=[int](($rows|Where-Object {[string]$_.horizon_designation -match '(?i)g'}).Count -gt 0)
            has_samples=[int](($rows|Where-Object {[int]$_.sample_count -gt 0}).Count -gt 0); has_MIR=[int]($mirLayers -gt 0); mir_horizon_count=$mirLayers
            has_organic_carbon=[int]($f.organic_carbon -eq 1); has_total_carbon=[int]($f.total_carbon -eq 1); has_Fe=[int]($f.iron -eq 1); has_Mn=[int]($f.manganese -eq 1)
            has_clay=[int]($f.clay -eq 1); has_sand=[int]($f.sand -eq 1); has_silt=[int]($f.silt -eq 1); has_pH=[int]($f.ph -eq 1); has_CEC=[int]($f.cec -eq 1); has_water_retention=[int]($f.water_retention -eq 1)
            structurally_reconstructable_profile=[int]($allDepths -and -not $invalid -and -not $overlap -and $ordered.Count -eq $rows.Count)
            reaches_10_cm=[int](($bottoms|Where-Object {$_ -ge 10}).Count -gt 0); reaches_20_cm=[int](($bottoms|Where-Object {$_ -ge 20}).Count -gt 0); reaches_30_cm=[int](($bottoms|Where-Object {$_ -ge 30}).Count -gt 0); reaches_50_cm=[int](($bottoms|Where-Object {$_ -ge 50}).Count -gt 0); reaches_100_cm=[int](($bottoms|Where-Object {$_ -ge 100}).Count -gt 0); reaches_150_cm=[int](($bottoms|Where-Object {$_ -ge 150}).Count -gt 0)
            has_matrix_color=0; has_munsell_hue=0; has_munsell_value=0; has_munsell_chroma=0; has_redox_features=0; has_redox_concentrations=0; has_redox_depletions=0; has_gley_information=0; has_drainage_class=0; has_flooding_information=0; has_ponding_information=0; has_water_table_information=0
        }
    }
    Export 'horizon_level_inventory' $horizons
    Export 'pedon_level_coverage' $summary
    Export 'measurement_definitions_by_group' $methodRows
    Export 'taxonomy_coverage' $tax

    $coverageCols=@('has_coordinates','has_taxonomy','has_horizon_depths','has_complete_depths','has_horizon_designations','has_texture_description','has_wetness_horizon_designation','has_samples','has_MIR','has_organic_carbon','has_total_carbon','has_Fe','has_Mn','has_clay','has_sand','has_silt','has_pH','has_CEC','has_water_retention','has_matrix_color','has_munsell_hue','has_munsell_value','has_munsell_chroma','has_redox_features','has_redox_concentrations','has_redox_depletions','has_gley_information','has_drainage_class','has_flooding_information','has_ponding_information','has_water_table_information','structurally_reconstructable_profile')
    $coverage = foreach($c in $coverageCols){$n=@($summary|Where-Object {[int]$_.$c -eq 1}).Count; [pscustomobject]@{field=$c; pedon_count=$n; percent=[math]::Round(100*$n/$summary.Count,2)}}
    Export 'pedon_coverage_statistics' $coverage

    $examples=@($summary|Where-Object {$_.structurally_reconstructable_profile -eq 1}|Sort-Object @{Expression='has_MIR';Descending=$true},@{Expression='horizon_count';Descending=$true}|Select-Object -First 5)
    $exampleIds=@($examples|ForEach-Object {[string]$_.lims_pedon_id})
    Export 'representative_profile_horizons' @($horizons|Where-Object {$exampleIds -contains [string]$_.lims_pedon_id})

    $neon=@($summary|Where-Object { $pid=[string]$_.lims_pedon_id; ($horizons|Where-Object {[string]$_.lims_pedon_id -eq $pid -and (($_.project_source,$_.lab_proj_name,$_.submit_proj_name)-join ' ') -match '(?i)NEON'}|Select-Object -First 1) })
    Export 'neon_pedon_coverage' $neon
}
finally { $cn.Close() }

Write-Output "Reconnaissance outputs written to $out"
