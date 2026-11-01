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

Die erste Version nutzt noch keine WebSockets, KI, Shop-Zugaenge, Bild-Uploads, Mengenbestaende oder Hintergrundauftraege. Auth-HTML bleibt no-store; der Service Worker speichert ausschliesslich eine anonyme Offline-Huelle und ausgewaehlte oeffentliche Assets. Der unprivilegierte Tablet-Geraetezugang ist offen.

Automatisierte Pruefung: lokale SQLite-Suite und GitHub-CI gegen Postgres 16 mit Migrationsvergleich. Die lokale Arbeitsumgebung blockiert TCP-Verbindungen; Postgres wird deshalb in CI geprueft. Der aktuelle Pruefstand steht in VALIDATION.md. Visuelle Zielgeraetepruefung bleibt offen.

Artikelpflege erweitert den bestehenden Service-Layer um Bearbeiten, gemeinsamen Favoritenstatus, Archivieren/Wiederaktivieren, Bestandskorrektur und Listenentfernung. Die beiden Archiv-/Favoritenflags und die portable Datenbankmigration sind in DATA_MODEL.md dokumentiert; es wurde kein neuer externer Dienst eingefuehrt.

## Barcode-Erfassung

Blueprint scan steuert die Erfassung; barcodes.py validiert GTINs und kapselt Haushaltszuordnungen. Konkrete Produktvarianten gehoeren jeweils zu einem Haushaltsartikel. Scan und Zuordnung veraendern weder Bestand noch Einkaufsbedarf.

scanner.js verwendet ausschliesslich den nativen BarcodeDetector und getUserMedia nach bewusstem Start. Bilder verlassen das Geraet nicht. Kamera ist nur fuer die Scan-Seite erlaubt; bei fehlender Browserunterstuetzung bleibt die manuelle Eingabe. Reale Kamera-/HTTPS-Pruefung steht aus.

catalog.py fragt Open Food Facts nur auf ausdruecklichen Wunsch mit dem Barcode ab, ohne Haushaltsdaten oder Bilder. Feste HTTPS-Hosts, keine Weiterleitungen, drei Sekunden Timeout und begrenzte Antwortgroesse. Oeffentliche Vorschlaege werden getrennt von Haushaltsdaten einen Tag gecacht, fehlende Treffer eine Stunde. Ein Datenbank-Gate begrenzt ausgehende Abfragen pro Umgebung auf eine alle fuenf Sekunden ueber alle Worker. Entwicklungsumgebung nutzt standardmaessig den Testkatalog; Konfiguration siehe RUNBOOK.md. Externe Vorschlaege bleiben manuell zu pruefen.

Der Scanner ist als kontextbezogene Hilfsseite ohne eigenen Navigationstab integriert. scan.py erhaelt den Zweck Artikelanlage/Nachkaufen/Artikelzuordnung in expliziten Formularfeldern und erzeugt ausschliesslich lokale Ruecksprungziele. Zuordnungen aus der Artikelpflege sind an deren erneut geprueften Haushaltsartikel gebunden. Kein Schemawechsel.

## Vorbereitetes Railway-Deployment

Dockerfile definiert Python 3.12, nur Laufzeitabhaengigkeiten und einen Benutzer ohne Root-Rechte. Explizite COPY-Pfade und .dockerignore halten lokale Datenbanken, Secrets, Tests und Vorschau-Daten aus dem Image. Gunicorn startet wsgi:app mit zwei Workern und Railway-PORT (lokaler Containerstandard 8080).

deployment/railway-settings.json (Referenz, nicht automatisch angewendet) waehlt den Docker-Build, fuehrt Alembic als Pre-Deploy-Kommando vor dem Webstart aus und prueft /health. Fehlgeschlagene Migration verhindert den neuen Webstart. Keine Migration in jedem Worker und keine automatisch angelegten Konten. Bestehende Datenbanken brauchen weiterhin Backup und einen geprueften Rueckweg.

CI baut das echte Image und prueft Gunicorn gegen isoliertes Postgres mit Produktionseinstellungen. Dieser Nachweis ersetzt keine Railway-/TLS-/Proxy-Pruefung. Erstes Ziel ist ein getrenntes James-Testprojekt mit eigenem Postgres, HTTPS-Origin und Open-Food-Facts-Testkatalog. Noch keine Railway-Ressourcen angelegt.

## Eingerichtete Testinfrastruktur

Das getrennte Projekt james-pwa liegt im Workspace maxandul's Projects, Environment staging. james-web und Postgres befinden sich in europe-west4-drams3a. Postgres verwendet das aktuelle Railway-Template mit Version 18 und persistentem Volume; deshalb prueft die aktuelle CI ebenfalls Postgres 18 (fruehere Laeufe nutzten 16). Der Web-Service nutzt ausschliesslich die private DATABASE_URL-Referenz; es wurde kein oeffentlicher Datenbankproxy angelegt.

HTTPS-Testdomain: https://james-web-staging.up.railway.app. Der Web-Service folgt feat/household-shopping; Pushes loesen Deployments aus. APP_ENV=production aktiviert die sicheren Cookie-/Konfigurationsregeln auch in staging. Produktvorschlaege verwenden weiterhin den Testkatalog. Pre-Deploy wendet Migrationen an und verifiziert db current sowie db check. Keine Benutzer automatisch angelegt; erster Owner per interaktiver CLI.

## Korrektur des Deploymentpfads

Der aktive Railway-Dienst hatte die fruehere railway.json nicht uebernommen. Die API weist diese Konfigurationsart inzwischen als veraltet zurueck. Die frueheren Aussagen zur automatischen Anwendung waren daher nicht zutreffend. Aktive Betriebsparameter werden direkt am expliziten james-web/staging-Service gesetzt und zurueckgelesen. deployment/railway-settings.json dokumentiert die Sollwerte, ist kein automatisch angewendetes Deploymentfile. Die irrefuehrende Root-Datei wurde entfernt. Eine spaetere IaC-Einfuehrung ist ein eigener Schritt mit Planpruefung.

readiness.py prueft fuer /health alle erwarteten Modelltabellen und den Alembic-Stand gegen die Migrationen des laufenden Images. Erreichbare, leere oder veraltete Datenbanken erhalten HTTP 503 statt ok. Oeffentliche Antworten enthalten keine Schemanamen oder Fehlerdetails. Erst ein erfolgreicher Schema-Healthcheck und kontrollierter Migrationslauf belegen die Bereitschaft zur Ersteinrichtung.

## PWA und gespeicherte Einkaufsliste

pwa.py stellt Manifest, Worker unter /sw.js mit Root-Scope, anonyme /offline-Huelle und /api/offline-list bereit. Der private GET-Endpunkt prueft persoenlichen Zugang und aktive Mitgliedschaft, liefert nur den vollstaendigen aktuellen Bedarf dieses Haushalts und setzt no-store. Er bucht nichts und akzeptiert keine frei waehlbare Haushaltskennung.

Der Service Worker cached nur eine explizite Liste oeffentlicher Assets und die anonyme Offline-Huelle. Er speichert keine angemeldeten Seiten, Login-/Einladungsseiten, API-Antworten oder POSTs. Nur Navigationen zu Haushalt/Einkauf/Offline bekommen bei Netzwerkfehler die Offline-Huelle. Updates entfernen ausschliesslich alte James-Shell-Caches.

pwa.js speichert die bestaetigte JSON-Liste getrennt im lokalen Geraetespeicher. offline-store.js bindet die einzelne Kopie an User, Auth-Version und Haushalt. Konto-/Sitzungswechsel oder Abmelden entfernen sie; Generationskennungen verhindern Wiederherstellung durch verspaetete Antworten. Aeltere Antworten duerfen neuere Snapshots nicht ersetzen. Logout setzt zusaetzlich Clear-Site-Data fuer storage/cache. Keine Passwoerter, CSRF-Token oder Einladungen im Offline-Speicher.

Die Offline-Kopie ist lesbar fuer Personen mit Zugriff auf dieses Browserprofil/Geraet. Rechteentzug kann ohne Verbindung nicht neu geprueft werden; beim naechsten Online-Abgleich werden 401/403 geloescht. Keine Offline-Schreibwarteschlange. Browser koennen Speicher entfernen; kein Ersatz fuer ein Serverbackup. Keine neue Datenbankmigration oder externe Abhaengigkeit.
