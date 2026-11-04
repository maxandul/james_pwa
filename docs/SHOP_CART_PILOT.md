# Angemeldeter Drei-Produkte-Warenkorbtest

Implementierung der naechsten POC-Etappe. Noch kein echter Kontowarenkorb-Nachweis
und kein neuer kostenpflichtiger Test in dieser Entwicklungsarbeit. Der bisherige
Anmeldetest hat die registrierte Uebermittlung der Zugangsdaten nachgewiesen;
ob Galaxus sie akzeptiert hat, ist dadurch allein nicht bestaetigt.

## Freigabe und Ablauf

1. In James unter `/shop-login` **Anmelden und drei Warenkorbpositionen
   vorbereiten** waehlen. Die drei Positionen und Gesamtmengen stehen sichtbar da.
2. Warenkorbvorbereitung und einmalige API-Kosten jeweils ausdruecklich
   bestaetigen. Ohne beide Freigaben entsteht kein Cart-Auftrag. Der alte
   Anmeldetest ist weiterhin vorausgewaehlt und veraendert keinen Warenkorb.
3. Der bestehende Worker meldet sich im Haushaltskonto ueber die registrierte
   Authentifizierung an. MFA oder unbekannte Anmeldeschritte bleiben manuell
   auf der privaten Statusseite. Erst bei sichtbar angemeldetem Konto soll der
   Agent den Warenkorb bearbeiten; kein Gastwarenkorb als Kontonachweis.
4. Der Agent liest zuerst den vorhandenen Warenkorb und soll nur die drei
   freigegebenen Positionen auf ihre Gesamtziele ergaenzen. Andere Positionen
   bleiben erhalten. Hoehere vorhandene Mengen oder unerwartete parallele
   Aenderungen fuehren zum Konfliktstopp, nicht zur automatischen Reduktion.
5. Der Agent soll den Warenkorb erneut oeffnen/aktualisieren und Kennungen und
   Mengen kontrollieren. Ein unsicherer Klick wird zuerst nachgeprueft, niemals
   blind wiederholt. Exakte Varianten fehlen: stoppen, keine Ersatzprodukte.
6. Der Nutzer oeffnet anschliessend Galaxus im **selben Konto** auf dem eigenen
   Geraet und prueft die drei Artikel und Mengen. Nach abgeschlossener
   Sitzungsbereinigung kann er diese manuelle Pruefung in James bestaetigen.

| Artikelkennung | Testprodukt | Packung | Gesamtziel |
| --- | --- | --- | --- |
| 14684120 | bluu Universal Waschstreifen | 60 Waschgaenge | 2 |
| 14730798 | Barilla Spaghetti n.5 | 500 g | 1 |
| 37264242 | Cirio Pizza Sauce | 400 g | 1 |

Das sind die bereits fuer den Gast-POC verwendeten Artikel, keine behaupteten
Haushaltspraeferenzen. Preise und Verfuegbarkeit muessen im echten Browser
geprueft werden. Waehrend des Tests den gemeinsamen Warenkorb nicht parallel
bearbeiten. Bei Abbruch koennen einzelne Positionen bereits veraendert sein;
vor einem erneuten Versuch erst den aktuellen Warenkorb kontrollieren. Keine
unsichere automatische Ruecknahme oder Loeschung anderer Positionen.

## Ergebnis und Grenzen

Ein fester, erlaubter Agentenbericht (`cart_ready`, `cart_partial`,
`cart_conflict`, `product_unavailable`, `account_not_verified` oder eine
Anmeldekategorie) wird getrennt vom beobachteten Authentifizierungsschritt
aufbewahrt. Die bisherige Implementation verwarf Berichte, sobald Zugangsdaten
uebermittelt waren; dies ist damit korrigiert. Keine freien Modelltexte,
Geheimnisse, OAuth-Parameter oder privaten Bilder werden gespeichert.

`cart_ready` ohne beobachtete registrierte Credential-Uebermittlung wird nicht
uebernommen, sondern als `account_not_verified` angezeigt. Jeder Agentenbericht
bleibt **ungeprueft**. Ein normaler Turnabschluss ist kein Warenkorbnachweis.
`device_verified_at` ist ausschliesslich eine explizite, CSRF-geschuetzte manuelle
Bestaetigung durch die startende Person nach dem Ende des Tests. Sie loest keine
API-Anfrage und keine Bestellung aus und behauptet keine unabhaengige technische
Pruefung durch James. Andere Haushaltsmitglieder koennen die private Testseite
oder diese Bestaetigung nicht fuer die startende Person absenden.

Der Auftrag verbietet Checkout, Bestellen, Zahlen, Abos, Kontoaenderungen und
Kontaktaufnahmen. Die gehostete Browserumgebung ist keine selbst kontrollierte
Browser-Engine mit eigener technischer Checkout-URL-/Aktionssperre. Dieses POC
ist kein allgemein freigegebener autonomer Bestelldienst. Fuer eine spaetere
technisch garantierte Grenze vor Zahlungen braucht es entsprechende kontrollierte
Tools oder eine selbst kontrollierte Browserlaufzeit.

## Betrieb

Eine additive Migration setzt bestehende Auftraege auf `task_kind=login` und
ergaenzt nur Testart, festen Berichtscode und manuelle Pruefzeit. Keine alten
Anmeldetests werden nachtraeglich in Warenkorbtests umgewandelt. Wiederverwendung
der Anfragekennung mit anderer Testart wird abgelehnt.

Pro Haushalt und UTC-Tag maximal zwei reine Anmeldetests und **ein** separat
freigegebener Warenkorbtest. Bestehende Logintests verbrauchen den einen
Warenkorbversuch nicht. Der eindeutige aktive Haushaltsslot gilt fuer beide
Testarten gemeinsam. Kein automatischer Neuversuch nach Fehler, Neustart oder
unklarem Ausgang. Der vorhandene zwölfminütige Ablauf mit Cancellation und
Bereinigung gilt weiter; kein garantiertes hartes Geldlimit. Das Loeschen des
Browserlaufs soll einen kontogebundenen Warenkorb nicht loeschen; die reale
Geraetepruefung muss diese Annahme bestaetigen.

Keine neuen Railway-Dienste, Geheimnisse oder API-Schluessel erforderlich.
Bestehende Domainfreigaben bleiben auf www.galaxus.ch und den verifizierten
Identity-Origin id.digitecgalaxus.ch beschraenkt. Die neue Migration muss vor
der neuen Worker-Version angewandt werden; bei parallelem Auto-Deploy zuerst
Web-Migration/Readiness und dann den Workerstatus pruefen, einen vorzeitig
fehlgeschlagenen Worker-Build erst nach erfolgter Migration erneut bereitstellen.

Der Warenkorbmodus ist zusaetzlich ueber `SHOP_CART_PILOT_ENABLED=0`
standardmaessig gesperrt (Web-POST und Worker). Erst Schema/Code auf beiden
Diensten bereitstellen, dann den Worker auf `1` setzen und seinen erfolgreichen
Start pruefen; erst danach den Webdienst auf `1` setzen. Dadurch kann die neue
Testart nicht versehentlich von einer alten, noch reinen Login-Worker-Version
bearbeitet werden. Ein GET oder das Aktivieren der Flags startet keinen Test.

## Einmaliger Wiederholungsversuch nach korrigierten Zugangsdaten

Der Nutzer meldete nach dem ersten Cart-Test einen Tippfehler in der hinterlegten
E-Mail-Adresse und korrigierte die Railway-Konfiguration selbst. Die erwarteten
Variablennamen sind vorhanden und der neue Worker-Deploy erreichte SUCCESS;
die Werte wurden nicht ausgelesen. Der alte Test wird nicht erneut ausgefuehrt.

`SHOP_CART_EXTRA_ATTEMPT_DATE=YYYY-MM-DD` kann auf dem Webdienst fuer genau einen
UTC-Tag gesetzt werden. Nur bei exakter Uebereinstimmung mit dem aktuellen
UTC-Datum erhoeht sich das Cart-Tageskontingent von eins auf **maximal zwei**.
Vergangene, zukuenftige, fehlende oder ungueltige Werte belassen es bei eins.
Die Ausnahme laeuft durch den Datumsvergleich automatisch ab, ohne Scheduler.
Keine Aenderung am Login-Kontingent, parallelen Haushaltsslot, API-Zeitbudget
oder an bestehenden Protokollen. Ein weiterer Test braucht weiterhin eine neue
Anfragekennung sowie eigene Warenkorb- und Kostenfreigaben in James. Keine
API-Sitzung durch eine Konfigurationsaenderung oder einen GET. Die Seite zeigt
das heute geltende Kontingent und die Ausnahme ausdruecklich an.

## Mehrstufige Anmeldung und Diagnose

Die Zugangsdatenübergabe ist ein Zwischenschritt. Der Browserauftrag muss danach
sichtbare Weiter-/Anmelden-Schaltflächen bedienen, weitere Passwort- oder
Bestätigungsschritte anfordern und die Rückleitung in den Shop abwarten. Erst
nach einer sichtbar angemeldeten Kontoansicht beginnt die Warenkorbvorbereitung.

- E-Mail und Passwort werden getrennt als übermittelt erfasst. Bei beiden lautet
  der Status `both_submitted`; keiner dieser Status ist ein Loginbeweis.
- Nach einer E-Mail-Stufe darf die erste Passwort-Stufe die E-Mail nochmals
  enthalten. Eine wiederholte Passwortübergabe oder eine reine Wiederholung der
  E-Mail wird weiterhin an die Person übergeben. Unklarer Versand wird nicht
  wiederholt.
- Der private Statusendpunkt liefert nur Zustand und feste Fortschrittskategorie.
  Die Warteseite lädt bei einer Zustandsänderung neu, aber niemals nach einer
  Eingabe oder während eines Formular-Submits. Manuelle Formulare werden nicht
  automatisch neu geladen.
- Feste Agentenberichte unterscheiden abgelehnte Anmeldung, ausstehende manuelle
  Bestätigung, unvollständigen Login und ausstehende Rückleitung. Sie bleiben als
  ungeprüfte Agentenmeldung gekennzeichnet. Rollen der übermittelten Felder und
  manuelle Kategorien stehen zusätzlich als feste Marker im Worker-Log;
  Feldwerte, freie Feldbeschriftungen und private Screenshots werden nicht geloggt.

Automatisierte Tests prüfen die getrennte und die kombinierte zweite Login-Stufe,
Datenschutz und Haushaltsgrenzen des Statusendpunkts sowie unveränderte
Wiederholungs- und Warenkorbgrenzen. Ein erfolgreicher Test mit dem echten Shop
und die Prüfung desselben Kontowarenkorbs auf einem zweiten Gerät bleiben die
Abnahme. Lokale Tests beweisen keine Shop-Anmeldung.

## Ausbau zu JayJays Shop-Agenten

Die bestehende Trennung bleibt: JayJay klärt Einkauf und Produktvarianten; ein
Shop-Auftrag führt den begrenzten Browserablauf aus. Ein neuer Shop benötigt
seine eigenen geprüften Anmeldeziele, Produktkennungen und Fähigkeitsnachweise.
Der aktuelle Galaxus-Pilot ist noch kein universeller Bestellagent.

Nächste Abnahmen: (1) angemeldeter Galaxus-Warenkorb mit den festen Zielmengen,
(2) Übergabe geprüfter Positionen aus einem Einkaufsvorhaben, (3) weitere Shops.
Ein verbindlicher Bestellabschluss ist eine spätere getrennte Funktion mit
konkreter Bestellfreigabe und Prüfung des Bestellergebnisses; er wird durch diese
Login-Korrektur nicht aktiviert. Gastwarenkorb, vorbereiteter Kontowarenkorb und
bestätigte Bestellung bleiben unterschiedliche Ergebnisse.

## Zeitbudget und Abbruchursache

Neue, ausdrücklich gestartete Tests haben ein Gesamtbudget von zwölf Minuten
ab Absenden des Startformulars, einschliesslich Warteschlange und Browseraufbau.
Die Oberfläche nennt diese Frist vor der Kostenfreigabe. Bestehende Laufzeiten
werden nicht verlängert. Der Browser-Timer erhält nur die verbleibende Frist;
manuelle Schritte bleiben auf höchstens zwei Minuten innerhalb der Gesamtfrist
begrenzt. Ein Zeitbudget ist weiterhin kein garantiertes Geldlimit.

Der Watchdog protokolliert eine feste Abbruchkategorie ohne private Daten.
Ein nach Fristablauf abgebrochener Turn wird als `expired` ausgewiesen, statt
lediglich als allgemeiner Fehler. Eine manuelle Stornierung bleibt als solche
sichtbar. Die Änderung beweist noch keinen erfolgreichen Shop-Login.
