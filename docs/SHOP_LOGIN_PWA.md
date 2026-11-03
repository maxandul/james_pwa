# Gemeinsames Galaxus-Konto im PWA-Anmeldepilot

Der Anmeldepilot ist nach ausdruecklicher Freigabe auf Railway in `staging`
bereitgestellt und aktiviert. Die Shop-Zugangsdaten wurden vom Nutzer direkt
im Worker hinterlegt; ihre Werte wurden nicht ausgelesen. Ein erster
PWA-Anmeldetest endete mit der bisherigen unspezifischen Abschlussmeldung.
Ein erfolgreicher Kontologin ist damit weiterhin nicht nachgewiesen.

## Ziel und aktueller Umfang

Ein bestehendes Galaxus-Konto gehoert zum Haushalt. Berechtigte Mitglieder
koennen einen Test starten; der zugehoerige Auftrag und manuelle Anmeldeschritte
bleiben nur fuer die startende Person sichtbar. Pro Haushalt darf genau ein
Auftrag offen sein, auch bei unklarer Bereinigung. Die Datenbank erzwingt dies
mit einem eindeutigen aktiven Haushaltsslot. Hoechstens zwei Tests pro UTC-Tag
und Haushalt fuer reine Anmeldungen sowie ein separater Warenkorbtest pro
UTC-Tag und Haushalt. Ein vorheriger Slot wird erst bei abgeschlossener Bereinigung frei.

Der Standardtest prueft **nur die Anmeldung**. Zusaetzlich gibt es den separat
freizugebenden Warenkorbtest mit genau drei festen Positionen; siehe
[SHOP_CART_PILOT.md](SHOP_CART_PILOT.md). Kein Test beauftragt eine Bestellung,
Kontoerstellung oder Aenderung von Kontoeinstellungen. Der angemeldete Warenkorb
und die Sichtbarkeit auf dem persoenlichen Geraet brauchen weiterhin eine reale
Abnahme, sie sind noch kein nachgewiesener Erfolg. Die temporaere Browsersitzung wird nach
dem Test geloescht; dauerhafte Cookies werden nicht gespeichert.

## Konfiguration auf Railway

| Variable | Ort | Inhalt |
| --- | --- | --- |
| `GALAXUS_HOUSEHOLD_ID` | Webdienst; Referenz im Worker | Tatsaechliche interne ID eures Haushalts aus der Datenbank |
| `GALAXUS_EMAIL` | Nur Worker, versiegelt setzen | E-Mail des bestehenden gemeinsamen Shopkontos |
| `GALAXUS_PASSWORD` | Nur Worker, versiegelt setzen | Passwort dieses Kontos |
| `SHOP_LOGIN_PILOT_ENABLED` | Webdienst; Referenz im Worker | Zunaechst `0`, erst nach Betriebspruefung `1` |
| `OPENAI_API_KEY` | Bestehende geschuetzte Konfiguration | Unveraendert weiterverwenden, im Worker referenzieren |

Keine echten Werte in Chat, Git, Kommandoausgaben oder PR schreiben. E-Mail und
Passwort direkt in Railways Variables-Oberflaeche eintragen. Der Webdienst
benoetigt diese beiden Geheimnisse nicht. Fehlende Zugangsdaten verhindern eine
neue API-Sitzung im Worker. Eine fehlende/falsche Haushaltsbindung verhindert das
Vormerken im Web und die Ausfuehrung. Es gibt keinen geratenen Standardhaushalt.
Das ist bewusst eine Installation fuer **einen** Haushalt, keine allgemeine
Mehrhaushalts-Kontoverwaltung.

## Ablauf und Umgang mit Geheimnissen

Die Person bestaetigt einen einmaligen kostenpflichtigen Anmeldetest sowie die
Nutzung des hinterlegten Haushaltskontos im OpenAI-gehosteten Shopbrowser. Erst
ein CSRF-geschuetzter POST reiht den Auftrag ein. Ein GET startet keinen Browser;
dieselbe Anfragekennung erzeugt keinen zweiten Auftrag. Kein hartes Geldlimit
wird versprochen. Nach sechs Minuten werden Abbruch und Bereinigung angefordert;
bei Dienst-/Netzausfall kann sich das verzoegern.

Der beaufsichtigte Worker uebernimmt genau einen Auftrag atomar. Er verwendet
Zugangsdaten ausschliesslich in registrierten `browser_authentication`-
Kontrollereignissen, nie in Modellanweisungen oder Chatnachrichten. Vor dem
Senden wird die aktuelle API-Anforderung erneut gelesen und Identitaet,
Haushaltsbindung, Sitzung, Zustand und Fristen werden erneut geprueft. Das
Anmeldeziel muss exakt `https://www.galaxus.ch` oder der verifizierte
Galaxus-Identity-Origin `https://id.digitecgalaxus.ch` sein. Andere SSO-/Login-Origins
stoppen den Pilot und brauchen zuerst eine verifizierte Anpassung.

Nur eindeutig erkannte E-Mail-/Benutzername- und Passwortfelder werden befuellt.
Getrennte E-Mail- und Passwortschritte sind moeglich. Jedes dieser Felder wird
hoechstens einmal pro Browsersitzung automatisch uebermittelt. Mehrdeutige
Methoden, unbekannte Felder und MFA-/Einmalcodes bleiben manuelle Anforderungen
auf der privaten Statusseite. Es wird kein SMS-Code automatisch beschafft oder
MFA-Geheimnis hinterlegt. Die Person aktualisiert die Seite selbst und gibt den
geforderten Schritt ein. Keine Eingaben werden vorausgefuellt oder wiederholt.
Nach einer unklaren Uebermittlung wird abgebrochen und bereinigt.

`ShopLogin` speichert nur Auftrag, Person, Haushalt, Auth-Version,
API-Sitzungs-/Anforderungsreferenzen, Fristen, Kostenfreigabe und Zustand. Keine
Passwoerter, Codes, Cookies, Modelltexte oder Bilder. Zusaetzlich werden
ausschliesslich feste technische Ergebniskategorien, ein gueltiger HTTP-Fehlercode,
die Anzahl beobachteter Browseraktionen und der Anmeldeschritt gespeichert.
Diese Angaben bleiben nach der Sitzungsbereinigung erhalten. Freie API- oder
Exceptiontexte werden weder gespeichert noch ausgegeben. Private Seiten verwenden
`Cache-Control: no-store`. Authentifizierte Seiten und POSTs werden nicht vom
Service Worker gecacht. Andere Haushaltsmitglieder sehen keine fremden
Anmeldeformulare. Abmelden, Rechteentzug und Fristablauf loesen Abbruch aus.

Eine angenommene Eingabe oder ein abgeschlossener API-Turn beweist keinen Login.
Echte Anmeldung, MFA und Warenkorbuebergabe muessen am Konto separat abgenommen
werden. Der Browser kann nach dem Login persoenliche Kontodaten sehen.

## Betrieb und Kosten

Der zusaetzliche Railway-Dienst laeuft mit einer Replik ohne oeffentliche Domain:

```bash
flask --app james shop-login-worker --watch
```

Er prueft die Datenbankqueue etwa alle 30 Sekunden, bearbeitet einen Test und
bereinigt abgebrochene, unklare oder abgelaufene Sitzungen. Er erzeugt im Leerlauf
keine OpenAI-Sitzungen, verbraucht aber Railway-RAM und etwas CPU. Die tatsaechlichen
Infrastrukturkosten werden nach Bereitstellung anhand der Messwerte beurteilt;
OpenAI-Kosten entstehen separat bei einem bewusst gestarteten Test.

Nach Neustart wird eine begonnene Sitzung nicht erneut erstellt. Bei unbekanntem
Erstellungsausgang erfolgt Abgleich anhand der eindeutigen Auftrags-UUID in den
letzten 100 API-Sitzungen. Nicht auffindbare oder aeltere Faelle bleiben
`cleanup_pending` und brauchen Betreiberpruefung. Cancellation und Loeschung
sind getrennte Aufrufe; fehlgeschlagene Bereinigung wird erneut versucht. Bei
laufendem Test oder Worker-Ausfall kann sie verzoegert sein. Kein garantiertes
Geldlimit. Einmaliger manueller Abgleich:

```bash
flask --app james shop-login-cleanup
```

## Bereitstellung und Abnahme

`deployment/shop-login-worker.json` dokumentiert die Bereitstellungsreferenz.
Webdienst und Worker sind im Runtimebranch `feat/household-shopping` aktiv.
Die folgenden Schritte beschreiben die urspruengliche kontrollierte Einrichtung.

1. Tests und Migration pruefen. Migration lehnt bereits vorhandene parallele
   offene Auftraege eines Haushalts ab, statt einen still zu verwerfen.
2. Code/Schema zunaechst bei deaktiviertem Pilot bereitstellen. Den beaufsichtigten
   Worker mit einer Replik einrichten; Haushalt-ID pruefen und setzen.
3. Die beiden Shop-Geheimnisse direkt und nur im Worker hinterlegen. Leere Queue,
   Neustart und Bereinigung ohne neue kostenpflichtige API-Sitzung pruefen.
4. Kontrolliert aktivieren. Ein neuer bezahlter Test startet erst nach bewusster
   Bestaetigung in James. Die fruehere Einzelgenehmigung ist verbraucht.
5. Echte Kontoanmeldung, MFA, Abbruch und Smartphone pruefen. Anschliessend den
   angemeldeten Drei-Produkte-Warenkorb und die geraeteuebergreifende Sichtbarkeit
   implementieren und abnehmen. Weiterhin kein Bestellabschluss.

## Diagnose des ersten Kontotests

Die urspruengliche Implementierung speicherte nur den Bereinigungszustand und
verwarf das technische Ergebnis nach dem Lauf. `closed` bedeutet lediglich,
dass keine offene Browsersitzung mehr zu bereinigen ist, nicht dass der Login
erfolgreich war. Aus dem ersten Lauf kann deshalb nachtraeglich kein genauer
Fehlergrund oder Login-Erfolg rekonstruiert werden. Die Workerlogs bestaetigen
nur den Abschluss, ohne Ursache. Keine Vermutung ueber falsche Zugangsdaten
oder eine Shop-Sperre als Nachweis ausgeben.

Die Korrektur trennt Ergebnis und Bereinigung. Die PWA zeigt kuenftig u.a.
Browserabschluss ohne Loginbeweis, API-Fehler, Verbindungsabbruch, Zeitablauf,
fehlende Konfiguration oder lokale Ablehnung an. Registrierte Anmeldung,
Uebermittlung, manueller Schritt und abweichendes Anmeldeziel werden als feste
Stufen erfasst. Ein alter oder unterbrochener Lauf ohne Ergebnis bleibt
ausdruecklich unbekannt. Kein automatischer neuer Test, keine Wiederholung
von Zugangsdaten und keine Aufweichung der Origin-Grenze. Ein neuer bezahlter
Anmeldeversuch braucht erneut die ausdrueckliche Bestaetigung in der PWA.

## Abschluss ohne Anmeldeanforderung (2026-11-03)

Der naechste vom Nutzer gestartete Lauf endete regulaer nach fuenf beobachteten
Browseraktionen, ohne registrierte Anmeldeanforderung und ohne HTTP-Fehler.
Damit wurden die hinterlegten Zugangsdaten nicht ueber diesen Mechanismus
uebermittelt. Es ist nicht nachgewiesen, ob eine Shop-Sperre, eine nicht gefundene
Maske oder ein nicht angeforderter Authentifizierungsschritt den Abschluss
ausloeste. Keine dieser Vermutungen als feststehende Ursache ausgeben.

Der Auftrag nennt jetzt konkrete Schritte: Hauptagent oeffnet die Galaxus-Seite,
wechselt ueber sichtbare Kontosteuerung zur bestehenden Anmeldung und fordert
selbst die registrierte Browserauthentifizierung an. Er wird informiert, dass
die Anwendung die Zugangsdaten bereits haelt. Keine Delegation dieses Schritts,
kein Anfordern von Geheimnissen im Chat und keine Eingabe erfundener Werte.
Die offizielle Anleitung bestaetigt, dass nur der Hauptagent Browseranmeldungen
anfordern kann:
https://developers.openai.com/api/docs/guides/agents-api/tools/computer-use

Ohne registrierte Anmeldeanforderung wird ein normaler Turnabschluss kuenftig als
`no_authentication` gespeichert. Auch schon vorhandene `turn_completed`-Datensaetze
ohne Anmeldeschritt werden in der PWA ausdruecklich entsprechend erklaert.

Der Agent darf genau einen festen Abschlusscode melden (Zugriff blockiert,
Maske nicht gefunden, Authentifizierung nicht verfuegbar, Methode nicht
unterstuetzt, angemeldete Ansicht, nicht angemeldet, unbekannt). Nur ein exakt
passender Token aus dem beendeten Hauptturn wird angenommen; fremde Turns,
freier Text und unbekannte Werte werden verworfen, widerspruechliche Tokens
werden zu `unknown`. Bestehende beobachtete Anmeldeschritte werden durch eine
solche Behauptung nicht ueberschrieben. Die PWA bezeichnet die Meldung explizit
als ungepruefte Agentenmeldung, niemals als unabhaengigen Erfolgsnachweis. Es
werden weiterhin keine privaten Texte, Passwoerter, Codes oder Screenshots
gespeichert. Kein neuer kostenpflichtiger Test wurde durch die Anpassung gestartet.

Eine tatsaechlich durch die Anwendung abgelehnte zusaetzliche Browser-Origin
wird separat als fester Marker erfasst, ohne Hostname oder URL zu speichern.
Dieser beobachtete Zugriffsstopp hat Vorrang vor einer Agentenvermutung ueber
eine Shop-Sperre. Dieser Diagnosemarker erweitert selbst keine Origin-Grenze.

### Verifizierter offizieller Login-Einstieg

Die offizielle Galaxus-Hilfe https://www.galaxus.ch/de/guide/52 verlinkt ihren
normalen Anmeldeprozess auf https://www.galaxus.ch/auth/v1/login. Beim Folgen
dieses oeffentlichen Links am 2026-11-03 wurde ein Redirect auf den Origin
`https://id.digitecgalaxus.ch` beobachtet. Der bisherige Pilot erlaubte nur
`www.galaxus.ch` und haette diese Weiterleitung abgelehnt. Das ist eine konkrete
Integrationsluecke, aber kein nachtraeglicher Beweis fuer den genauen Abschlussgrund
des bereits geloeschten Browserlaufs. Keine OAuth-Queryparameter aufbewahren.

Der Loginpilot startet jetzt am offiziellen Einstieg und erlaubt zusaetzlich
ausschliesslich diesen exakt verifizierten Identity-Origin fuer Browserzugriff
und registrierte Credential-Uebermittlung. Keine Subdomain-Wildcards, keine
andere Ports und keine automatische Freigabe weiterer Redirects. Der allgemeine
Browser-/Gastwarenkorb-Probe bleibt ohne ausdrueckliche Zusatzkonfiguration auf
seinen bisherigen Einzel-Origin beschraenkt. Lookalikes werden abgelehnt.
Die Sicherheits- und Kostenfreigaben, Haushaltsbindung und MFA-Pause bleiben
bestehen. Diese Anpassung erfordert keine neue Datenbankmigration.
