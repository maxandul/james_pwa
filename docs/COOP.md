# Coop-Verbindung und eindeutige Produktvorbereitung

Stand: 10.11.2026. Gespeicherte Anmeldung, genaue Zuordnung und begrenzter
Coop-Warenkorbtest für höchstens drei Produkte. Kein Checkout.
Der Nutzer hat den bestehenden Galaxus-Test mit den richtigen Gesamtmengen
unabhängig im echten Kontowarenkorb bestätigt. Dieser Ablauf bleibt erhalten.

## Nutzung

1. Unter **Mehr → Coop verbinden** den Browser ausdrücklich öffnen. Dort selbst
   anmelden, in James das sichtbare richtige Konto bestätigen und **Speichern
   und schliessen** wählen. Danach erneut öffnen und dasselbe Konto prüfen.
   Der Nutzer hat Anmeldung und Wiederöffnung mit erhaltener Anmeldung am 10.11.2026 bestätigt.
2. Unter **App-Verwaltung → Einkaufsorte** ist der vorhandene Einkaufsort Coop
   mit dem technischen Shop `coop` verbunden. Eigene oder umbenannte Einkaufsorte
   lassen sich dort ausdrücklich verbinden; je Haushalt nur einer pro Shop.
3. Beim Haushaltsartikel **Produkte und Einkaufsorte** öffnen. Ein konkretes
   Produkt mit genauer Variante im Namen und genauer Packungsangabe hinterlegen.
   Zum Coop-Angebot den HTTPS-Produktlink, die identische Artikelnummer und die
   ausdrücklich geprüfte Packungsumrechnung speichern. Die Checkbox bestätigt,
   dass die Person genau dieses Produkt und diese Packung geprüft hat.
   Dies ist keine automatische Live-Prüfung des Sortiments.
4. Artikel auf die Einkaufsliste setzen und über **Coop-Einkauf vorbereiten**
   ein Vorhaben mit höchstens drei Positionen erstellen. Im Vorhaben
   **Coop-Testvorschau prüfen** öffnen. Angezeigt werden Artikel, Produkt,
   Packung, Shop-ID, Gesamtziel in Shop-Packungen und allfällige Mehrmenge.
5. Fehlende, mehrdeutige, geänderte oder unbestätigte Zuordnungen blockieren
   die vollständige Freigabereife. Bei Änderungen ein altes Vorhaben verwerfen
   und neu erstellen, damit es keine Mengen weiter reserviert. Alte Vorhaben
   ohne vollständigen Produktsnapshot werden nicht automatisch aufgewertet.

Die Testvorschau bietet einen ausdrücklichen Start des Warenkorbtests. Preis,
Verfügbarkeit, Liefergebiet und bereits vorhandene Warenkorbmengen werden
dabei im echten Shop geprüft. Es gibt keine stillen Ersatzprodukte oder
Packungswechsel. JayJay wird später dieselben Fachfunktionen aufrufen.

## Bestehendes Modell, gezielte Erweiterung

- `HouseholdItem` und `ShoppingNeed` bleiben Artikel und gemeinsamer Bedarf.
- `Product` bleibt die konkrete Variante mit Marke und `package_text`.
- `ShopOffer` bleibt die Zuordnung mit `shop_sku`, URL und `units_per_pack`.
  Neu: Bestätigungszeit und Fingerabdruck der genauen Identität. Produktversion,
  Name, Marke, Packung, ID, Link, Umrechnung, Einheit und Shop-Zuordnung fliessen
  ein. Eine spätere Änderung macht die Bestätigung unwirksam. Eine URL muss auf
  `https://www.coop.ch/<Sprache>/.../p/<Artikelnummer>` zeigen und zur ID passen;
  Zusatzparameter/Fragmente müssen entfernt werden. Keine URL wird serverseitig
  automatisch aufgerufen. Doppelte aktive IDs können nicht neu bestätigt werden.
- `PurchaseSource.shop_key` ist unabhängig vom frei bearbeitbaren Anzeigenamen.
  Eine Änderung löst bestehende Bestätigungen. Zusammenführen unterschiedlich
  verbundener Einkaufsorte ist gesperrt, damit Shop-IDs nicht umgedeutet werden.
- `PurchasePlan.lines` bewahrt den genauen Produktstand einschliesslich
  Versionen, Shop-ID, Variante, Packung und Umrechnung. Die Vorschau prüft ihn
  erneut gegen aktive Zuordnungen. Veränderte reservierte Mengen werden nicht
  still in neue Warenkorbziele übersetzt.
- `ShopBrowser` bewahrt einen eigenen Browserbase-Kontext je Haushalt und Shop.
  Bestehende Profile werden als Galaxus erhalten, mit derselben Kontextreferenz,
  Ergebnismeldung und Version. Die Migration startet keinen Browser.

## Betrieb und Abnahme

Migration: `d39b71c5fa26`. Web zuerst bis zum neuen Head migrieren, danach Worker
auf denselben Code bringen. Der vorhandene Worker wartet auf passende
Schema-Readiness. Eine laufende manuelle Browsersitzung vor dem Rollout speichern
und schliessen. Kein neuer Dienst, kein neues Shop-Passwort und kein neuer
OpenAI-Schlüssel erforderlich. `SHOP_BROWSER_ENABLED=1` gilt weiterhin.

`SHOP_BROWSER_HOUSEHOLD_ID` ist eine optionale shopneutrale Haushaltsbindung.
Fehlt sie, gilt die bestehende `GALAXUS_HOUSEHOLD_ID` auch für die manuell
gespeicherten Shop-Browser. Der alte API-Anmeldepilot bleibt Galaxus-spezifisch.
Private Kontrolle bleibt auf den aktiven Haushaltseigentümer und dessen
Anmeldung begrenzt. Profile sind gleichzeitig speicherbar; offen ist höchstens
ein Browser pro Haushalt. Erstellungs- oder Bereinigungsfehler sperren weitere
Starts bis zur Klärung. Löschen einer Coop-Verbindung löscht nicht das Galaxus-Profil.

Der Worker öffnet für Coop `https://www.coop.ch/de/`; die Person durchläuft den
Shop-Login manuell in der bestehenden Live-Ansicht. Der Galaxus-Agent und seine
festen drei Produkte bleiben unverändert. Coop verwendet einen eigenen Driver
mit geprüften Produkt- und Bedienelementkennungen. Der alte feste Galaxus-Cart-
Aufruf bleibt für Coop gesperrt. Ein GET auf die Vorschau startet nichts;
ein bestätigter POST reiht genau ein Vorhaben ein.

Tests prüfen Profiltrennung, Wiederverwendung des richtigen Kontextes,
unveränderten Galaxus-Ablauf, CSRF/Haushaltsgrenzen, Identitätsänderungen,
Packungsrundung, alte Vorhaben und Migration mit vorhandenen Daten. Ein Downgrade
mit vorhandenen Coop-Profilen wird vor Änderungen abgewiesen; Profile werden
nicht zur Rückkehr auf ein altes Schema automatisch gelöscht.

## Einmaliger delegierter Test vom 10.11.2026

Der Nutzer bestätigte die erhaltene Anmeldung und überliess die Produktauswahl
ausdrücklich dem Agenten. Gewählt wurden zwei Packungen Barilla Spaghetti No. 5
(500 g, ID 3032108), eine Packung Prix Garantie Tomaten gehackt (400 g,
ID 6492579) und eine Packung JuraSel Tafelsalz mit Jod (500 g, ID 3020051).
Die Produktseiten wurden öffentlich geprüft; persönliche Haushaltspräferenzen
werden daraus nicht abgeleitet. Artikel tragen das Präfix `[Coop-Test …]`.

`flask --app james coop-cart-pilot --request-id <UUID> --authorize-test --queue`
erstellt Testartikel, Product/ShopOffer und ein normales PurchasePlan über die
bestehenden Fachfunktionen. Die stabile Anfragekennung verhindert jeden erneuten
Start desselben Tests, auch nach Fehlern oder späteren Aufträgen. Ohne `--queue`
wird nur vorbereitet; ohne ausdrückliche Autorisierung wird nichts erstellt.
Bestehende Produktzuordnungen werden nicht überschrieben.

PurchasePlan bewahrt Auftragszustand, Startzeit und Klickzahl. ShopBrowser
referenziert das verwendete Vorhaben. Der Worker schliesst zunächst eine offene
manuelle Coop-Sitzung mit Speicherung, öffnet dann denselben Kontext für den
einmaligen Auftrag. Ein Claim wird nie automatisch wiederholt. Gesamtlaufzeit
einschliesslich Warteschlange höchstens zwölf Minuten, bis zu 40 Modellschritte.
Ein Neustart nach Claim führt zu INTERRUPTED/CREATION_UNKNOWN. Providerfehler
beenden den Plan ebenfalls; ein Fehler löscht keine gespeicherte Anmeldung.

Der Driver erlaubt nur Hauptprodukt-Adds mit passender Artikelnummer,
ID-Suche und begrenzte Navigation. Empfehlungen, fremde Produkte,
Mengeneditoren, Checkout, Bestellung und Zahlung sind nicht freigegeben.
Vor jeder Aktion werden aktuelle Zuordnung und Vorhaben erneut geprüft.
CART_READY bleibt eine Agentenmeldung; die unabhängige Kontrolle desselben
Kontowarenkorbs durch den Nutzer steht nach dem Test noch an.
