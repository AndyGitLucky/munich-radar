param([int]$Port = 8015)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& (Join-Path $PSScriptRoot '.venv/Scripts/python.exe') -X utf8 -m src.map_pipeline serve --port $Port
