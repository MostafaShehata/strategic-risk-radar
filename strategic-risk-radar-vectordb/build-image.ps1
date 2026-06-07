param(
    [string]$ImageName = "strategic-risk-radar-vectordb:local"
)

Push-Location $PSScriptRoot
try {
    docker build -t $ImageName .
}
finally {
    Pop-Location
}
