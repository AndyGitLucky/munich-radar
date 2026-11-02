# München: illustrierte Kartenpipeline

Verbindliche Basis ist die erste vollständige 75-Kachel-Karte aus diesem Chat.
Die Originalbilder, ihre vollständigen Prompts und tatsächlich verwendeten
Bildreferenzen liegen unverändert unter `baseline/`. Die Originalpalette und
Detaildichte sind die visuelle Vorgabe.

Der Ablauf ist an einer lokalen Änderung von `r03c05` geprüft: Der kopierte
Kreisplatz wurde durch ein eigenes dicht bebautes Viertel ersetzt. Palette und
Miniaturdetail bleiben nah am Original. Bildgenerierung erfolgt mit dem eingebauten
Imagegen-Werkzeug; die Skripte übernehmen Vorbereitung, Versionierung, Prüfung,
Zusammensetzen und Auslieferung. Sie rufen keine externe Bild-API auf.

Die geografischen Quellen stehen in `sources.json`. Die Geometrie verwendet
EPSG:3857, das feste Raster und die Landmarkenzuordnung aus `plan.json`.
Originale: 1254 × 1254 Pixel, Überlappung 358 Pixel; Gesamtbild 12311 × 9234 Pixel.
Die Bebauung ist illustriert, Straßen und gezeichnete Landmarkenbasen sind
vereinfacht. © OpenStreetMap-Mitwirkende, ODbL.

## Einrichten und starten

Aus dem Projektverzeichnis, mit Python 3.12 und der vorhandenen `.venv`:

```powershell
uv pip install --python .venv/Scripts/python.exe --cache-dir .cache/map-pipeline -r requirements-map.txt
.\.venv\Scripts\python.exe -m src.map_pipeline inspect
.\.venv\Scripts\python.exe -m src.map_pipeline build --baseline --publish
.\Start-Atlas.ps1
```

Die Karte läuft lokal unter <http://127.0.0.1:8015/>. Unter **Info → Kartenansicht**
stehen aktuelle Karte und unveränderte Originalkarte zur Verfügung. Bei belegtem
Port: `Start-Atlas.ps1 -Port 8016`. Playwright verwendet vorhandenes Chromium oder
das installierte Chrome. Falls beides fehlt: `python -m playwright install chromium`.
Für die vollständige Testsuite zusätzlich die Entwicklungsabhängigkeiten aus
`requirements-dev.txt` installieren; diese schließen die Kartenabhängigkeiten ein.

## Eine Kachel austauschen

```powershell
# Eine neue, bisher unbenutzte Versionskennung wählen:
.\.venv\Scripts\python.exe -m src.map_pipeline prepare r03c05 block-02 --task "Den kopierten Kreisplatz durch ein eigenes dichtes Viertel ersetzen; Palette und Detailmaßstab beibehalten." --rect 0 0 820 850
```

Der Befehl legt unter `candidates/r03c05/block-02/` den vollständigen Prompt und
die tatsächlich zu verwendenden Referenzpfade an. Mit Imagegen die vorhandene
Kachel anhand dieser Vorgaben bearbeiten. Das native PNG anschließend aufnehmen:

```powershell
.\.venv\Scripts\python.exe -m src.map_pipeline import r03c05 block-02 --image 'C:/Pfad/zur/Imagegen-Ausgabe.png'
.\.venv\Scripts\python.exe -m src.map_pipeline preview r03c05 block-02
```

`preview` erstellt eine vollständige, geprüfte Vergleichsversion, ohne die aktive
Karte zu verändern. Den ausgegebenen Vergleichspfad unter `/atlas/candidates/…/`
öffnen. Er zeigt Original, rohe Ausgabe, begrenzten Kandidaten, geografische
Vorlage und die Einfügung in die Gesamtkarte. Die interaktive Vorschau verwendet
dieselbe Projektion und Event-App wie die aktive Karte.

Erst nach visueller Prüfung von Farben, Maßstab, Inhalt und Übergängen übernehmen:

```powershell
.\.venv\Scripts\python.exe -m src.map_pipeline review r03c05 block-02 --decision accept --note "Palette, Detail und Nachbarübergänge visuell geprüft."
.\.venv\Scripts\python.exe -m src.map_pipeline activate r03c05 block-02
```

Die Browserseite danach neu laden. Eine abgelehnte Ausgabe mit `--decision reject`
kennzeichnen. Messwertwarnungen blockieren die Freigabe, bis sie untersucht wurden;
eine begründete Ausnahme benötigt ausdrücklich `--allow-warnings`. Eigene Wahrzeichen
liegen standardmäßig außerhalb der Bearbeitung; beabsichtigte Änderungen daran
bereits bei `prepare` mit `--allow-landmarks` kennzeichnen.

## Rücksetzen und prüfen

```powershell
# Genau eine Kachel auf das Original zurücksetzen:
.\.venv\Scripts\python.exe -m src.map_pipeline rollback --tile r03c05
# Eine vorhandene vollständige Version wieder aktivieren:
.\.venv\Scripts\python.exe -m src.map_pipeline rollback --release RELEASE_ID
# Aktuelle Auswahl erneut bauen und geprüfte Ausgabe aktivieren:
.\.venv\Scripts\python.exe -m src.map_pipeline build --publish
# Komplette Pixelprüfung eines Builds wiederholen:
.\.venv\Scripts\python.exe -m src.map_pipeline verify RELEASE_ID
# Unabhängigen zweiten Aufbau der Originalkarte erzeugen:
.\.venv\Scripts\python.exe -m src.map_pipeline build --baseline --fresh
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/check_atlas.py --browser chromium --variant painted
```

`activate` und `rollback` bauen eine neue Version beziehungsweise verwenden einen
bereits geprüften Build. Erst nach erfolgreicher Prüfung wird `current.json`
atomar umgeschaltet. Offene Browseransichten behalten bis zum Neuladen ihren
vollständigen bisherigen Bildstand. Eine Dateisperre verhindert konkurrierende
Schreibvorgänge und verlorene Versionsänderungen.

## Was fest bleibt

- Originaldateien und vollständige Referenzen werden per SHA-256 geprüft.
- Die erste Originalmontage legt die Überlappungsschnitte in `baseline/joins.json`
  fest. Spätere Kachelwechsel berechnen keine neuen Schnittlinien für die Nachbarn.
- Außerhalb der ausdrücklich gewählten Bearbeitungsfläche bleibt jeder Pixel der
  Zielkachel unverändert. Ein 16-Pixel-Übergang liegt innerhalb dieser Fläche.
  Neue Bildpixel werden weder vergrößert noch global umgefärbt.
- Alle nativen Auslieferungskacheln, geschützten Landmarken, Quellkerne und die
  vollständige Stadtfläche werden unabhängig vom Canvas-Renderer geprüft.
- Sättigung, Helligkeit und Detailkontrast werden immer gegen das unveränderte
  Original geprüft, auch nach mehreren Bearbeitungen. Sie sind Diagnosewerte und ersetzen keine
  visuelle Freigabe und beweisen keine geografische Richtigkeit.

## Ablage und nachgewiesenes Beispiel

- `baseline/`: 75 unveränderte Originalbilder, Prompts und Referenzen.
- `candidates/TILE/VERSION/`: Anforderung, Imagegen-Original, begrenzter Kandidat,
  Messwerte, Freigabe und Vergleichsseite.
- `states/`, `history/`, `current.json`: gespeicherte Quellauswahl und Versionswechsel.
- `releases/`: erzeugte Masterbilder, Zoomkacheln, Prüfungen und Laufzeiten.
  Diese großen abgeleiteten Dateien sind von Git ausgeschlossen.
- `reports/`: Beispielprüfung und Browserbilder.
- `src/map_pipeline/`: zentrale CLI, Versionslogik, Renderer, Prüfung und Server.

Die damalige vollständige PNG-Sicherung war nicht mehr vorhanden. Alle 75
ursprünglichen Kachelbilder waren anhand gespeicherter Prüfsummen wiederherstellbar.
Aus ihnen wurde der Referenzmaster neu aufgebaut. Zwei unabhängige Aufbauten
lieferten identische PNG-Bytes und null Kanalabweichung über 454719096 Kanäle.

Das Beispiel liegt unter `candidates/r03c05/shape-01/`:
[Vergleich öffnen](http://127.0.0.1:8015/atlas/candidates/r03c05/shape-01/),
[Bild](candidates/r03c05/shape-01/image.png), [vollständiger Prompt](candidates/r03c05/shape-01/prompt.md).
Im bearbeiteten Bereich: Sättigung +1,98 Prozentpunkte, Helligkeit −2,42 Punkte,
Detailkontrast 96,6 % des Originals. Im Gesamtbild ändern sich 696530 Pixel;
außerhalb der gewünschten Fläche beträgt die Abweichung null. Beobachtungen,
Originalausgabe und verwendeter Prompt sind dort vollständig erhalten.

Die Originalkarte enthält weiterhin illustrative Ungenauigkeiten und weitere
wiederholte Motive. Dieses Beispiel prüft den kontrollierten Kachelaustausch;
es ist keine automatische Freigabe aller 75 Bilder. Generative Ausgaben sind
nicht deterministisch; gespeicherte Bilder und ihre Montage sind reproduzierbar.

## Tatsächliche Prüfung am 2026-11-02

- `python -m pytest -q`: 127 Tests bestanden, einschließlich bisheriger Event-Tests.
- `scripts/check_atlas.py --browser webkit --variant baseline`: bestanden.
- `scripts/check_atlas.py --browser chromium --variant painted`: bestanden;
  inklusive Touch-Zoom, Empfehlungen, Marker, Merkliste, ICS/GPX und Leerzuständen.
- `scripts/check_atlas_versions.py`: native Nachbarvorschau, unveränderte
  Markerprojektion/Empfehlungen und vollständiger Vergleich bestanden.
- `scripts/check_atlas_lifecycle.py --leave-example`: einzelne Kachel aktivieren,
  auf Original zurücksetzen und vollständige Versionen wieder aktivieren bestanden.
  Ohne `--leave-example` stellt dieses Skript abschließend den Ausgangsstand wieder her.
- 75 Quellkerne und 48 geschützte Landmarken geprüft; null ungezeichnete Pixel
  innerhalb der Stadtgrenze; native Zoomkacheln mit null Kanalabweichung.
- 112 bestehende App-, Konfigurations-, Daten- und Testdateien nach der Bereinigung
  per Prüfsumme unverändert. Die aktuellen Dateien und Befehle sind unter
  [reports/validation.json](reports/validation.json) erfasst.

Tatsächliche Umgebung: Python 3.12.13, Pillow 13.0.0, NumPy 2.5.4, Playwright
1.62.0 und Chrome 156.0.8078.79. Die einzelnen Render-/Prüfzeiten stehen in den
Release-Metadaten und im Validierungsbericht. Die Veröffentlichung bleibt lokal.
