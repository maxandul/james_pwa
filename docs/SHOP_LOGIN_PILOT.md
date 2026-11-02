# Shop-Anmeldung: lokaler Pilot und anschliessende PWA-Einbindung

Stand 02.11.2026. Der echte Agents-API-Gastwarenkorb mit drei Positionen ist
nachgewiesen. Nun folgt die Kontoanmeldung; ein echter Login wurde in dieser
Etappe noch nicht gestartet. Die vorherige Kostenfreigabe galt genau fuer den
bereits abgeschlossenen Warenkorbtest und ist nicht wiederverwendbar.

## Implementierte Anmeldeschicht

`scripts/shop_auth_portal.py` stellt eine kurzlebige lokale Eingabemaske bereit.
Sie laeuft ausschliesslich auf `127.0.0.1` mit zufaelligem Port und privatem,
unguessbarem Link. Sie ist fuer den vertrauenswuerdigen Rechner der Person
gedacht, die sich anmeldet. Kein oeffentliches Hosting, kein Tunnel, kein
Zugriff ueber das lokale Netzwerk. Keine Integration in die produktive PWA.

Der Pilot zeigt nur eine vom API-Browser registrierte Authentifizierungsanforderung
fuer exakt `https://www.galaxus.ch`. Unbekannte Login-Origins, einschliesslich
externer SSO-Anbieter, werden angehalten. Fehlende oder geaenderte Anforderungen
werden vor jeder Uebermittlung erneut bei der API geprueft. Die Person waehlt
eine angebotene Anmeldemethode, bestaetigt das angezeigte Ziel und gibt die
dafuer benoetigten Werte in maskierte Felder ein. Weitere Anforderungen,
etwa fuer einen Verifizierungscode, werden als neue Anforderung behandelt.

Die Eingaben werden direkt als
`agent.session.input.computer_use_approval_request_result` mit
`response.type=browser_authentication` uebertragen. Das sind Anmeldedaten fuer
den OpenAI-gehosteten Browser; sie werden an OpenAI uebermittelt und dort zum
Ausfuellen des registrierten Shopformulars verwendet. Sie sind keine
Chatnachricht. Das ist keine Zusicherung, dass der Browser nach der Anmeldung
keine persoenlichen Kontodaten auf den besuchten Seiten sehen kann.

## Schutz und Grenzen

- Kein Speichern der Eingaben in James-Datenbank, Flask-Session, Dateien oder
  eigenen Access-Logs. Keine Rohfehler oder eingegebenen Werte in Antworten.
- Exakter Host und Origin, eigener CSRF-Token, private URL, keine externen
  Ressourcen, no-store, kein Framing, keine Referrer-Weitergabe.
- Felder werden aus dem frisch gelesenen Schema erzeugt; Pflichtfelder,
  unbekannte/mehrfach uebermittelte Felder und fremde Methoden werden geprueft.
- Pro Anforderung nur eine Uebermittlung. Bei unklarer Netzwerkantwort ist
  die Anforderung lokal geschlossen; kein automatischer zweiter Loginversuch.
- Die Maske wartet maximal 120 Sekunden pro Anforderung. Der gesamte
  Operatorlauf hat das bekannte 360-Sekunden-Beobachtungs-/Cancellation-Budget.
- Im Loginmodus zeichnet der Runner weder Modelltexte noch Screenshotdateien
  der privaten Sitzung auf. Er erlaubt keine Sitzungsaufbewahrung.
- Bei einem Fehler wird Cancellation angefordert; ausstehende Bereinigung
  wird ausgewiesen. Weder Cancellation noch Loeschung sind bei Netzfehlern
  garantiert sofort wirksam. Kein garantiertes Geldlimit.
- Der lokale Browser/Passwortmanager steht unter Kontrolle der Person. Der
  Pilot sendet kein Kommando zum Speichern von Passwoertern oder Zahlungsdaten.

## Betreiberkommando fuer einen spaeter freigegebenen lokalen Test

Erst auf dem eigenen vertrauenswuerdigen Rechner ausfuehren, nachdem der
vorhandene API-Schluessel sicher in der Prozessumgebung verfuegbar ist und
eine neue Kostenfreigabe fuer diesen Login-Test vorliegt. Keine Geheimnisse
in Chat, Repository, Befehlsargumenten oder Screenshots weitergeben.

```bash
python -m pip install -r requirements.txt -r requirements-browser.txt
python scripts/jayjay_login_pilot.py \
  --state /PFAD/AUSSERHALB/DES/REPOS/login-pilot-neu.json \
  --authorize-single-test-without-hard-cost-cap
```

Die Konsole zeigt einen lokalen privaten Link. Die Person oeffnet ihn auf
demselben Rechner und aktualisiert ihn, wenn der Agent eine Anmeldung
angefordert hat. Alle Eingaben ausschliesslich in dieser Maske. Der Agent
darf nur die bestehende Anmeldung pruefen: keine Kontoerstellung,
Warenkorbaenderung, Zahlung oder Bestellung. Eine Uebermittlungsbestaetigung
oder ein abgeschlossener API-Turn ist kein unabhaengiger Login-Nachweis.

Dieser Test ist noch nicht ausgefuehrt und die Live-Tauglichkeit der
Anmeldung ist offen. Die Sitzung wird abschliessend geloescht und ist kein
dauerhafter Zugang oder persoenlich uebergebener Warenkorb.

## Naechster Schritt fuer James auf Handy und Tablet

Das lokale Formular darf nicht einfach oeffentlich auf Railway exponiert
werden. Fuer die PWA ist eine eigene Einbindung notwendig:

1. API-Sitzung und Anforderung an die aktuell angemeldete Person, ihren
   Haushalt und ihre Auth-Version binden. Authentifizierung ist persoenlich;
   andere Haushaltsmitglieder bekommen keine Loginanforderung oder Kontodaten.
2. Nur Metadaten und Referenzen dauerhaft speichern. Eingaben ausschliesslich
   im HTTPS-POST annehmen und direkt an die erwartete API-Anforderung
   weiterreichen. Keine Uebernahme in Chat, Offline-Snapshot oder Telemetrie.
3. Serverseitige Sperren gegen doppelte Uebermittlung, aktuelle Anforderungen
   bei jedem GET/POST lesen, stale/revoked/expired sicher abbrechen. Die lokale
   Condition ist kein Ersatz fuer diese Datenbank-/Mehrworker-Koordination.
4. Sitzungsende und Bereinigung durch einen ueberwachten Worker mit
   Wiederanlauf-/Abgleichverfahren absichern. Ein Webrequest oder lokaler
   Thread allein garantiert keinen Stopp nach Serverneustart.
5. Nach erfolgreicher Anmeldung denselben Warenkorb im normalen Browser der
   Person pruefen. Erst der Test im selben Shopkonto belegt eine Uebergabe
   auf deren Geraet; ein Cart-Link allein uebertraegt keinen Gastwarenkorb.

Erst nach diesen Nachweisen ein Browserwerkzeug fuer JayJay freischalten.
Checkout und Bestellabschluss bleiben ausserhalb dieser Etappe.

## Validierung

Isolierte Tests decken Schema-/Methodenpruefung, frische API-Anforderungen,
CSRF/Origin/Host, Ablauf und Replay, Zielverwechslung, HTML-Escaping,
unklare Antworten sowie die Unterdrueckung privater Modelltexte und
Screenshotdateien ab. Kein echter Schluessel und keine echten Kontodaten
in diesen Tests. Quelle fuer die registrierte Authentifizierung:
[Offizielle Agents-API-Computer-use-Dokumentation](https://developers.openai.com/api/docs/guides/agents-api/tools/computer-use#handle-sign-in).
