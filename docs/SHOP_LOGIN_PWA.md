# Gemeinsames Galaxus-Konto im PWA-Anmeldepilot

Implementiert, noch nicht auf Railway bereitgestellt oder aktiviert. Kein neuer
kostenpflichtiger API-Test in dieser Etappe. Der einmalig genehmigte
Gastwarenkorbtest bleibt der bisherige Live-Nachweis.

## Ziel und aktueller Umfang

Ein bestehendes Galaxus-Konto gehoert zum Haushalt. Berechtigte Mitglieder
koennen einen Test starten; der zugehoerige Auftrag und manuelle Anmeldeschritte
bleiben nur fuer die startende Person sichtbar. Pro Haushalt darf genau ein
Auftrag offen sein, auch bei unklarer Bereinigung. Die Datenbank erzwingt dies
mit einem eindeutigen aktiven Haushaltsslot. Hoechstens zwei Tests pro UTC-Tag
und Haushalt. Ein vorheriger Slot wird erst bei abgeschlossener Bereinigung frei.

Dieser Pilot testet **nur die Anmeldung**. Er erstellt keine Konten, aendert
keine Einstellungen oder Warenkoerbe und bestellt nicht. Angemeldeter Warenkorb
und Sichtbarkeit auf dem persoenlichen Geraet sind die anschliessende Abnahme,
kein bereits implementierter Nachweis. Die temporaere Browsersitzung wird nach
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
Anmeldeziel muss exakt `https://www.galaxus.ch` sein. Andere SSO-/Login-Origins
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
Passwoerter, Codes, Cookies, Modelltexte oder Bilder. Private Seiten verwenden
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

`deployment/shop-login-worker.json` ist die vorbereitete Referenz, nicht bereits
angewandte Konfiguration. Webdienst, Datenbank und Railway wurden nicht veraendert.

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
