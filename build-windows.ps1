param(
    [Parameter(Position = 0)]
    [string]$RomPath
)

$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    if ([string]::IsNullOrWhiteSpace($RomPath)) {
        & py -3 .\build.py
    }
    else {
        & py -3 .\build.py $RomPath
    }

    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}
