# Architekturvorschlag

Stand: 01.11.2026. Flask-Basis und erster Einkaufsablauf implementiert. Postgres ist das Betriebsziel; Railway ist noch nicht eingerichtet. Weitere Komponenten bleiben Vorschlaege.

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

Bestaetigt und umgesetzt: E-Mail/Passwort, Registrierung nur per persoenlicher Einladung. Der Betreiber legt den ersten Owner per CLI an. Weitere Details und Grenzen in [AUTH.md](AUTH.md). Ein Shared-Tablet-Zugang ist kein allgemeiner administrativer Zugang. Er darf schnell Bedarf erfassen, aber keine Rechte oder Shop-Geheimnisse verwalten.

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

Noch keine Railway-Ressourcen erstellt. Abhaengigkeiten sind in requirements.txt gepinnt; ENV-Variablen stehen in env.example. Betrieb und Migration siehe [Runbook](RUNBOOK.md).

## Implementierter Ausschnitt

App Factory, Flask-SQLAlchemy/SQLAlchemy, Flask-Login, Flask-WTF-CSRF und Flask-Migrate/Alembic. SQLAlchemy-URL wird fuer Postgres auf Psycopg 3 normalisiert. SQLite ist nur fuer lokale Entwicklung und die isolierten Standardtests vorgesehen.

Blueprints auth und main, zentrale Fachregeln in services.py. Jeder Browser-Schreibzugriff nutzt CSRF und den serverseitig ermittelten Haushalt. PostgreSQL-Zeilensperren, Versionspruefung und Activity-UUIDs schuetzen vor verlorenen bzw. wiederholten Buchungen.

Die erste Version nutzt noch keine WebSockets, KI, Shop-Zugaenge, Bild-Uploads, Mengenbestaende oder Hintergrundauftraege. Auth-HTML ist no-store; es gibt noch keinen Service Worker. Der unprivilegierte Tablet-Geraetezugang ist offen.

Pruefung: SQLite-Suite lokal erfolgreich. Lokale TCP-Verbindungen zu Postgres und Webserver sind in der Arbeitsumgebung blockiert. Postgres-CI und visuelle Zielgeraetepruefung sind deshalb getrennt zu verifizieren; siehe VALIDATION.md.
