param([switch]$Update, [int]$Port = 8000)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$radarPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $radarPython)) {
    throw 'Die lokale Python-Umgebung fehlt. Bitte die Einrichtung in README.md ausführen.'
}
if ($Update) {
    & $radarPython -m src.main
    if ($LASTEXITCODE -ne 0) { throw 'Die Aktualisierung ist fehlgeschlagen. Vorhandene Daten bleiben erhalten.' }
}
Write-Host "München Radar läuft gleich auf http://127.0.0.1:$Port – Beenden mit Strg+C."
& $radarPython -m src.serve --port $Port
