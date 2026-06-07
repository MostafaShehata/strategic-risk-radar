param(
    [string]$ImageName = "strategic-risk-radar-rag-api:local"
)

Push-Location $PSScriptRoot
try {
    docker build -t $ImageName .
}
finally {
    Pop-Location
}
