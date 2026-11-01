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

## GitHub-CI erfolgreich

[Prueflauf 41318470053](https://github.com/maxandul/james_pwa/actions/runs/41318470053) am Implementierungscommit 63dbceb93de9b63c3d081d05156800a8a3e11c27:

- SQLite: 24 bestanden, zwei nur fuer Postgres vorgesehene Tests uebersprungen.
- Postgres 16: 26 Tests bestanden, einschliesslich parallelem Nachkaufen/Einkaufen und gleichzeitigem Neuausstellen von Einladungen.
- Initiale Migration gegen Postgres angewendet; db check meldet keine Abweichung der Modellmetadaten.

Ersteinrichtung separat lokal geprueft: erster Owner samt Haushalt angelegt, erneute Initialisierung abgewiesen. Kein produktiver Datenbankzugriff.

Die ersten CI-Laeufe scheiterten vor den Tests an der Anfuehrungszeichenfolge im Container-Healthcheck. Die Workflow-Konfiguration wurde korrigiert; der oben verlinkte Lauf ist erfolgreich.

## Vor Alltagseinsatz noch offen

- Visuelle und interaktive Desktop-/Handy-/Tabletpruefung in erreichbarer Umgebung.
- Tatsaechliche HTTPS-/Proxy-Konfiguration, Login-Limits hinter Railway und Cookie-Verhalten.
- Railway-Deployment und Produktionsmigration; Backup und Restore.
- Eingeschraenkter Geraetezugang, Barcode, Mengenbestand und Offline-Lesen.

Es wurden keine echten Benutzerpasswoerter, Shop-Zugaenge oder privaten Haushaltsdaten fuer Tests verwendet.

## Erweiterung Artikelpflege

Lokal: 42 Tests bestanden; drei ausschliesslich fuer Postgres vorgesehene Parallelitaetstests uebersprungen. Der aktuelle CI-Nachweis fuer den jeweiligen Implementierungsstand steht bei [PR #2 / Checks](https://github.com/maxandul/james_pwa/pull/2/checks).

Neue Prueffaelle: Metadaten bearbeiten und zuruecknehmen, vier Bestandszustaende ohne Aenderung des Einkaufsbedarfs, Listenentfernung ohne Kaufbuchung, gemeinsame Favoriten samt Filter/Replay, Archivierung nur ohne offenen Bedarf, Wiederaktivierung, keine Nachbestellung archivierter Artikel, veraltete Formulare, Einheitenwechsel bei offenem Bedarf, Haushaltsgrenzen, Suche und kompatible Ruecknahme alter Activity-Snapshots.

Migration zusaetzlich mit vorhandenen Artikeln, offenem Bedarf und referenzierender Historie getestet: Upgrade, Ruecknahme der neuen Flags und erneutes Upgrade erhalten die bisherigen Daten. Der Postgres-spezifische Test prueft paralleles Archivieren/Nachkaufen und verhindert unsichtbaren offenen Bedarf.

Responsive CSS ist fuer Touch und flexible Viewportbreiten angepasst. Keine Behauptung einer erfolgten visuellen Fold-/Tablet-Abnahme; diese braucht den Neustart der erreichbaren Vorschau und die echten Zielgeraete. Die Datenbank der laufenden User-Vorschau wurde nicht veraendert.

## Erweiterung Barcode

Gezielte lokale Pruefung nach Herkunftsergaenzung: 33 Barcode-/Migrationstests bestanden. Vorherige komplette SQLite-Suite: 72 bestanden, fuenf nur fuer Postgres vorgesehene Tests uebersprungen. JavaScript: fuenf Node-Tests bestanden. Den abschliessenden Gesamtstand belegt der aktuelle Lauf bei PR #2 / Checks.

Geprueft: Laengen/Pruefziffern/fuehrende Nullen, UPC-/EAN-Aequivalenz, CSRF, Haushaltsgrenzen, wiederholte Registrierung, Zuordnung zu bestehenden/neuen Artikeln, archivierte Artikel, Entfernen ohne Bedarfsaenderung, Herkunft, manuelle Eingabe bei Katalogausfall, Cache und Abrufbegrenzung. HTTP-Tests simulieren feste HTTPS-Ziele, Timeout, Fehler und begrenzte Antwortgroesse; keine echte Provider-Erreichbarkeit behauptet.

Postgres-CI prueft zusaetzlich gleichzeitige Erstregistrierung und konkurrierende Katalogabrufe. Node simuliert fehlende APIs, Start per Benutzeraktion, genau einmalige Erkennung, Stoppen nach spaeter Berechtigung und Hintergrundwechsel sowie Erhalt der benannten Katalogaktion. Keine echte Kamera oder visuelle Fold-/Tablet-Pruefung. Die laufende Vorschau-Datenbank wird erst beim vom User ausgefuehrten Neustart migriert.

## Scan als Prozesshilfe

Sechs zusaetzliche Integrationstests pruefen die Einstiege ohne Scan-Tab, Artikelanlage mit Rueckkehr und ohne Kauf, festes Artikelziel bei Zuordnung, fremde Kontextartikel, bestehende andere Zuordnungen sowie Kontexterhalt bei ungueltigem Code und Katalogfehler. Keine Schemaaenderung. Vollstaendige Pruefung inklusive Postgres ueber PR #2 / Checks. Visuelle Geraeteabnahme bleibt offen.

## Deployment-Vorbereitung

Dockerfile und railway.json sind fuer getrennten James-Testbetrieb vorbereitet. CI baut das Produktionsimage, startet den echten Gunicorn-Prozess gegen isoliertes Postgres und prueft Health, Login-HTML samt CSRF, no-store, CSP, HSTS und Secure/HttpOnly/SameSite-Cookie. Ergebnisse im aktuellen PR-Check.

Lokal kein Docker-Befehl verfuegbar; kein lokaler Image-Build behauptet. Railway-CLI 5.28.0 startet, aber whoami/list scheitern an DNS fuer backboard.railway.com. Keine Railway-Ressource erstellt und keine Deployment- oder produktive DB-Aktion ausgefuehrt. Railway-Verbindung, HTTPS-/Proxy-Verhalten und echte Geraete bleiben offen.

## Railway-staging eingerichtet

Getrenntes Projekt james-pwa mit eigenem Postgres-18-Volume und james-web in europe-west4-drams3a erstellt. HTTPS-Domain und private DB-Referenz konfiguriert; Web-Service an feat/household-shopping angebunden. Erstes Deployment startet vom zuvor in CI geprueften Commit eb6ad8cb4956fe45321bfd168a6a07be5ca48f48. Nachfolgende Konfiguration prueft im Pre-Deploy zusaetzlich current/check und richtet die CI auf Postgres 18 aus.

Endgueltigen Deploymentstatus im Railway-Dashboard pruefen; angelegte Ressourcen sind noch kein Nachweis eines erfolgreichen Deployments. Kein erster Owner eingerichtet, keine Login-/Einladungs-/Kamerapruefung und kein Backup/Restore behauptet. Aktuelle HTTPS-Adresse und IDs im Runbook. Automatisierte CI-Ergebnisse bleiben in PR #2 / Checks nachvollziehbar.

Erstes Web-Deployment e92d81be-f267-43ca-80d4-e305749a6ad1 erreichte SUCCESS. Browseraufruf der HTTPS-Domain zeigt die James-Anmeldeseite; /health liefert status ok und bestaetigt die Verbindung zu Postgres. Persoenliche Anmeldung weiterhin offen, da erster Owner interaktiv durch den User einzurichten ist.

## Korrektur des unvollstaendigen Betriebsnachweises

Der User meldete bei der Ersteinrichtung eine fehlende user-Tabelle. Die bisherigen gruenen Healthchecks und SUCCESS-Deployments belegten nur Webstart und Datenbankverbindung, keine ausgefuehrten Migrationen. Diese Grenze wurde zuvor faelschlich als vollstaendiger Deploymentnachweis behandelt.

Aktive Servicekonfiguration kontrolliert: kein Pre-Deploy/Healthcheck vorhanden. Sollwerte direkt am James-Web-Service gesetzt und zurueckgelesen; alte Config-as-Code-Datei von Railway als veraltet zurueckgewiesen. Referenz nach deployment/railway-settings.json verschoben. Frischer Quellbuild und Schema-Readiness sind fuer die Wiederabnahme erforderlich.

Vier neue Regressionstests pruefen erreichbare Datenbank ohne Revision, vollstaendiges aktuelles Schema, veraltete Revision und fehlende Tabelle trotz aktuellem Stamp. Lokale SQLite-Pruefung erfolgreich; Postgres und Container folgen im aktuellen PR-Check. Neuer /health kann eine leere Datenbank nicht mehr als bereit melden.

Die bisherige Health-Testannahme (create_all ohne Migration meldet ok) wurde auf 503/unavailable angepasst. Railway protokolliert nun die drei tatsaechlich ausgefuehrten Upgrades bis b8cf5f8bfc8c; der neue Schema-Healthcheck liefert ueber HTTPS ok.

## PWA und Offline-Lesen

Fuenf neue Flask-Tests pruefen Manifest/PNG-Icons/Worker-Scope, identitaetsfreie Offline-Huelle, no-store und Zugriffsschutz des Snapshots, Haushaltsisolation/Read-only sowie Logout-Loeschheader. Node prueft Kontowechsel, verspaetete Antworten nach Logout/Speicherreset, fremde Antworten, Reihenfolge der Snapshots, oeffentliche Cache-Allowlist, Ausschluss von Auth/API/POST, Navigation-Fallback und Cache-Upgrade. Zusaetzlich gerenderte Textdaten, explizites Entfernen und Logout waehrend einer laufenden Abfrage simuliert.

Die automatisierten Tests ersetzen keine Installation oder echten Flugmodus auf dem Fold/Tablet. User bestaetigt allgemeine Online-Ablaeufe; Kamerascan bei schlechtem Licht noch nicht erfolgreich. Keine Kameraabnahme behauptet. Aktuelle CI-Nachweise in PR #2 / Checks.

Zusaetzliche asynchrone UI-Pruefung: Bereitmeldung erst nach abgeschlossenem Service-Worker-Install. Browserpruefung der oeffentlichen Offline-Ansicht auf Railway: Leerzustand vorhanden und keine Skriptfehler; Screenshot-Aufnahme durch Browser-Timeout begrenzt. Keine echte Flugmodus-/Installationsabnahme behauptet.
