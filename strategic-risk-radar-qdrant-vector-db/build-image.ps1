param(
    [string]$ImageName = "strategic-risk-radar-qdrant-vector-db:local"
)

Push-Location $PSScriptRoot
try {
    docker build -t $ImageName .
}
finally {
    Pop-Location
}
