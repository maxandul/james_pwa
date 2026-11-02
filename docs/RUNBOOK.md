# Lokal starten und spaeter betreiben

Stand: 01.11.2026. Lokale Erstversion; noch kein Railway-Deployment.

## Voraussetzungen

Python 3.12 und die gepinnten Pakete aus requirements-dev.txt. Entwicklung kann SQLite nutzen, Ziel fuer den Betrieb ist Postgres mit Psycopg 3. Eine lokale .env wird nicht automatisch geladen; Variablen in der Shell setzen oder den eigenen Prozessstarter verwenden. env.example enthaelt nur Platzhalter.

## Start auf Windows / PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
$env:APP_ENV = 'development'
$env:SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
$env:DATABASE_URL = 'sqlite:///james.db'
$env:PUBLIC_BASE_URL = 'http://127.0.0.1:5067'
flask --app james db upgrade
flask --app james init-household
flask --app james run --host 127.0.0.1 --port 5067
```

Danach http://127.0.0.1:5067 oeffnen. Persoenlichen Zugang mit dem Verwaltungsbefehl selbst einrichten. Es gibt keine eingebauten Demo-Zugangsdaten und keine offene Registrierungsseite. Ohne gleichbleibenden SECRET_KEY sind bestehende Sitzungen nach einem Neustart ungueltig; fuer dauerhaften lokalen Betrieb einen eigenen geheimen Wert sicher aufbewahren.

## Zugang wiederherstellen / sperren

```powershell
flask --app james reset-password --email person@example.test
flask --app james revoke-member --email person@example.test
```

Reset fragt das neue Passwort verdeckt ab und invalidiert alte Sitzungen. Sperre fragt nach Bestaetigung und verweigert das Sperren des Owner. Diese Befehle sind nur fuer den Betreiber mit Zugriff auf die richtige Datenbank. Kein Passwort im Befehlsargument oder Repo speichern.

## Tests

```powershell
python -m pytest -q
```

Standard: temporaere SQLite-Datenbank pro Test. Postgres-Test benoetigt eine leere, ausschliesslich fuer Tests bestimmte Datenbank mit Namen james_test_*. `JAMES_TEST_DATABASE_URL` wird explizit gesetzt. Test-Fixtures erzeugen und entfernen dort ihre Tabellen; niemals eine produktive URL verwenden. Das Praefix wird vor jeder Fixture geprueft.

Die GitHub-Workflowdatei prueft SQLite sowie Postgres 16, einschliesslich simultaner Nachkauf-/Kaufaktionen. Ausserdem wird die initiale Migration gegen die Modellmetadaten verglichen. Der Migrationstest prueft Upgrade, Schemaabgleich, Downgrade und erneutes Upgrade auf einer separaten SQLite-Testdatei.

## Railway vorbereiten (noch nicht ausgefuehrt)

- Eigenes James-Projekt und Postgres-Service festlegen; Gourmen-Ressourcen nicht verwenden.
- APP_ENV=production, eigener zufaelliger SECRET_KEY (mindestens 32 Zeichen), DATABASE_URL des James-Postgres und PUBLIC_BASE_URL mit dem richtigen HTTPS-Origin setzen.
- App akzeptiert postgresql:// und postgres:// und normalisiert auf postgresql+psycopg://.
- Anforderungen installieren, versionierte Migration vor dem Webstart als separaten Deployment-Schritt ausfuehren: `flask --app james db upgrade`.
- Procfile startet Gunicorn mit zwei Workern und dem bereitgestellten PORT. Health-Pfad: /health.
- Migrationsergebnis mit `flask --app james db current` und `flask --app james db check` kontrollieren.
- Erstbenutzer einmalig via init-household einrichten. Keine Auth-Daten an Logs oder Chat uebergeben.
- Trusted-Proxy-Verhalten und IP-Limits anhand des echten Deployments pruefen. Die App aktiviert absichtlich keinen pauschalen ProxyFix.
- Vor privaten Daten: automatisches Backup und Restore in eine isolierte DB testen. Zusaetzlich Betrieb, Neustart, Cookie-Verhalten und Handy-/Tablet-Bedienung abnehmen.

Keine automatische Anwendung von Migrationen in jedem Webworker. Ein Downgrade der initialen Migration entfernt alle James-Tabellen und ist nur fuer leere Testdatenbanken vorgesehen. Produktive Ruecknahme immer mit gesichertem Backup und eigenem Plan.

## Update der lokalen Vorschau: Artikelpflege

Neue Revision eebb352b7301 fuegt Favoriten- und Archivstatus hinzu. Vor Start der aktualisierten App `flask --app james db upgrade` mit derselben lokalen Datenbank ausfuehren. Der in dieser Sitzung verwendete temporaere Vorschau-Starter james_preview.py erledigt das Upgrade beim Neustart selbst. Ein laufender alter Server muss dafuer gestoppt werden; keine Datenbankdatei loeschen. Testdaten bleiben erhalten.

Die SQLite-Downgradepruefung benoetigt SQLite 3.35 oder neuer fuer natives DROP COLUMN. Die Entwicklung nutzt Python 3.12. Ein Downgrade entfernt die Favoriten-/Archivflags; es ist kein normaler Anwender-Schritt.

## Barcode und optionaler Produktkatalog

Revision b8cf5f8bfc8c mit db upgrade anwenden. Der temporaere Vorschau-Starter erledigt dies beim Neustart; alten Server zuerst mit Ctrl+C stoppen. Keine Datenbankdatei loeschen. Die Scan-Hilfe wird aus Neuer Artikel, Nachkaufen per Barcode im Haushalt oder der Barcode-Zuordnung in der Artikelpflege geoeffnet. Manuelle Eingabe funktioniert ohne Kamera und ohne externen Katalog.

OPENFOODFACTS_ENVIRONMENT akzeptiert staging/production. Standard bei APP_ENV=development: staging (world.openfoodfacts.net); sonst production (world.openfoodfacts.org). Entwicklung und automatisierte Tests nicht gegen den produktiven Katalog richten. Staging verwendet die dokumentierten oeffentlichen Zugangsdaten off:off und kann andere/unvollstaendige Produkte enthalten.

OPENFOODFACTS_USER_AGENT identifiziert die App mit Versions-/Kontaktangabe; Standard verweist auf das James-Repository. Vor Betrieb aktuelle [API-Dokumentation](https://openfoodfacts.github.io/documentation/docs/Product-Opener/api/) und ODbL-Hinweise pruefen. Herkunft und Lizenzlink werden bei Vorschlaegen und gespeicherten Produkten angezeigt. Keine Bilder abgefragt oder hochgeladen. Live-Erreichbarkeit aus Railway noch pruefen.

Kamera braucht einen sicheren Browserkontext (HTTPS oder localhost) und BarcodeDetector-Unterstuetzung. Ein Handy erreicht ueber localhost nicht den PC. Fuer reale Geraetepruefung HTTPS-Vorschau bereitstellen; manuelle Eingabe bleibt als Rueckfallebene.

JavaScript-Pruefung mit Node: `node --test tests/scanner.test.cjs`. Simuliert Kameralebenszyklus, spaete Berechtigungen/Ergebnisse und benannte Formularaktionen; kein Hardwaretest.

## Konkrete HTTPS-Testumgebung vorbereiten

Dateien: Dockerfile, .dockerignore und deployment/railway-settings.json (Referenz, nicht automatisch angewendet). Keine zusaetzliche Start-Command-Ueberschreibung im Railway-Dashboard notwendig. Das Image startet Gunicorn, die Railway-Konfiguration wendet Migrationen als Pre-Deploy an und erwartet /health innerhalb 120 Sekunden. Bei Migrationsfehlern das Deployment untersuchen, nicht durch einen zweiten Webstart umgehen.

1. Separates Railway-Projekt James mit eigener Testumgebung, eigenem Web-Service und Postgres erstellen. Keine bestehenden Gourmen-Ressourcen verbinden. EU-Region fuer beide Services waehlen, sofern im Workspace verfuegbar.
2. Web-Service mit maxandul/james_pwa verbinden, fuer diese Vorschau Branch feat/household-shopping. Nach spaeterem Merge bewusst auf main umstellen. Repository-Zugriff und Railway-Workspace muessen bestaetigt verfuegbar sein.
3. Oeffentliche Railway-Domain erzeugen und diese HTTPS-Adresse als PUBLIC_BASE_URL setzen. Noch keine eigene DNS-Domain erforderlich.
4. Variablen im Web-Service setzen:

| Variable | Testumgebung |
| --- | --- |
| APP_ENV | production (sichere Cookies und Postgres-Pflicht auch in der Vorschau) |
| DATABASE_URL | Railway-Referenz auf den privaten Postgres-Service, z.B. ${{Postgres.DATABASE_URL}} |
| SECRET_KEY | Eigener zufaelliger Wert, mindestens 32 Zeichen; sicher erzeugen und nur in Railway speichern |
| PUBLIC_BASE_URL | Exakter HTTPS-Origin der erzeugten Domain |
| OPENFOODFACTS_ENVIRONMENT | staging fuer die technische Vorschau |
| OPENFOODFACTS_USER_AGENT | App-/Versionsangabe mit Maintainer-Kontakt; kein Geheimnis |

5. Deployment starten. Pre-Deploy-/Build-Logs und erwarteten Git-Commit kontrollieren. Im explizit angegebenen James-Projekt/Environment/Web-Service db current und db check ausfuehren. Keine Variablenwerte oder DB-URLs in Logs/Chat kopieren.
6. Ersten Owner mit dem interaktiven init-household-Kommando im James-Web-Service einrichten; Passwort verdeckt eingeben. Keine eingebauten Demo-Zugaenge und keine automatische Uebernahme der lokalen Vorschau-Daten.
7. `python scripts/check_deployment.py https://DEINE-DOMAIN` prueft Health, Anmeldeseite, CSRF-Feld, Cache-/Sicherheitsheader und sichere Sitzungscookies ohne Zugangsdaten. Das Skript prueft keine Anmeldung oder TLS-Terminierung hinter dem Proxy im Detail.
8. Auf echten Geraeten anmelden, persoenliche Einladung oeffnen, gemeinsamen Bedarf erfassen, Seite neu laden, Rueckgaengig, Scan-Berechtigung und Kamera pruefen. Beide Fold-Displays, Drehen und Tablet einschliessen. Bei Scan-Ausfall manuelle Eingabe pruefen. Hinter Railway besonders IP-Loginlimits und Proxy-Header beobachten; kein pauschales ProxyFix ohne geklaerte Vertrauenskette.

Vor privaten Alltagsdaten Backup/Restore in isolierter Datenbank nachweisen. Bis dahin nur Testdaten verwenden. Downgrade oder Zuruecksetzen einer befuellten Datenbank nicht als Deployment-Reparatur ausfuehren.

Stand dieser Vorbereitung: Railway-CLI ist installiert, aber ihr API-Host ist aus der Agent-Shell nicht aufloesbar. Ein direkter Railway-Zugang muss noch verbunden werden. Deshalb noch keine Projekt-/Service-IDs, HTTPS-Adresse oder erfolgreiche Railway-Abnahme dokumentiert.

## Eingerichtetes James-staging

Stand 01.11.2026: getrennte Ressourcen angelegt, abschliessende Betriebs- und Geraeteabnahme noch offen.

| Ressource | Wert |
| --- | --- |
| Projekt | james-pwa / 9e1b0a24-3eb7-4906-9881-3bae2113f001 |
| Workspace | maxandul's Projects |
| Environment | staging / 6a3cada1-355c-4823-bc7a-c85ba2a68636 |
| Web-Service | james-web / f7326491-f6bb-498c-a58a-9baeb7dbcc40 |
| Datenbank-Service | Postgres / 5e61bc6e-a634-4425-b956-ddae0c7ca70d |
| Datenbank | PostgreSQL 18, persistentes Volume |
| Region | europe-west4-drams3a fuer beide Services |
| HTTPS-Adresse | https://james-web-staging.up.railway.app |
| Quellbranch | feat/household-shopping (automatische Deployments bei Push) |

Railway-OAuth ist verbunden. Die fruehere CLI-DNS-Einschraenkung der Agent-Shell bleibt bestehen; Plattformaktionen erfolgen ueber die direkte Railway-Verbindung. Keine Secrets ausgelesen oder dokumentiert. Keine lokalen Vorschau-Daten uebertragen. Postgres ist nur im privaten Netzwerk verdrahtet.

Einmaliger erster Zugang: im eigenen PowerShell-Terminal ausfuehren. Falls die lokale CLI noch nicht angemeldet ist, zuerst railway login ausfuehren. E-Mail, Name, Haushaltsname und Passwort werden interaktiv erfragt; Passwort nicht in Chat, Befehlsargumente oder Dokumentation kopieren.

```powershell
railway ssh --project 9e1b0a24-3eb7-4906-9881-3bae2113f001 --environment 6a3cada1-355c-4823-bc7a-c85ba2a68636 --service f7326491-f6bb-498c-a58a-9baeb7dbcc40 flask --app james init-household
```

Danach an der HTTPS-Testadresse anmelden und weitere Person ueber Zusammen nutzen einladen. Die lokale Vorschau-Anmeldung gilt hier nicht. Vor Alltagsdaten bleiben Backup/Restore, echtes Login/Einladung und Geraeteabnahme erforderlich. Ein erneutes init-household bei vorhandenem User wird abgewiesen.

## Fehlerkorrektur: fehlende Tabellen bei init-household

Symptom: relation user does not exist trotz vorherigem gruenem /health. Ursache: im aktiven Dienst fehlte das Pre-Deploy-Kommando; die alte railway.json wurde nicht angewendet. SELECT 1 pruefte nur die Verbindung. Der erste Owner wurde bei diesem Fehler nicht angelegt.

Am James-Web-Service im expliziten staging-Environment sind nun diese aktiven Werte zu setzen und vor einem frischen Build zurueckzulesen:

- Pre-Deploy: `flask --app james db upgrade && flask --app james db current && flask --app james db check`
- Healthcheck: /health, Timeout 120 Sekunden.

Die API lehnt die fruehere Railway-Config-File-Einstellung als veraltet ab. Die Sollwerte stehen nur als Referenz in deployment/railway-settings.json. Nicht auf automatische Anwendung einer Root-JSON-Datei vertrauen. Ein frischer Build vom Quellbranch muss die aktuellen Serviceeinstellungen enthalten; ein Erfolg alter Deployment-Snapshots reicht nicht.

Nach Auslieferung muss der neue Schema-Healthcheck ok liefern; er prueft Tabellen und Migrationsrevision. Erst danach denselben interaktiven init-household-Befehl erneut ausfuehren. Keine Datenbank loeschen und kein db stamp als Reparatur verwenden. Das fehlgeschlagene Passwort bleibt ungespeichert; erneut verdeckt eingeben.

## James auf Handy/Tablet installieren und offline testen

1. Die HTTPS-Adresse online oeffnen und anmelden. Unten bestaetigt der Speicherstatus die gesicherte Einkaufsliste. Browser kann lokalen Speicher blockieren; dann erscheint ein Hinweis.
2. Browsermenue: App installieren oder zum Startbildschirm hinzufuegen. Falls der Browser einen Installationsdialog bereitstellt, erscheint auch der James-Installieren-Button. Unter iOS erfolgt das Hinzufuegen ueber Teilen. Die Installation ist eine Aktion des Users.
3. Nach einmaligem Online-Oeffnen etwas auf die Liste setzen und den Status Offline-Liste auf diesem Geraet bereit abwarten. Dann Flugmodus aktivieren und Einkaufsliste oeffnen, auch nach Schliessen/Neustart der App.
4. Gespeicherte Liste muss mit Zeitstempel sichtbar sein und darf keine Kauf-/Bearbeitungsaktionen anbieten. Ohne vorhandenen Snapshot klarer Leerzustand.
5. Wieder online die Online-Liste oeffnen und Aktualisierung pruefen. Offline gibt es keine Warteschlange; keine Aktionen werden spaeter unbemerkt nachgeholt.
6. Abmelden: Kopie und Browsercache werden entfernt. Konto-/Haushaltswechsel darf niemals die vorherige Liste zeigen. Unter Gespeicherte Einkaufsliste laesst sich die Kopie auch explizit entfernen.

Die Offline-Kopie gehoert zum Browserprofil und ist auf einem entsperrten gemeinsamen Geraet lesbar. Ein Rechteentzug wird erst bei erneuter Online-Verbindung erkannt. Installation und Browser-Speicherverwaltung sind kein Backup. Reale Geraeteabnahme bleibt offen, insbesondere Fold-Aussen-/Innendisplay, Flugmodusstart und Tablet.

Tests: `node --test tests/scanner.test.cjs tests/pwa.test.cjs` und `python -m pytest -q`. Kein Schema-/ENV-Update fuer diesen Schritt. Die bestehenden Railway-Pre-Deploy-Einstellungen bleiben aktiv.


## Auslieferung Produkt-/Shop-Grundlage

Neue Revision: 4b4e6934c1ee nach b8cf5f8bfc8c. Additive Tabellen, Product.version und Backfill bestehender Einkaufsorte; keine Bestands-/Bedarfsbuchung.

Der laufende Railway-Service folgt feat/household-shopping. Neue Arbeiten werden deshalb auf feat/product-sources isoliert und per PR gegen diesen Branch geprueft. Vor dem Zusammenfuehren native Sicherung des bestehenden Postgres-Volumes im Railway-Dashboard erstellen; Wiederherstellungsweg dokumentieren. Kein Merge/Deploy vor Sicherung. Aktuelle Connector-Werkzeuge bieten keine Backup-Erstellung; Dashboard war im Agent-Browser nicht angemeldet. Es wurde keine Sicherung behauptet oder Live-Migration ausgefuehrt.

Nach Zusammenfuehren Pre-Deploy upgrade/current/check im expliziten staging-Service beobachten; current muss 4b4e6934c1ee zeigen, /health muss ok liefern. Danach vorhandene Artikel, Einkaufsbedarf und Barcodes kontrollieren, zweite Person/alte Formulare pruefen und Milch mit zwei Einkaufsorten testen. Downgrade wuerde neue Produkt-Shop-Daten entfernen und ist kein regulaerer Rueckgaengig-Weg.


## Belegimport (02.11.2026)

Revision 9172cfe4fad4 nach 4b4e6934c1ee fuegt ausschliesslich receipt_import hinzu. Keine Aenderung bestehender Artikel. Nach Auslieferung db upgrade/current/check und /health pruefen. Die Produkt-/Shop-Migration wurde am 02.11.2026 nach ausdruecklicher Nutzerfreigabe ohne Backup erfolgreich ausgeliefert (keine echten Daten). Generelle Backup-/Restore-Aufgabe bleibt vor echtem Betrieb bestehen.

Einstieg: Einkaufsliste → Einkauf per Beleg erfassen. JPEG/PNG/PDF bis 10 MB, PDF bis drei Seiten oder Text bis 24'000 Zeichen. Maximal 60 Vorschlagszeilen. Native Werkzeuge poppler-utils und Tesseract (deu/eng) sind im Image installiert; Windows-Vorschau ohne diese Werkzeuge bietet weiterhin Texteingabe. Keine externe KI/OCR-Uebertragung. Originaldateien nur temporaer, erkannter Text/Entwurf im Haushalt gespeichert. Private Belegseiten werden nicht offline gecacht.

Erkennung ist ein Vorschlag: Kopf-/Fusszeilen koennen als Kandidaten erscheinen, Gewichts-/Mehrfachpackmengen und Rabatte sind nicht automatisch zuverlaessig zugeordnet. Alle Mengen explizit in ganzen Artikeleinheiten pruefen. Neue Artikel haben Einheit Packung. Unsichere Zeilen ueberspringen. Keine Preisbuchhaltung, automatische Produkt-/Shop-Zuordnung oder direkte Synchronisation mit Haendler-Apps.

Bestaetigung sperrt zuerst den Haushalt und prueft signierte Artikelversionen. Alle Buchungen gemeinsam oder keine. Dieselbe Datei/derselbe normalisierte Text wird nur einmal pro Haushalt angelegt; identische legitime Belege ohne Datum muessen unterscheidbaren Belegtext besitzen. Quittungen verbleiben nach Ruecknahme gesperrt gegen erneutes Verbuchen. Gesammelte Ruecknahme nur ohne zwischenzeitliche Artikelaenderungen; neu angelegte Artikel bleiben erhalten.

Pruefung: python -m pytest -q; node --test tests/scanner.test.cjs tests/pwa.test.cjs; python scripts/check_receipt_tools.py fuer echte synthetische PDF/JPEG/PNG-Erkennung. CI prueft das native OCR auch im Produktionsimage. Reale Coop-/Migros-Bons und Fold/Tablet weiter praktisch abnehmen.


## Einkaufsvorhaben

Neue additive Migration d6e2f6837481 nach 9172cfe4fad4 erstellt purchase_plan. Vorbereitung reserviert offene Artikeleinheiten unter der Haushaltssperre. Bedarf und Bestand bleiben unveraendert. Zwei gleichzeitige Vorhaben duerfen dieselben Bedarfsmengen nicht doppelt reservieren. Produkt-/Angebotsversionen und Artikeleinheiten werden bei Erstellung geprueft; gespeicherte Vorhaben behalten ihre Produkt-/Packungssnapshots.

Einstieg Einkaufsliste → Einkauf vorbereiten. Shop waehlen, Artikel markieren, Menge bestaetigen, Vorhaben speichern. Konkrete Produkte/Packungszahlen und Shoplinks koennen manuell uebertragen, als Text kopiert oder mit der nativen Teilen-Funktion geteilt werden. Keine automatische Warenkorbbefuellung, keine Preise/Verfuegbarkeitsgarantie. Manuell bestaetigter Status bestellt fuehrt keinen Checkout und keinen Wareneingang aus. Beenden/Verwerfen gibt Reservierungen frei; es storniert nichts im Shop.

Kauf, Belegimport oder Entfernen begrenzen verbleibende Reservierungen auf den noch offenen Bedarf (aelteste Vorhaben zuerst). Dabei wird nicht behauptet, welcher Bestellung eine Lieferung zugehoert. Nach erneutem Nachkaufen oder Ruecknahme werden freigegebene Reservierungen nicht automatisch reaktiviert. Neue Plaene bewusst pruefen. Versionswechsel verhindert das Ueberschreiben mit alten Statusformularen. Direkte Teil-/Lieferzuordnung bleibt spaeterer Ausbau.

Pruefung: pytest inkl. Haushaltsgrenzen, Replay, parallelen Reservierungen, Kauf-/Beleg-/Entfernen-Pfaden, Ruecknahme und Packungsrundung. Keine private Shop-Sitzung verfuegbar; angemeldete Native-Uebergabe ist kein bestandenes Abnahmekriterium dieses Teilschritts.
