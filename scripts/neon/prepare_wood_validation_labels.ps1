param(
    [string]$InputCsv = "C:\Users\NI34189\OneDrive - MIT Lincoln Laboratory\Documents\MIT MS Stuff\Wetland InfoLiterature\WOOD_2025_balanced_bare_soil_validation.csv",
    [string]$OutputCsv = "data\raw\NEON\WOOD_2025\WOOD_2025_balanced_bare_soil_validation_label_template.csv"
)

$rows = Import-Csv -LiteralPath $InputCsv
$outputDirectory = Split-Path -Parent $OutputCsv
New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null

$prepared = foreach ($row in $rows) {
    $geometry = $row.'.geo' | ConvertFrom-Json
    [pscustomobject]@{
        point_id            = $row.'system:index'
        longitude           = [double]$geometry.coordinates[0]
        latitude            = [double]$geometry.coordinates[1]
        predicted_bare_soil = [int]$row.predicted_bare_soil
        ndvi                = [double]$row.NDVI
        mndwi               = [double]$row.MNDWI
        observed_class      = ''
        confidence          = ''
        notes               = ''
    }
}

$prepared | Export-Csv -LiteralPath $OutputCsv -NoTypeInformation
Write-Output "Prepared $($prepared.Count) validation records at $OutputCsv"
