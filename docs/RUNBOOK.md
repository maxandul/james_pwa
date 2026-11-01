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
