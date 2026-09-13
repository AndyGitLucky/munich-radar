# München Radar

Eine kleine tägliche Auswahl aus Münchens offiziellen Veranstaltungskalendern. Python sammelt und bewertet die Termine; HTML, CSS und JavaScript zeigen höchstens fünf Empfehlungen pro Ansicht. Ohne Konten, API-Schlüssel, Frontend-Framework oder laufenden Produktionsserver.

**Website:** [München Radar öffnen](https://andygitlucky.github.io/munich-radar/) · [GitHub-Repository](https://github.com/AndyGitLucky/munich-radar)

MVP mit vier echten Quellen und Veröffentlichung über GitHub Pages. Die mitgelieferten JSON-Daten sind echte Abrufe, keine Beispieldaten. Auf dem iPhone die Website in Safari öffnen; über **Teilen → Zum Home-Bildschirm** lässt sie sich als direkter Einstieg ablegen. Der eigene PC muss für die veröffentlichte Seite nicht laufen.

## Hier lokal starten

Die Python-3.12-Umgebung ist in diesem Arbeitsordner bereits unter `.venv` eingerichtet.

```powershell
# Vorhandene Daten ansehen, ohne Netzabruf:
.\.venv\Scripts\python.exe -m src.serve

# Browser öffnen: http://127.0.0.1:8000
# Beenden: Strg+C
```

Zum Aktualisieren den Vorschauprozess beenden und aus dem Projektverzeichnis ausführen:

```powershell
.\.venv\Scripts\python.exe -m src.main
.\.venv\Scripts\python.exe -m src.serve
```

Alternativ: `./Start-Radar.ps1` beziehungsweise `./Start-Radar.ps1 -Update`. Mit `-Port 8001` kann eine andere lokale Portnummer gewählt werden. Für die normalen Python-Befehle ist keine Änderung der PowerShell-Ausführungsrichtlinie nötig.

`src.serve` baut zuerst `dist/` und liefert ausschließlich diesen öffentlichen Ordner aus, gebunden an `127.0.0.1`. Nach einer Aktualisierung bei weiterlaufender Vorschau `python -m src.build` ausführen und die Browserseite neu laden. Die HTML-Datei nicht per Doppelklick öffnen: Browser blockieren dabei gewöhnlich die JSON-Abrufe.

## Auf einem anderen Rechner einrichten

Python 3.12 oder neuer vorausgesetzt:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m src.main
python -m src.serve
```

Für den reinen Betrieb genügt `requirements.txt`. Die Entwicklungsdatei ergänzt pytest und Playwright. Ein Node.js-Projekt wird nicht benötigt. Die auf diesem Rechner verwendeten zusätzlichen Ordner `.python/` und `.cache/` gehören zur lokalen Einrichtung und werden nicht versioniert.

## Was enthalten ist

- Heute, Morgen, aktuelles/kommendes Wochenende, nächste 30 Tage und in den letzten 72 Stunden neu entdeckte Termine.
- Filter für nachweislich kostenlose und ausdrücklich familiengeeignete Angebote.
- Konfigurierbare, erklärbare Bewertung mit Gründen auf jeder Karte.
- Höchstens fünf Tipps, maximal drei pro Quelle und eine Empfehlung pro Veranstaltungsreihe.
- Vorschau an den Schwellen 14/7/3/1 Tage für Highlights und 3/1 Tage für andere Termine. Wiederkehrende Reihen werden dort ausgelassen.
- Deutsche responsive Oberfläche, Tastaturbedienung, Quellenlinks, Aktualisierungsstand und verständliche Leer-/Fehlerzustände.

Die Browseransichten rechnen immer in `Europe/Berlin`, unabhängig vom Standort des Geräts. Sie aktualisieren die Zeitzuordnung bei einem Tageswechsel. Die Bewertung selbst stammt vom letzten Pipeline-Lauf; ab 24 Stunden wird der Datenstand als veraltet angezeigt.

## Quellen und bewusst begrenzte Abdeckung

| Quelle | Verarbeitung | Grenze |
| --- | --- | --- |
| [Corso Leopold](https://www.corso-leopold.de/) | Aktueller Programmlink von der Startseite; datierte Öffnungszeiten des gesamten Straßenfests | Zwei Seiten pro Lauf. Getrennte Festivaltage mit tatsächlichen Öffnungszeiten; keine Übernahme aller Bühnenauftritte. Der Eintritt bleibt unbekannt, wenn auf der Programmseite keine Angabe steht. |
| [Gasteig](https://www.gasteig.de/veranstaltungen/) | Datierte Teaser der Startübersicht, auch Festivals; `Event`-JSON-LD auf Detailseiten | Maximal 14 passende Detailseiten pro Lauf. Kein vollständiger Veranstaltungskatalog. |
| [Deutsches Museum](https://www.deutsches-museum.de/museumsinsel/programm/kalender) | Öffentliches Kalenderfragment `/search.html` und dessen Weiterblättern-Links | Sechs Seiten mit derzeit zehn Terminen pro Seite. Wegen vieler Tagesangebote deckt dies vor allem die nächsten Tage ab. |
| [Lenbachhaus](https://www.lenbachhaus.de/besuchen/kalender) | Explizit datierte HTML-Terminkarten, laufender und nächster Monat | Undatierte Dauerangebote werden ausgelassen. Preise/Zielgruppen fehlen oft in der Übersicht und bleiben dann unbekannt. |

Die Anbindung wurde am 13.09.2026 live geprüft. Der öffentliche Datumsfilter des Museumskalenders lieferte beim Test eine Serverfehlerseite; deshalb verwendet der Collector ausschließlich die tatsächlich ausgegebenen Pagination-Links. Lenbachhaus hat auf Detailseiten zwar JSON-LD, dort kann jedoch die Formatbezeichnung anstelle des eigentlichen Titels stehen und die Uhrzeit fehlen. Die Kalenderkarten enthalten die präziseren Angaben.

Die Quellen sind zunächst stark auf Museen und Kultur ausgerichtet. Corso Leopold ist als eigene offizielle Festivalquelle integriert; weitere Straßenfeste, Märkte und stadtweite Hinweise sind noch nicht umfassend abgedeckt. Die Ansicht „Demnächst“ filtert auf 30 Tage; sie verspricht keine vollständige Abdeckung dieses Zeitraums durch jede Quelle.

Das HTTP-Modul prüft `robots.txt`, setzt `MunichRadar/0.1`, verwendet 20 Sekunden Timeout und mindestens eine Sekunde Abstand je Host. Zusätzliche Crawl-Verzögerungen werden berücksichtigt. Es folgt nur Links innerhalb konfigurierter Ursprünge. Keine Login-Sitzungen, Umgehung von Sperren oder aggressiven Wiederholungen.

## Konfiguration

`config/sources.yaml` steuert aktivierte Quellen, HTTP-Regeln, Quellenpriorität und Abrufgrenzen. Eine kleinere Prioritätszahl bevorzugt bei Dubletten den entsprechenden Veranstalter. Neue Quellen bekommen einen eigenen Collector und einen Eintrag in `src/collectors/__init__.py`.

`config/relevance.yaml` enthält Interessen, Punktgewichte, Mindestbewertung, Auswahlgrenzen, Zeitraum und Vormerkschwellen. Die anfänglichen Interessen übernehmen den Schwerpunkt aus `PROJECT.md`: Wissenschaft, Technik, Museen, Familie und Kultur. Sie lassen sich ohne Codeänderung anpassen. Nach Änderungen Pipeline und Build erneut ausführen.

Die Regeln unterscheiden **neu entdeckt** von **neu eröffnet**. Mehrere beobachtete Tage derselben Reihe markieren diese als wiederkehrend; ein mehrwöchiger Ausstellungszeitraum allein zählt nicht als Wiederholung. Einzelne Öffnungstage desselben Festivals tragen das Tag `festival_day` und erhalten keinen Wiederholungsabzug. Angaben zu Preisen, Öffnungszeiten oder Familienfreundlichkeit werden nicht ergänzt, wenn die Quelle sie nicht belegt.

## Daten und Schema

Das vorgeschlagene Modell aus `PROJECT.md` ist implementiert. Dokumentierte Ergänzungen in Schema-Version 1:

| Feld | Bedeutung |
| --- | --- |
| `sources` | Alle zusammengeführten Quellen mit Name, URL und Priorität. |
| `all_day` | Quelle liefert nur ein Datum oder einen ganztägigen Zeitraum; die UI erfindet keine Uhrzeit. |
| `source_priority` | Priorität für die Auswahl der primären Quelle. |
| `series_id` | Quellenspezifischer Schlüssel, um wiederholte Vorstellungen in der Auswahl zu begrenzen. |
| `status` | `scheduled`, `cancelled` oder `postponed`; nur bestätigte geplante Termine gelangen in den öffentlichen Datensatz. |
| `stale` | Termin stammt aus einem älteren erfolgreichen Abruf einer inzwischen ausgefallenen Quelle. |

Zeitstempel sind ISO 8601 mit Berliner UTC-Offset. Ein reines Enddatum gilt einschließlich dieses Tages; ein ausdrücklich auf Mitternacht datiertes Ende gilt exklusiv. Termine über Mitternacht werden korrekt dem Folgetag zugeordnet.

Die ID ist ein deterministischer Hash aus bereinigtem Titel, **vollständigem Beginn**, Ort und Quelle. Der vollständige Beginn verhindert Kollisionen zwischen zwei Vorstellungen am selben Tag. Korrigiert eine Quelle Titel, Ort oder Beginn, kann sich die ID ändern; das ist eine bewusste Grenze des MVP.

- `data/events.json`: normalisierte, gefilterte, zusammengeführte und bewertete Termine.
- `data/metadata.json`: Stand, Quellenzustände, Zählwerte, Auswahlregeln, vorberechnete Ansichten und Vorschau.
- `data/source-state.json`: letzte normalisierte Einzelquellenstände; erhält `discovered_at` über Updates hinweg und ermöglicht Rückfall bei Ausfällen. Wird versioniert, aber nicht veröffentlicht.
- `data/raw/`: letzter Rohdatensatz je Quelle, lokal und von Git ausgeschlossen.
- `data/last-failure.json`: Diagnose eines vollständig fehlgeschlagenen Laufs, nicht Teil der Website.
- `dist/`: veröffentlichbarer Build; nur Frontend, `events.json` und `metadata.json`.

`discovered_at` bleibt bei unveränderter ID erhalten; `updated_at` bedeutet zuletzt von der Quelle erfolgreich bestätigt. Bei Teilausfällen bleiben noch relevante, höchstens sieben Tage alte Termine der betroffenen Quelle erhalten und werden markiert. Ein fehlerhafter Eintrag stoppt die anderen nicht. Wenn alle Quellen ausfallen, endet der Prozess mit Fehlercode und lässt den letzten öffentlichen Datenstand unangetastet. Eine unerwartet leere Quelle gilt vorsichtshalber als Fehler.

## Prüfen

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m src.build

# Vorhandenes Chrome für lokale Browserprüfungen:
$env:RADAR_BROWSER_PATH = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe scripts/browser_smoke.py
```

Ohne vorhandenes Chrome: `python -m playwright install chromium`, anschließend den Browsercheck ohne `RADAR_BROWSER_PATH` ausführen. Linux-CI verwendet `python -m playwright install --with-deps chromium`.

Unit-Tests prüfen Normalisierung, Validierung, stabile IDs, Sommer-/Winterzeit, Dubletten, Bewertung, Wiederholungen, Zeitansichten, echte gekürzte Parserfixtures sowie Teil- und Totalausfälle. Sie führen keine Netzabrufe aus. Der Browsercheck prüft alle Ansichten, Filter, eine abweichende Gerätezeitzone, 1440/390/320 Pixel Breite, schädlich formatierten Quellentext und Laden nach einem Fehler. Screenshots landen unter `.scratch/`.

## GitHub Pages betreiben

Das Projekt verwendet `AndyGitLucky/munich-radar`. Zur Einrichtung in einem weiteren Repository:

1. Projekt einschließlich `data/events.json`, `data/metadata.json` und `data/source-state.json` auf den Standardbranch übertragen. Lokale Umgebungen und `dist/` ausschließen; `.gitignore` ist vorbereitet.
2. In **Settings → Pages → Build and deployment** die Quelle **GitHub Actions** auswählen.
3. Dem Update-Workflow Schreibzugriff auf Repository-Inhalte erlauben; eventuelle Branch-Regeln müssen die Datencommits des Actions-Bots zulassen.
4. Unter **Actions → Update Munich Radar → Run workflow** den ersten Lauf starten.

Der vorbereitete Workflow testet, sammelt, baut, speichert Daten/Entdeckungshistorie per Commit und veröffentlicht das Pages-Artefakt. Er läuft viermal täglich um 04/09/14/19 Uhr UTC: in Berlin im Sommer 06/11/16/21 Uhr, im Winter eine Stunde früher. GitHub-Zeitpläne können sich verzögern; sie sind kein minutengenauer Dienst. Einrichtung und Berechtigungen richten sich nach der [GitHub-Pages-Dokumentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages), Zeitpläne nach der [Actions-Dokumentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

Der separate Test-Workflow führt Offline-Tests, Build und Browsercheck bei Codeänderungen aus. Alle Frontend-Pfade sind relativ und funktionieren damit auch unter `https://NAME.github.io/REPOSITORY/`. Den Status der Aktualisierungen und Veröffentlichungen zeigt der Actions-Bereich des Repositorys. Codeänderungen mit **Update Munich Radar → Run workflow** veröffentlichen; reine Datenupdates erfolgen zusätzlich nach Zeitplan.
