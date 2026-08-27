param(
    [string]$InputCsv = "outputs/tables/kssl_spatial/kssl_mt_nd_spatial_evidence.csv",
    [string]$OutputDir = "outputs/tables/kssl_spatial"
)

$rows = Import-Csv -LiteralPath $InputCsv
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

function Export-Counts {
    param([string[]]$Fields, [string]$Name)
    $rows |
        Group-Object -Property $Fields |
        ForEach-Object {
            $values = $_.Name -split ', '
            $record = [ordered]@{}
            for ($i = 0; $i -lt $Fields.Count; $i++) { $record[$Fields[$i]] = $values[$i] }
            $record['count'] = $_.Count
            [pscustomobject]$record
        } |
        Export-Csv -LiteralPath (Join-Path $OutputDir $Name) -NoTypeInformation
}

Export-Counts @('state') 'state_counts.csv'
Export-Counts @('hydric_evidence_tier') 'kssl_evidence_counts.csv'
Export-Counts @('ssurgo_hydric_class') 'ssurgo_hydric_class_counts.csv'
Export-Counts @('nwi_intersect') 'nwi_intersection_counts.csv'
Export-Counts @('ssurgo_hydric_class', 'nwi_intersect') 'ssurgo_by_nwi_counts.csv'
Export-Counts @('hydric_evidence_tier', 'nwi_intersect') 'kssl_evidence_by_nwi_counts.csv'
Export-Counts @('hydric_evidence_tier', 'ssurgo_hydric_class') 'kssl_evidence_by_ssurgo_counts.csv'

Write-Output "Summarized $($rows.Count) records to $OutputDir"
