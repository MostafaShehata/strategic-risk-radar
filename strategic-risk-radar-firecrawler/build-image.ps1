param(
    [string]$ImageName = "strategic-risk-radar-firecrawler:local"
)

Push-Location $PSScriptRoot
try {
    docker build -t $ImageName .
}
finally {
    Pop-Location
}
