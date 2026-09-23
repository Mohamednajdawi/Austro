$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    & uv sync --locked
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
    & docker start acg-local-ollama
    if ($LASTEXITCODE -ne 0) { throw 'Create the acg-local-ollama container using README instructions first' }
    & uv run --locked python -m acg_agent_platform seed --env-file local-model.env.example
    if ($LASTEXITCODE -ne 0) { throw 'Sandbox initialization failed' }
    Write-Host 'Open http://127.0.0.1:8765. Issue tokens in a second terminal as described in README.'
    & uv run --locked python -m acg_agent_platform serve --env-file local-model.env.example
    if ($LASTEXITCODE -ne 0) { throw 'Application server failed' }
} finally {
    Pop-Location
}
