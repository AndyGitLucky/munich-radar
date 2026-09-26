# München Radar

Eine kleine tägliche Auswahl aus Münchens offiziellen Veranstaltungskalendern. Python sammelt und bewertet die Termine; HTML, CSS und JavaScript zeigen höchstens fünf Empfehlungen pro Ansicht. Ohne Konten, API-Schlüssel, Frontend-Framework oder laufenden Produktionsserver.

**Website:** [München Radar öffnen](https://andygitlucky.github.io/munich-radar/) · [GitHub-Repository](https://github.com/AndyGitLucky/munich-radar)

MVP mit modular angebundenen Veranstalterquellen und Veröffentlichung über GitHub Pages. Die mitgelieferten JSON-Daten sind echte Abrufe, keine Beispieldaten. Auf dem iPhone die Website in Safari öffnen; über **Teilen → Zum Home-Bildschirm** lässt sie sich als direkter Einstieg ablegen. Der eigene PC muss für die veröffentlichte Seite nicht laufen.

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
- Themenbuttons für Musik, Food, Kunst, Shopping & Märkte, Bühne, Draußen und Wissen; Filterung vor der Empfehlungsauswahl, zusätzliche Ansicht aller Treffer.
- Konfigurierbare, erklärbare Bewertung mit Gründen auf jeder Karte.
- Höchstens fünf Tipps, maximal drei pro Quelle und eine Empfehlung pro Veranstaltungsreihe.
- Vorschau an den Schwellen 14/7/3/1 Tage für Highlights und 3/1 Tage für andere Termine. Wiederkehrende Reihen werden dort ausgelassen.
- Deutsche responsive Oberfläche, Tastaturbedienung, Quellenlinks, Aktualisierungsstand und verständliche Leer-/Fehlerzustände.
- Karte mit allen Treffern des gewählten Zeitraums und Filters, gebündelten Orten und Anfahrt über Google Maps. Unbekannte Kartenorte werden separat aufgeführt.
- Persönliche Merkliste ohne Konto, nur im jeweiligen Browser gespeichert. Auch aus dem aktuellen Radar verschwundene Termine bleiben darin erhalten.
- Einzelne Termine als `.ics`-Datei übernehmen; bei mehrtägigen Veranstaltungen wahlweise einen Besuchstag. Dies ist ein einmaliger Import, kein automatisch aktualisiertes Kalender-Abo.
- GPX-Wegpunkt mit geprüftem Kartenort und Veranstaltungsname herunterladen. Anfahrt verwendet Ortsnamen und Adressen statt Übersichtspunkten; bei ungenauen Geländen wird zunächst die Ortssuche geöffnet.

Die Merkliste erreichst du über den immer sichtbaren Knopf oben rechts. Sie wird nicht zwischen Geräten synchronisiert und geht beim Löschen der Browserdaten verloren. Details zu Bedienung, Kalenderimport und Kartenorten: [Karte und persönliche Termine](docs/map-calendar.md).

Die Browseransichten rechnen immer in `Europe/Berlin`, unabhängig vom Standort des Geräts. Sie aktualisieren die Zeitzuordnung bei einem Tageswechsel. Die Bewertung selbst stammt vom letzten Pipeline-Lauf; ab 24 Stunden wird der Datenstand als veraltet angezeigt.

## Quellen und bewusst begrenzte Abdeckung

| Quelle | Verarbeitung | Grenze |
| --- | --- | --- |
| [Märkte München](https://maerkte-muenchen.de/unsere-maerkte/wochenmaerkte.html) | Städtische Marktseiten mit ausdrücklich genannten Wochenzeiten | Bis zu 40 Detailseiten, nur gleicher Ursprung. Regelmäßige Termine für 30 Tage; Feiertage und Jahresend-Sondertage ausgelassen, keine geratenen Verlegungen. Externe Bauernmarktseiten nicht übernommen. |
| [Corso Leopold](https://www.corso-leopold.de/) | Aktueller Programmlink von der Startseite; datierte Öffnungszeiten des gesamten Straßenfests | Zwei Seiten pro Lauf. Getrennte Festivaltage mit tatsächlichen Öffnungszeiten; keine Übernahme aller Bühnenauftritte. Der Eintritt bleibt unbekannt, wenn auf der Programmseite keine Angabe steht. |
| [Gasteig](https://www.gasteig.de/veranstaltungen/) | Datierte Teaser der Startübersicht, auch Festivals; `Event`-JSON-LD auf Detailseiten | Maximal 14 passende Detailseiten pro Lauf. Kein vollständiger Veranstaltungskatalog. |
| [Deutsches Museum](https://www.deutsches-museum.de/museumsinsel/programm/kalender) | Öffentliches Kalenderfragment `/search.html` und dessen Weiterblättern-Links | Sechs Seiten mit derzeit zehn Terminen pro Seite. Wegen vieler Tagesangebote deckt dies vor allem die nächsten Tage ab. |
| [Lenbachhaus](https://www.lenbachhaus.de/besuchen/kalender) | Explizit datierte HTML-Terminkarten, laufender und nächster Monat | Undatierte Dauerangebote werden ausgelassen. Preise/Zielgruppen fehlen oft in der Übersicht und bleiben dann unbekannt. |
| [muenchen.de](https://www.muenchen.de/veranstaltungen/event/) | Festivalkalender, Familie/Kinder und Brauchtum; datierte Einzelvorstellungen | Je zwei Seiten pro Kategorie. Verwendet die tatsächlichen Vorstellungszeiten, nicht den äußeren Laufzeitraum einer Reihe. Veranstalterquellen haben bei Dubletten Vorrang. |
| [Münchner Stadtbibliothek](https://www.muenchner-stadtbibliothek.de/veranstaltungen) | HTML-Kalender mit verlinkten Folgeseiten | Vier Seiten; datierte Ausstellungen und Einzeltermine. Keine pauschale Annahme kostenlosen Eintritts. |
| [Münchner Stadtmuseum](https://www.muenchner-stadtmuseum.de/veranstaltungen/details) | Datierte Karten einschließlich Filmmuseum | Aktueller Kalendermonat. Ausgebuchte Angebote ausgelassen. Wegen wechselnder Veranstaltungsorte wird das Hauptgebäude nicht als Standardort eingesetzt. |
| [Haus der Kunst](https://www.hausderkunst.de/kalender) | Tagesabschnitte und echte Weiterblättern-Links | Vier Seiten. Bei fortgesetzten Tagesabschnitten stammt das Datum aus dem offiziellen Pagination-Link. |
| [Pinakotheken](https://www.pinakothek.de/de/programm/programm-uebersicht) | Öffentlicher Tageskalender `/_proxy_calendar` | Sieben Tage, nur konfigurierte Münchner Häuser. `entryFee: 0` bedeutet nicht zwingend kostenlosen Museumseintritt. |
| [Olympiapark](https://www.olympiapark.de/de/veranstaltungen) | Event-JSON-LD, ergänzt um zugehörige Detail-Links und Kartentexte | Offizielle Startübersicht; kein vollständiger Veranstaltungskatalog. |
| [Tollwood](https://www.tollwood.de/tollwood-winterfestival/) | Expliziter Winterfestival-Zeitraum einschließlich Ausgabejahr | Gesamtfestival; keine einzelnen Shows und kein pauschaler Gratis-Status. Außerhalb der nächsten 30 Tage erscheint es noch nicht in der Auswahl. |
| [Messe München](https://messe-muenchen.de/de/veranstaltungen/) | Vom öffentlichen Kalender eingebundene Suche, nach Zeitraum gefiltert | Maximal zwei Seiten à 100 Ergebnisse, nur Münchner Standorte. Internationale Messen ausgeschlossen; Fachmessen als kommerziell markiert. |
| [Munichs Robotics Meetup](https://www.meetup.com/de-DE/munichs-robotics-meetup/) | Öffentliche kommende Termine dieser ausgewählten Gruppe | Kein Login und keine Mitgliederdaten. Nur Präsenz-/Hybridtermine mit Münchner Ort. Eine ausdrücklich leere Terminliste ist ein erfolgreicher Abruf. |

Die Anbindung wurde am 13.09.2026 live geprüft. Der öffentliche Datumsfilter des Museumskalenders lieferte beim Test eine Serverfehlerseite; deshalb verwendet der Collector ausschließlich die tatsächlich ausgegebenen Pagination-Links. Lenbachhaus hat auf Detailseiten zwar JSON-LD, dort kann jedoch die Formatbezeichnung anstelle des eigentlichen Titels stehen und die Uhrzeit fehlen. Die Kalenderkarten enthalten die präziseren Angaben.

Die Erweiterung ergänzt stadtweite Festivals, Familienangebote, Brauchtum, weitere Museen und Messen. Die Ansicht „Demnächst“ filtert auf 30 Tage; sie verspricht keine vollständige Abdeckung dieses Zeitraums durch jede Quelle. MVV/MVG-Hinweise und gesonderte Stadtteil-/Bezirksausschusskalender sind noch nicht integriert: Die geprüften Verkehrsseiten liefern keinen passenden datierten Veranstaltungskalender; der geprüfte städtische Beteiligungskalender sperrt automatische Abrufe. Details und Grenzen stehen im [Quellenprüfbericht](docs/sources.md).

Das HTTP-Modul prüft `robots.txt`, setzt `MunichRadar/0.1`, verwendet 20 Sekunden Timeout und mindestens eine Sekunde Abstand je Host. Zusätzliche Crawl-Verzögerungen werden berücksichtigt. Es folgt nur Links innerhalb konfigurierter Ursprünge. Die öffentliche Messesuche verwendet zusätzlich einen ausdrücklich konfigurierten API-Ursprung; ihr im öffentlichen Kalender gelieferter Suchschlüssel wird nur für den Abruf verwendet und nicht gespeichert. Suchanfragen per POST unterliegen denselben Robots- und Herkunftsprüfungen; Weiterleitungen werden dabei abgelehnt. Keine Login-Sitzungen, Umgehung von Sperren oder aggressiven Wiederholungen.

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
- `config/places.json`: geprüfter Ortskatalog mit OpenStreetMap-Koordinaten und Namensvarianten; unbekannte Orte bleiben unzugeordnet.
- `dist/`: veröffentlichbarer Build; Frontend einschließlich lokal ausgelieferter Kartenbibliotheken, `events.json`, `metadata.json` und `places.json`.

`discovered_at` bleibt bei unveränderter ID erhalten; `updated_at` bedeutet zuletzt von der Quelle erfolgreich bestätigt. Bei Teilausfällen bleiben noch relevante, höchstens sieben Tage alte Termine der betroffenen Quelle erhalten und werden markiert. Ein fehlerhafter Eintrag stoppt die anderen nicht. Wenn alle Quellen ausfallen, endet der Prozess mit Fehlercode und lässt den letzten öffentlichen Datenstand unangetastet. Eine unerwartet leere Quelle gilt vorsichtshalber als Fehler. Nur ein ausdrücklich geprüftes leeres Suchergebnis bzw. ein gültiger leerer Kalender kann als erfolgreicher Abruf gelten; dann verschwinden zuvor gespeicherte Termine dieser Quelle. Eine Fehlerseite oder ausschließlich ungültige Einträge erfüllen diese Ausnahme nicht.

## Prüfen

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m src.build

# Vorhandenes Chrome für lokale Browserprüfungen:
$env:RADAR_BROWSER_PATH = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
.\.venv\Scripts\python.exe scripts/browser_smoke.py
.\.venv\Scripts\python.exe scripts/browser_features.py
```

Ohne vorhandenes Chrome: `python -m playwright install chromium`, anschließend den Browsercheck ohne `RADAR_BROWSER_PATH` ausführen. Linux-CI verwendet `python -m playwright install --with-deps chromium`.

Unit-Tests prüfen Normalisierung, Validierung, stabile IDs, Sommer-/Winterzeit, Dubletten, Bewertung, Wiederholungen, Zeitansichten, echte gekürzte Parserfixtures sowie Teil- und Totalausfälle. Sie führen keine Netzabrufe aus. Der Browsercheck prüft alle Ansichten, Filter, eine abweichende Gerätezeitzone, 1440/390/320 Pixel Breite, schädlich formatierten Quellentext und Laden nach einem Fehler. Screenshots landen unter `.scratch/`.

Der zusätzliche Featurecheck prüft Merkliste, getrennte Nutzer, tatsächliche Kalender-Downloads, Sommerzeit und mehrtägige Besuchstage, Kartenfilter, Kartenfehler und einen Datensatz mit 2.000 Terminen. Kartenbilder werden in Tests vollständig simuliert, um OpenStreetMap nicht durch automatisierte Kartenabrufe zu belasten. CI führt diesen Check mit Chromium und WebKit aus; ein Test auf dem tatsächlichen iPhone bleibt für den nativen Kalenderimport sinnvoll.

## GitHub Pages betreiben

Das Projekt verwendet `AndyGitLucky/munich-radar`. Zur Einrichtung in einem weiteren Repository:

1. Projekt einschließlich `data/events.json`, `data/metadata.json` und `data/source-state.json` auf den Standardbranch übertragen. Lokale Umgebungen und `dist/` ausschließen; `.gitignore` ist vorbereitet.
2. In **Settings → Pages → Build and deployment** die Quelle **GitHub Actions** auswählen.
3. Dem Update-Workflow Schreibzugriff auf Repository-Inhalte erlauben; eventuelle Branch-Regeln müssen die Datencommits des Actions-Bots zulassen.
4. Unter **Actions → Update Munich Radar → Run workflow** den ersten Lauf starten.

Der vorbereitete Workflow testet, sammelt, baut, speichert Daten/Entdeckungshistorie per Commit und veröffentlicht das Pages-Artefakt. Er läuft viermal täglich um 04/09/14/19 Uhr UTC: in Berlin im Sommer 06/11/16/21 Uhr, im Winter eine Stunde früher. GitHub-Zeitpläne können sich verzögern; sie sind kein minutengenauer Dienst. Einrichtung und Berechtigungen richten sich nach der [GitHub-Pages-Dokumentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages), Zeitpläne nach der [Actions-Dokumentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

Der separate Test-Workflow führt Offline-Tests, Build und Browsercheck bei Codeänderungen aus. Alle Frontend-Pfade sind relativ und funktionieren damit auch unter `https://NAME.github.io/REPOSITORY/`. Den Status der Aktualisierungen und Veröffentlichungen zeigt der Actions-Bereich des Repositorys. Codeänderungen mit **Update Munich Radar → Run workflow** veröffentlichen; reine Datenupdates erfolgen zusätzlich nach Zeitplan.
