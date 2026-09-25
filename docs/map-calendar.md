# Karte, Merkliste und Kalenderdateien

## Bedienung

- **Liste** zeigt weiterhin höchstens fünf bewertete Empfehlungen pro Zeitraum.
- **Karte · alle Treffer** zeigt alle erfassten Termine desselben Zeitraums und Filters, unabhängig von Relevanzschwelle, Quellenlimit und Fünferlimit. „Demnächst“ behält seine bestehende Bedeutung: in den nächsten 30 Tagen beginnende Termine; laufende Angebote stehen unter Heute und den passenden Tagesansichten.
- Ein Punkt steht für einen Veranstaltungsort, seine Zahl für die dortigen Termine. Nahe Orte werden beim Herauszoomen zusammengefasst. Antippen öffnet die zugehörigen Termine, Merken, Kalender-Download und Anfahrt.
- **Anfahrt** öffnet Google Maps mit dem Ziel und Verkehrsmittel ÖPNV. Startpunkt und Abfahrtszeit werden dort gewählt. München Radar fragt keinen Gerätestandort ab.
- **Merken** speichert einen Termin ausschließlich im Browser. **Merkliste** oben auf der Seite öffnet alle gespeicherten Termine, auch vergangene; dort gilt kein Fünferlimit. Die Merkliste lässt sich ebenfalls als Karte ansehen.
- Fehlende Kartenorte bleiben als aufklappbare Terminliste sichtbar. Eine Ortsangabe wie „verschiedene Orte“ wird nicht durch einen geratenen Punkt ersetzt.

## Persönliche Daten bleiben lokal

`localStorage`, Schlüssel `munich-radar.saved.v1`, enthält eine Kopie jedes gemerkten Termins. Kein Konto, keine E-Mail, kein zusätzlicher Server und kein Zugriff auf Apple-/Google-Kalender. Nutzer in verschiedenen Browserprofilen haben getrennte Listen; Personen im selben Browserprofil teilen dessen Merkliste. Andere Tabs desselben Profils übernehmen Änderungen.

Gesperrter oder voller Browserspeicher wird sichtbar gemeldet; die Auswahl funktioniert dann nur bis zum Ende der Sitzung. Nach Löschen der Browserdaten ist die Liste verloren. Es gibt keine Geräte-Synchronisierung oder Wiederherstellung. Bei beschädigtem Speicher überschreibt die App die vorhandenen Daten nicht stillschweigend.

Bleibt die Termin-ID im aktuellen Datensatz vorhanden, wird die gespeicherte Kopie beim Laden aufgefrischt. Fehlt sie, bleibt die Kopie mit einem Prüfhinweis erhalten. Das Fehlen eines Termins ist **kein Nachweis einer Absage**. Bei Quellenkorrekturen können sich IDs ändern; solche Fälle werden nicht automatisch als derselbe Termin behauptet.

## Kalender-Download ist kein Abo

**In Kalender übernehmen** erzeugt eine `.ics`-Datei. Diese wird mit der gewünschten Kalenderanwendung geöffnet/importiert. Die Dateibehandlung hängt vom Gerät und Browser ab; gegebenenfalls wird sie zunächst im Download-Ordner gespeichert. Google Kalender bietet den Dateiimport in seiner Desktop-Weboberfläche an.

Die Kopie enthält Titel, Ort, vorhandene Zeiten, Beschreibung und Quellenlink. Sie liest oder verändert keinen bestehenden Kalender automatisch. Änderungen, Absagen und das Entfernen aus der Radar-Merkliste werden nicht in bereits importierte Einträge übertragen. Wiederholte Importe können je nach Kalender-App Duplikate erzeugen. Es gibt kein persönliches Kalender-Abo in dieser Version.

Bei mehrtägigen Veranstaltungen kann ein einzelner Besuchstag gewählt werden. Dieser erscheint ganztägig mit Hinweis auf die separat zu prüfenden Öffnungszeiten. Alternativ lässt sich ausdrücklich der gesamte Zeitraum übernehmen. Übernacht-Termine bis 24 Stunden behalten ihre tatsächlichen Zeiten.

Technisch: RFC 5545, CRLF-Zeilenenden, UTF-8-Faltung auf höchstens 75 Bytes, maskierte Textfelder, deterministische UID, UTC für genaue Uhrzeiten und exklusive Enddaten für ganztägige Termine. Ohne bekanntes Ende wird keine Dauer erfunden. Kein automatischer Alarm; Termine werden als „frei“ (`TRANSP:TRANSPARENT`) importiert.

## Kartenorte und Kartendienst

`config/places.json` enthält 42 am 25.09.2026 geprüfte Veranstaltungsorte mit Koordinaten, Namensvarianten und Links zu den zugrunde liegenden OpenStreetMap-Objekten. Die Punkte bezeichnen Häuser bzw. Gelände, nicht automatisch Eingänge. Großflächige Orte sind als ungefähr markiert. Neue unbekannte Namen müssen im Ortskatalog geprüft und ergänzt werden.

Die einmalige Einrichtung verwendete die öffentliche Nominatim-Suche mit identifizierbarem User-Agent, einem Prozess, mindestens einer Sekunde Abstand und lokal gespeicherten Ergebnissen. Die Ergebnisse wurden geprüft: beispielsweise wurde HP8 vom gleichnamigen Fahrrad-Reparaturpunkt und die Bibliothek Riem von Waldtrudering unterschieden. Es gibt **keine periodischen Geocoding-Abfragen** und keine Suche aus den Browsern der Besucher. Regeln: https://operations.osmfoundation.org/policies/nominatim/

Leaflet und Markercluster werden mit festen Versionen und Lizenzdateien lokal ausgeliefert. Die eigentlichen Kartenbibliotheken und Kartenbilder laden erst beim Öffnen der Karte. Kartenbilder kommen von `https://tile.openstreetmap.org/{z}/{x}/{y}.png`, mit sichtbarer OSM-Nennung und normalem Browser-Caching/Referer. Keine Vorab-Downloads, Offline-Karten oder automatisierten Lasttests gegen OSM. Der Kartenanbieter sieht die üblichen Verbindungsdaten und den aufgerufenen Kartenausschnitt, nicht die gespeicherte Merkliste als Datensatz. Regeln: https://operations.osmfoundation.org/policies/tiles/

Der Gemeinschaftsdienst hat keine zugesicherte Verfügbarkeit. Bei wachsender Nutzung kann ein anderer geeigneter Kartenanbieter eingesetzt werden. Tests ersetzen alle Kartenbilder durch lokale Testantworten.

## Prüfung

`python scripts/browser_features.py` prüft getrennte Besucher, Speichern und Entfernen über Neuladen/Tabs hinweg, erhaltene alte Termine, Browser-Speicherfehler, tatsächliche ICS-Downloads, mehrtägige Besuchstage, Sommerzeitwechsel, sichere Textmaskierung, Kartenfilter, alle Treffer statt fünf, unbekannte Orte, Handybreiten und Wiederholung nach Kartenladefehlern. Ein Test mit 2.000 Terminen misst den Aufbau mit simulierten Kartenbildern; er ist kein Lasttest des Kartenanbieters.

Für WebKit: `RADAR_BROWSER=webkit` setzen und vorher `python -m playwright install webkit` ausführen. Ohne diese Variable wird Chromium verwendet. Auch WebKit-Tests ersetzen kein Importexperiment auf einem echten iPhone.
