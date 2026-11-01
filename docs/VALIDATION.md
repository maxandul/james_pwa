# Pruefstand der ersten Version

Stand: 01.11.2026.

## Lokal nachgewiesen

- App Factory erstellt acht Tabellen in isolierter Testdatenbank; Health und Anmeldeseite antworten.
- SQLite-Suite: 24 Tests bestanden, ein Postgres-spezifischer Test mangels Test-URL uebersprungen.
- E-Mail/Passwort, CSRF, generische Anmeldefehler und dauerhaftes Login-Limit.
- E-Mail-gebundene Einladungen mit Hash, Ablauf, Widerruf, erneuter Ausstellung und Einmalverwendung.
- Zwei Mitglieder sehen dieselbe Liste; fremde Haushaltsartikel und Einladungsverwaltung sind gesperrt.
- Entzogene Mitgliedschaft sperrt bestehende Sitzung; Passwortreset invalidiert alte Sitzungen.
- Nachkauf ohne doppelten Grundbedarf, Request-Replay, Versionskonflikt, Zusatzmenge, Teilkauf, Ruecknahme und Schutz vor veralteter Ruecknahme.
- Initiale Migration: Upgrade, Schemaabgleich, Downgrade und erneutes Upgrade auf separater SQLite-Datei.

Ein Fehler in der Fehlerseite bei entzogener Mitgliedschaft wurde durch die Tests gefunden und korrigiert. Ein Haushaltsisolationstest wurde auf den konkreten Artikel-Link statt eines generischen Beispielworts in der leeren Ansicht praezisiert.

## Umgebungsgrenzen

Ein isolierter lokaler Postgres-16-Cluster wurde gestartet. Der Testprozess durfte keine TCP-Verbindung dorthin oeffnen (Permission denied). Der Browser konnte auch den gestarteten lokalen Flask-Webserver nicht erreichen (Connection timed out). Das belegt keine Funktionsstoerung von Postgres oder Flask und wird nicht als erfolgreicher Integrationstest gewertet.

Die Postgres-Suite einschliesslich simultaner Requests und Migrationsvergleich ist im GitHub-Workflow vorbereitet. Ihr tatsaechliches Ergebnis ist am Pull Request separat nachzuweisen. Bis dahin bleibt Postgres-Integration unabgenommen.

## Vor Alltagseinsatz noch offen

- Visuelle und interaktive Desktop-/Handy-/Tabletpruefung in erreichbarer Umgebung.
- Tatsaechliche HTTPS-/Proxy-Konfiguration, Login-Limits hinter Railway und Cookie-Verhalten.
- Railway-Deployment und Produktionsmigration; Backup und Restore.
- Eingeschraenkter Geraetezugang, Barcode, Mengenbestand und Offline-Lesen.

Es wurden keine echten Benutzerpasswoerter, Shop-Zugaenge oder privaten Haushaltsdaten fuer Tests verwendet.
