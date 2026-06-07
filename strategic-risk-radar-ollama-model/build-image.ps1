param(
    [string]$ImageName = "strategic-risk-radar-ollama-model:local"
)

Push-Location $PSScriptRoot
try {
    docker build -t $ImageName .
}
finally {
    Pop-Location
}
