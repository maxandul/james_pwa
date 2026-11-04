# Galaxus: Anmeldung behalten und Browser übernehmen

Stand: 04.11.2026. **Vorbereiteter Operator-Prototyp, noch kein erfolgreicher
Galaxus-Nachweis und noch keine PWA- oder Warenkorb-Integration.**

## Entscheidung

Den bisherigen, nach jedem Test gelöschten OpenAI-Browser nicht weiter als
Dauerlösung verwenden. Zuerst nachweisen, dass ein manuell angemeldeter
Browserkontext beim erneuten Öffnen nutzbar bleibt. Browserbase bietet Contexts
und eine interaktive Live View. Die Agentensteuerung folgt erst nach diesem
Nachweis; bestehender OpenAI-Schlüssel und laufende Anwendung bleiben erhalten.

## Vorbereitung

Browserbase-Projekt und API-Schlüssel sind erforderlich. In der geprüften
Railway-Web-Konfiguration sind diese noch nicht eingerichtet. Separater Dienst,
separate Abrechnung. Kein Abo wurde abgeschlossen. `keepAlive` benötigt laut
Anbieterdokumentation mindestens Hobby. Keine automatische Tarifbuchung.

Privat als Umgebungsvariablen setzen: `BROWSERBASE_API_KEY`,
`BROWSERBASE_PROJECT_ID`. Nie als Kommandoargument, Chat-Nachricht oder in Git.
Abhängigkeiten: `pip install -r requirements-shop-browser.txt`.

## Bedienung durch den Operator

Ein privater Statuspfad ausserhalb von Git, pro Haushalt ein eigener Pfad.
Hier nur Platzhalter; keine realen Kontodaten in Dokumentation oder Tests.

```sh
python scripts/shop_browser_context.py init --state /private/james-shop/state.json
python scripts/shop_browser_context.py open --state /private/james-shop/state.json
python scripts/shop_browser_context.py close --state /private/james-shop/state.json
python scripts/shop_browser_context.py open --state /private/james-shop/state.json
python scripts/shop_browser_context.py close --state /private/james-shop/state.json
```

`open` gibt einen zeitlich begrenzten Steuerungslink im privaten Terminal aus.
Dieser Link gewährt Browserzugriff: nicht in Logs/CI/Issues veröffentlichen.
Der Nutzer meldet sich in genau diesem Browser selbst an. Danach `close`,
Synchronisierung abwarten, erneut `open` und das sichtbare Konto prüfen.
Die Sitzung ist auf zwölf Minuten begrenzt. Context bleibt beim Schliessen
bestehen. `forget` schliesst die Sitzung und löscht das Providerprofil.

Die Statusdatei speichert nur Projekt-, Kontext- und Sitzungsreferenzen mit
Dateimodus 0600; Cookies bleiben beim Provider. Keine Video-/Konsolenaufzeichnung
angefordert, keine Passwortübergabe an ein Modell. Keine Browseraktionen ausser
Aufruf der Galaxus-Startseite. Kein Agent, kein Kauf, keine Warenkorbänderung.

Bei `creation_pending` ist der Ausgang einer API-Erstellung unklar: im privaten
Provider-Dashboard abgleichen, bevor der Marker manuell bereinigt wird.
Nicht erneut erstellen und dabei unbekannte Sitzungen vervielfachen. Sitzungen
enden zusätzlich über das Provider-Zeitlimit. Bei fehlgeschlagener Bereinigung
bleibt die Sitzungsreferenz für einen weiteren `close`-Versuch erhalten.

## Abnahme und nächste Umsetzung

1. Galaxus im bereitgestellten Browser erreichbar, ohne Umgehung einer Sperre.
2. Nutzer kann sich anmelden; sichtbares richtiges Konto manuell bestätigen.
3. Nach Schliessen und Wiederöffnen ist die Anmeldung weiterhin sichtbar.
4. Android/iPhone-Eingabe praktisch testen. Browserbase unterstützt mobile
   Tastaturen in der Live View laut Dokumentation nicht direkt. Für James ist
   daher ggf. ein eigener Eingaberelay nötig; Desktop-Erfolg reicht nicht.
5. Erst dann Haushaltsbindung, CSRF-geschützte PWA-Steuerung, Sperre zwischen
   Nutzer und Agent, Widerruf und private Fehlerdiagnose implementieren.
6. Agent soll ein freigegebenes Testprodukt gezielt auf Sollmenge setzen;
   Warenkorb danach unabhängig im normalen Galaxus-Konto kontrollieren.
7. Wiederverwendung beim nächsten Auftrag prüfen. Bestellauslösung bleibt eine
   spätere, separate Funktion mit konkreter Warenkorb-/Kostenfreigabe.

Eine gespeicherte Sitzung garantiert weder dauerhaft gültige Anmeldung noch
Akzeptanz des Cloud-Browsers durch Galaxus. Scheitert bereits der manuelle Login
an einer Zugriffssperre, wird dieser Weg beendet und ein nutzereigener Browser
als Alternative geprüft. Kein Wechsel von Proxy/Identität zur Umgehung.

## Quellen

- https://docs.browserbase.com/platform/browser/core-features/contexts
- https://docs.browserbase.com/platform/browser/observability/session-live-view
- https://docs.browserbase.com/reference/api/create-a-session
- https://docs.browserbase.com/reference/api/update-a-session
