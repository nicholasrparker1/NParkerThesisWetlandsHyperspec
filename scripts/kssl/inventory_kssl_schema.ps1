param(
    [string]$DatabasePath = "data/raw/KSSL/MIR Spectra_Access_Portable.accdb",
    [string]$OutputDirectory = "outputs/tables/kssl_reconnaissance/schema"
)

$ErrorActionPreference = "Stop"
$db = (Resolve-Path -LiteralPath $DatabasePath).Path
$out = Join-Path (Get-Location) $OutputDirectory
New-Item -ItemType Directory -Path $out -Force | Out-Null

$connection = New-Object System.Data.OleDb.OleDbConnection(
    "Provider=Microsoft.ACE.OLEDB.12.0;Data Source=$db;Mode=Read;"
)
$connection.Open()

function Export-SchemaTable {
    param([string]$CollectionName, [string]$FileName)
    try {
        $data = $connection.GetSchema($CollectionName)
        $data | Export-Csv -LiteralPath (Join-Path $out $FileName) -NoTypeInformation -Encoding utf8
        Write-Output "$CollectionName`: $($data.Rows.Count) rows"
    }
    catch {
        Write-Warning "Could not read schema collection $CollectionName`: $($_.Exception.Message)"
    }
}

try {
    $tables = $connection.GetSchema("Tables") |
        Where-Object { $_.TABLE_TYPE -eq "TABLE" -and $_.TABLE_NAME -notlike "MSys*" } |
        Sort-Object TABLE_NAME
    $tables | Export-Csv -LiteralPath (Join-Path $out "tables.csv") -NoTypeInformation -Encoding utf8

    $columns = $connection.GetSchema("Columns") |
        Where-Object { $_.TABLE_NAME -notlike "MSys*" } |
        Sort-Object TABLE_NAME, ORDINAL_POSITION
    $columns | Export-Csv -LiteralPath (Join-Path $out "columns.csv") -NoTypeInformation -Encoding utf8

    $counts = foreach ($table in $tables) {
        $name = [string]$table.TABLE_NAME
        $escaped = $name.Replace("]", "]]" )
        $command = $connection.CreateCommand()
        $command.CommandText = "SELECT COUNT(*) FROM [$escaped]"
        try {
            [pscustomobject]@{ table_name = $name; row_count = [long]$command.ExecuteScalar(); error = "" }
        }
        catch {
            [pscustomobject]@{ table_name = $name; row_count = $null; error = $_.Exception.Message }
        }
    }
    $counts | Export-Csv -LiteralPath (Join-Path $out "table_counts.csv") -NoTypeInformation -Encoding utf8

    Export-SchemaTable "Indexes" "indexes.csv"
    Export-SchemaTable "ForeignKeys" "foreign_keys.csv"
    Export-SchemaTable "DataTypes" "data_types.csv"
}
finally {
    $connection.Close()
}

Write-Output "Schema inventory written to $out"
