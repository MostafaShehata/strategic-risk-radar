param(
    [string]$ImageName = "strategic-risk-radar-news-enrichment:local"
)

Push-Location $PSScriptRoot
try {
    docker build -t $ImageName .
}
finally {
    Pop-Location
}
