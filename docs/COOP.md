# Coop-Verbindung und eindeutige Produktvorbereitung

Stand: 05.11.2026. Erste Etappe: gespeicherte Anmeldung, genaue Zuordnung und
schreibgeschützte Testvorschau. Kein Coop-Warenkorb-Agent und kein Checkout.
Der Nutzer hat den bestehenden Galaxus-Test mit den richtigen Gesamtmengen
unabhängig im echten Kontowarenkorb bestätigt. Dieser Ablauf bleibt erhalten.

## Nutzung

1. Unter **Mehr → Coop verbinden** den Browser ausdrücklich öffnen. Dort selbst
   anmelden, in James das sichtbare richtige Konto bestätigen und **Speichern
   und schliessen** wählen. Danach erneut öffnen und dasselbe Konto prüfen.
   Die manuelle Anmeldung bei Coop wurde mit dieser Codeänderung noch nicht live geprüft.
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

Die automatische Warenkorbübertragung ist die nächste Etappe. Preis,
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

Migration: `c28a60b4e915`. Web zuerst bis zum neuen Head migrieren, danach Worker
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
festen drei Produkte bleiben unverändert. Coop lehnt den bisherigen Cart-Aufruf
in Route und Worker ab, damit der Galaxus-Agent keinen falschen Shop übernimmt.
Die Vorschau ist ausschliesslich GET und startet keine Browser- oder API-Läufe.

Tests prüfen Profiltrennung, Wiederverwendung des richtigen Kontextes,
unveränderten Galaxus-Ablauf, CSRF/Haushaltsgrenzen, Identitätsänderungen,
Packungsrundung, alte Vorhaben und Migration mit vorhandenen Daten. Ein Downgrade
mit vorhandenen Coop-Profilen wird vor Änderungen abgewiesen; Profile werden
nicht zur Rückkehr auf ein altes Schema automatisch gelöscht.

Offene Live-Abnahmen: (1) manuelle Coop-Anmeldung und Wiederöffnung,
(2) zwei bis drei vom Nutzer gewählte Produkte zuordnen,
(3) Vorschau prüfen. Erst danach den eigenen Coop-Warenkorb-Agenten ergänzen.
