# Architekturvorschlag

Stand: 01.11.2026. Noch nicht implementiert. Postgres und Railway sind die gewuenschte Richtung; die konkrete Ausgestaltung ist ein Vorschlag.

## Komponenten und Verantwortung

| Komponente | Verantwortung |
| --- | --- |
| PWA im Browser | Touch-Oberflaeche fuer Tablet und Handy, Barcode-Erfassung, gespeicherte Liste |
| Flask-Webanwendung | Seiten/API, Anmeldung, Haushaltsgrenzen und Fachlogik |
| Postgres | Verbindlicher Haushaltsbestand, Einkaufsbedarf und Buchungen |
| Serverseitiger Auftrag (spaeter) | Woechentliche Vorschlaege unabhaengig von geoeffneten Geraeten |
| Shop-Adapter (spaeter) | Pro Shop explizit unterstuetzte Produkt- und Warenkorbfunktionen |
| MCP-Zugang (spaeter) | Authentifizierte Werkzeuge fuer dieselbe Fachlogik |
| Browserunterstuetzung (Pruefkandidat) | Angemeldete Shop-Sitzung fuer Aktionen ohne geeignete offizielle Schnittstelle |

Die Fachlogik liegt zentral im Service-Layer. Weboberflaeche, Hintergrundauftrag und MCP duerfen keine abweichenden Bestandsregeln implementieren.

## Technischer Startvorschlag

- Flask mit serverseitigen Templates und gezieltem JavaScript.
- Postgres mit ORM und versionierten Migrationen; konkrete Bibliotheksversionen bei Implementierung festlegen.
- Ein Repository und eine Webanwendung. Kein separates Frontend-Framework oder zusaetzlicher Dienst ohne konkreten Bedarf.
- PWA-Manifest und Service Worker; Offline-Verhalten ist ausdruecklicher Produktumfang.
- Railway fuer Webanwendung und Postgres. Scheduler/Worker erst bei tatsaechlichem Hintergrundbedarf.
- Produktbilder zunaechst optional; vor eigenen Uploads dauerhaften Dateispeicher und Loeschregeln festlegen.

## Gemeinsame Nutzung und Anmeldung

Ein Haushalt besitzt persoenliche Mitglieder und optional einen eingeschraenkten Geraetezugang. Das Schema erlaubt Haushaltszuordnung, auch wenn die Oberflaeche anfangs nur einen Haushalt bedient.

Login- und Einladungsverfahren muessen vor dem Auth-Paket konkret entschieden werden. Ein Shared-Tablet-Zugang ist kein allgemeiner administrativer Zugang. Er darf schnell Bedarf erfassen, aber keine Rechte oder Shop-Geheimnisse verwalten.

Jeder Zugriff prueft Haushaltszugehoerigkeit und Berechtigung serverseitig. Zustandsaendernde Browseraktionen benoetigen Schutz passend zum gewaehlten Auth-Verfahren, insbesondere gegen CSRF bei Cookie-Sitzungen. Zugang widerrufbar machen; sensible Werte nicht im Service-Worker-Cache speichern.

## Synchronisation und Offline

Zunaechst nach Schreibaktionen aktualisieren und beim Oeffnen/Fokussieren sowie periodisch neu laden. Die benoetigte Aktualitaet wird im Bedienungstest geprueft.

Die erste Offline-Stufe stellt die zuletzt gespeicherte Liste lesbar bereit. Schreibaktionen ohne Verbindung werden erkennbar blockiert.

Eine spaetere Schreib-Warteschlange braucht lokale Request-IDs, Idempotenz, Versionskonflikte, sichtbare Synchronisationszustaende und Wiederaufnahme nach App-Neustart. Offline-Schreiben ist kein Nebeneffekt eines Service Workers.

## Shop-Adapter

Faehigkeiten werden getrennt ausgewiesen: Suche, Produktdetails, Preis/Verfuegbarkeit, Warenkorb befuellen, Bestellnachweis, Bestellung absenden.

Reihenfolge: geeignete offizielle Schnittstelle pruefen, bei Bedarf Drittanbieter evaluieren, dann Browserunterstuetzung als gesonderte Option testen. Eine interne Shop-Schnittstelle ist kein stabiler Vertrag.

Ein Browser-Warenkorb lebt in einer Sitzung. Das Befuellen auf einem Server bedeutet nicht automatisch, dass derselbe Warenkorb auf dem Handy sichtbar ist. Ein angemeldetes Shop-Konto, eine echte Teilen-Funktion oder ein nachgewiesener Uebergabeweg ist erforderlich.

Standort des Browsers (lokaler Rechner oder verwalteter Server) ist offen. Lokaler Betrieb braucht einen laufenden Rechner; Serverbetrieb braucht eigene Sitzungsverwaltung und erreichbare Interaktion fuer Anmeldung/Pruefungen. Der bisherige Test hat keine dieser Betriebsvarianten validiert.

## ChatGPT / MCP

Geplant sind klar umrissene Werkzeuge fuer Bestand lesen, Bedarf erfassen und Einkaufsvorschlag vorbereiten. Datenbankzugriff erfolgt ueber dieselben Services.

MCP ersetzt weder Shop-Login noch eine Bestellschnittstelle. Die konkrete ChatGPT-Anbindung, Authentifizierung und Verfuegbarkeit im verwendeten Zugang werden vor Umsetzung geprueft. Unbeaufsichtigte Wochenauftraege laufen serverseitig.

Menuevorschlaege koennen zunaechst in ChatGPT entstehen. KI direkt innerhalb der App waere eine separate API-Integration mit separat zu klaerenden Kosten und Datenflussen. Die Basis-App funktioniert ohne KI.

## Betrieb

Vor Alltagseinsatz: getrennte Entwicklungs-/Produktionskonfiguration, HTTPS, Geheimnisverwaltung, Datenbankbackup und ein erprobter Restore. Keine privaten Haushaltsdaten in oeffentlichen Repo-Dateien oder Test-Fixtures.

Migrationen versionieren; produktive Migration und Rueckweg dokumentieren. Logs enthalten technische Fehler und fachliche Referenzen, keine Passwoerter, Sitzungscookies oder Zahlungsdaten.

Noch keine Railway-Ressourcen erstellt, keine ENV-Namen verbindlich festgelegt und keine Abhaengigkeiten installiert.
