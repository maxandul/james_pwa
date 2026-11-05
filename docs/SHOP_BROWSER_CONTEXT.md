# Galaxus: Anmeldung behalten und Browser übernehmen

Stand: 04.11.2026. Manuelle Anmeldung und Wiederverwendung des gespeicherten
Profils nach Schliessen und erneutem Öffnen wurden vom Nutzer bestätigt.
Der Nutzer hat anschliessend den Warenkorbtest unabhängig mit den richtigen
Produkten und Gesamtmengen im echten Kontowarenkorb bestätigt.
Kein Bestellabschluss implementiert.

Erweiterung vom 05.11.2026: separate Profile je Shop, Coop-Verbindung und genaue
Testvorschau siehe [COOP.md](COOP.md). Bestehendes Galaxus-Profil bleibt erhalten.

## PWA-Verbindungstest

`/shop-browser` bietet dem Eigentümer des gebundenen Haushalts:

- Browser nach ausdrücklichem Start mit Speicherung der Shop-Anmeldung öffnen.
- Private Browseransicht in einem neuen Fenster öffnen; dort selbst anmelden.
- Sichtbares richtiges Konto manuell bestätigen (kein unabhängiger Nachweis).
- Speichern und schliessen; dasselbe Browserprofil danach erneut öffnen.
- Gespeichertes Profil und Anmeldung beim Provider löschen.

Zustandsänderungen brauchen POST, CSRF und die aktuelle Datensatzversion.
Haushalt und Eigentümer stammen aus der James-Anmeldung. Links sind nicht
öffentlich gelistet oder protokolliert; die private Weiterleitung prüft Nutzer,
Haushalt, Sitzungsversion und Ablauf erneut. Ein bereits geöffnetes Fenster
wird durch das Schliessen der Provider-Sitzung unbrauchbar. Cookie-/Profildaten
bleiben beim Provider; die James-Datenbank hält private Providerreferenzen und
während der Sitzung den temporären Steuerungslink. Kein Shop-Passwort wird an
ein Modell übergeben; keine Video- oder Konsolenaufzeichnung angefordert.

Der vorhandene einzelne `shop-login-worker --watch` bearbeitet die Warteschlange.
Er hält die CDP-Verbindung offen, ohne kostenpflichtiges Keep-alive anzufordern.
Höchstens zwölf Minuten ab Start in James; Provider-Zeitlimit zusätzlich zwölf
Minuten ab Browsererstellung. Free-Plan laut aktueller Preisübersicht:
15 Minuten je Sitzung. Kein Upgrade vorausgesetzt, Tarifverfügbarkeit beim
Live-Test prüfen. Keine Proxies, kein CAPTCHA-Lösen, kein Stealth-Wechsel.

Bei «wird vorbereitet» den Statuslink verwenden. Nach Ablauf oder Worker-Neustart
werden bekannte Sitzungen geschlossen und das Profil bleibt erhalten.
Unklare Erstellung (`creation_unknown`) wird nicht wiederholt: Operator muss im
Provider-Dashboard abgleichen. Fehlgeschlagene Bereinigung behält die Referenz;
Löschabsicht geht bei einem Netzwerkfehler nicht verloren. Entzogene Mitgliedschaft
oder geänderte James-Anmeldung lösen Profilbereinigung aus. Automatischer Worker
braucht genau eine laufende Instanz; parallele CDP-Worker sind nicht unterstützt.

## Deployment

Web und Worker auf denselben getesteten Commit bringen. Web führt die Migration
bis zum aktuellen Head `a47b9d31e602` aus. Worker beginnt neue Browserjobs erst bei bereitem Schema.
Auf beiden Services `SHOP_BROWSER_ENABLED=1` setzen. Bestehende
`GALAXUS_HOUSEHOLD_ID` bleibt. Nur der Worker braucht `BROWSERBASE_API_KEY` und
`BROWSERBASE_PROJECT_ID`; beide sind dort vom Nutzer bereits hinterlegt.
Bestehender OpenAI-Schlüssel bleibt unverändert.

Kein Browserstart allein durch Deployment oder GET. Keine Warenkorbänderung,
kein Agent und kein Checkout durch diesen Verbindungstest. Der alte Pilot bleibt
separat, parallele Starts mit einem offenen neuen Browser werden abgewiesen.

## Abnahme

1. In James «Galaxus verbinden» starten, Browser öffnen, selbst anmelden.
2. Richtiges Konto sichtbar bestätigen und «Speichern und schliessen» wählen.
3. Warten bis «Bereit», gespeicherten Browser erneut öffnen.
4. Prüfen, ob ohne neuen Login dasselbe Konto sichtbar ist.
5. Den separaten Warenkorbtest für die angezeigten drei Produkte starten;
   danach den Warenkorb unabhängig auf dem normalen Gerät kontrollieren.

Desktop zuerst. Mobile Tastaturen werden in der Browserbase-Live-View laut
Dokumentation nicht direkt unterstützt; komfortabler mobiler Eingaberelay bleibt
offen. Anmeldung kann vom Shop widerrufen werden. Gespeicherte Cookies sind kein
Nachweis für eine gültige oder dauerhafte Anmeldung.

## Operator-Prototyp und CLI

`scripts/shop_browser_context.py` bleibt als separater Operator-Prototyp vorhanden.
Seine `open`-Variante trennt den Client und fragt deshalb weiterhin Keep-alive an;
nicht mit dem Free-Plan-PWA-Worker verwechseln. CLI-Zugang kann über `browse`
(bei Entwicklung geprüft: 0.11.3) erfolgen. Railway-OAuth liefert dieser Umgebung
nur Variablennamen. Die versuchte CLI-Anmeldung wurde durch die Netzwerksperre zu
`backboard.railway.com` verhindert. Deshalb erfolgt der PWA-Test direkt auf Railway,
mit dort vorhandenen Schlüsseln, ohne Export in Chat oder Logs.

## Quellen

- https://docs.browserbase.com/platform/browser/core-features/contexts
- https://docs.browserbase.com/platform/browser/observability/session-live-view
- https://docs.browserbase.com/reference/api/create-a-session
- https://docs.browserbase.com/reference/api/update-a-session
- https://www.browserbase.com/pricing

## Begrenzter Warenkorbtest im gespeicherten Browser

Nach dem Öffnen und der Bestätigung des richtigen Kontos bietet `/shop-browser`
einen separaten Teststart mit den festen Gesamtmengen 2/1/1 aus `shop_cart.py`.
Nur der gebundene Haushaltseigentümer darf starten; CSRF, Versionsprüfung,
bestätigte aktive Sitzung und mindestens drei Minuten Restzeit sind erforderlich.
Der bestehende Worker übernimmt den Auftrag einmalig in derselben CDP-Sitzung.
Ein Neustart führt zu `INTERRUPTED`, niemals zur automatischen Wiederholung.

Der ComputerToolset-Runner verwendet `gpt-6.1-sol`, maximal 40 API-Schritte und
neun Minuten innerhalb der verbleibenden Browsersitzung. API-Aufrufe haben
45 Sekunden Timeout und keine automatischen Wiederholungen. Screenshots werden
nur im Arbeitsspeicher gehalten und zur Steuerung an OpenAI gesendet (`store=false`).
Gespeichert werden ausschliesslich feste Ergebniscodes und die Klickanzahl.
Der Driver erlaubt passende Galaxus-Leseziele, Produktsuche nach den drei IDs und
begrenzte Hinzufügen-Klicks auf deren Produktseiten. Checkout, Bestellen,
Mengeneditoren, fremde Produkte und beliebige Tastatureingaben sind nicht freigegeben.
Unbekannte Bedienelemente stoppen mit `CONTROL_BLOCKED`; die Allowlist muss bei
Shop-Änderungen gegebenenfalls anhand eines konkreten Tests angepasst werden.

`CART_READY` wird ausdrücklich als Agentenmeldung angezeigt. Der Eigentümer hat
den erfolgreichen Galaxus-Test im Gespräch unabhängig auf seinem Gerät bestätigt.
Dies ist keine nachträglich automatisch gesetzte technische Prüfung in der App.
Teiländerungen werden nicht automatisch zurückgesetzt. Zum Abbrechen dient
«Speichern und schliessen»; während eines Laufs den Shop nicht parallel bedienen.
Web und Worker müssen gemeinsam auf dieselbe Migration ausgeliefert werden.
