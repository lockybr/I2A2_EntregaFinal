# Helper script to start the backend from the repository root
# Usage: Open PowerShell in the repo root and run: .\start_backend.ps1
Set-Location -Path (Join-Path $PSScriptRoot 'backend')
Write-Host "Starting backend from: " (Get-Location)
# Run uvicorn pointing to the package module under backend
# This ensures the ASGI app in backend/api/main.py is loaded ('api.main:app')
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
