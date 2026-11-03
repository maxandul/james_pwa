# Fachliches Datenmodell

Stand: 01.11.2026. Zielmodell mit folgendem implementierten Ausschnitt; initiale Alembic-Migration liegt separat vor.

## Kernobjekte

| Objekt | Wesentliche Daten und Beziehung |
| --- | --- |
| Household | Gemeinsamer Haushalt; fachliche Daten sind immer einem Haushalt zugeordnet |
| User | Persoenliche Identitaet; das konkrete Auth-Verfahren ist offen |
| Membership | User zu Household, aktiv/inaktiv; spaeter Bestellberechtigung |
| DeviceAccess | Widerrufbarer Tablet-Zugang mit eingeschraenkten Rechten und eigener Quellenkennung |
| HouseholdItem | Haushaltsartikel: Name, Kategorie, Favorit, Bestandsmodus, Nachkaufmenge/-einheit, bevorzugte Bezugsquelle |
| Product | Konkrete Variante: Marke, Name, Packungsmenge und Einheit; optional Bild |
| ProductBarcode | Barcode als Zeichenfolge zu Product; fuehrende Nullen bleiben erhalten |
| ItemProduct | Zuordnung erlaubter Produkte zum Haushaltsartikel, inklusive bevorzugter Variante |
| PurchaseSource | Bezugsquelle: Online-Shop oder Laden |
| ShopOffer | Product zu PurchaseSource mit Shop-Artikelkennung, URL und optionalem Preis-/Verfuegbarkeits-Snapshot samt Abrufzeit |
| StockState | Aktueller Bestandsstand je HouseholdItem: Modus, bekannt/unbekannt, einfacher Status oder Menge, Aenderungszeit |
| StockMovement | Bestaetigter Verbrauch, Einkauf, Wareneingang oder Korrektur; Menge oder Statuswechsel, Quelle und Ruecknahmebezug |
| ShoppingNeed | Einkaufsbedarf: Artikel oder Freitext, gewuenschte Menge/Einheit, Bezugsquelle, offen/erfuellt/storniert |
| Activity | Fachliche Aenderung mit User oder DeviceAccess, Zeitpunkt und Request-Kennung |

Product und Barcode-Zuordnungen bleiben in der ersten Version ebenfalls innerhalb des Haushalts. Ein gemeinsamer oeffentlicher Katalog ist nicht erforderlich.

## Objekte fuer Einkaufsvorhaben und Shop-Ausbau

| Objekt | Zweck |
| --- | --- |
| Purchase | Einkaufsvorhaben bei einer Bezugsquelle; Art Laden/online, Status, spaeter Shop-Referenz und Bestaetigungsquelle |
| PurchaseLine | Geplantes konkretes Produkt oder Freitext mit Menge und Einheit; Produktdaten als Snapshot |
| NeedAllocation | Verbindet eine Bedarfsteilmenge mit einer PurchaseLine; verhindert doppelte Einplanung |
| Receipt | Ein bestaetigter Einkauf/Wareneingang mit eindeutiger Buchungskennung |
| ReceiptLine | Tatsaechliche Menge und Produkt; Verweis auf PurchaseLine, soweit vorhanden |
| ShopTransferAttempt | Spaeter: Uebergabeversuch und Ergebnis pro Position; keine Zugangsdaten in fachlichen Logs |

Diese Objekte werden erst im jeweiligen Umsetzungspaket eingefuehrt. Die erste Listenansicht benoetigt noch keinen vollstaendigen Bestellprozess.

## Bestand und Einheiten

- Im einfachen Modus ist die Menge leer. Status: vorhanden, knapp, leer oder unbekannt.
- Im Mengenmodus ist eine bekannte nichtnegative Dezimalmenge mit definierter Einheit gespeichert. Unbekannt ist nicht gleich null.
- Mengen werden als Dezimalwerte modelliert, nicht als ungenaue binaere Gleitkommazahlen.
- Bestandseinheit und Bestelleinheit sind getrennt: zwei bestellte Packungen koennen je 500 g enthalten.
- Zunaechst nur explizite Zuordnungen und kompatible Einheiten; keine stillen Annahmen fuer "1 Packung".
- Eine Packung mit 500 g und eine mit 1 kg sind verschiedene Product-Varianten.
- Einkaufsbedarf ist unabhaengig vom Bestand: Auch ein vorhandener Artikel kann zusaetzlich benoetigt werden.

## Zustandsmodell fuer Online-Einkaeufe

| Status | Bedeutung |
| --- | --- |
| draft | Einkaufsvorschlag, noch kein Shop-Auftrag |
| prepared | Warenkorb vorbereitet; keine verbindliche Bestellung bestaetigt |
| ordered | Bestellung bestaetigt; Quelle manuell oder Shop-Nachweis gespeichert |
| outcome_unknown | Ergebnis eines Absendeversuchs unklar; kein automatischer Neuversuch |
| partially_received | Ein Teil wurde als angekommen gebucht |
| received | Alle erwarteten Mengen abgeschlossen |
| cancelled | Vorhaben bzw. offene Restmengen beendet |

Fehler einer Warenkorbuebergabe gehoeren in den Uebergabeversuch und setzen nicht automatisch die ganze Bestellung auf "bestellt" oder "storniert".

## Integritaetsregeln

1. Alle Beziehungen und Zugriffspruefungen muessen Haushaltsgrenzen erhalten.
2. Ein einfacher Nachkauf-Aufruf wird innerhalb einer Transaktion zusammengefuehrt. Wiederholte Requests nutzen dieselbe Idempotenzkennung.
3. "Nachkaufen" setzt den offenen Zielbedarf; "Zusaetzliche Menge" erhoeht ihn ausdruecklich.
4. Zugeordnete Bedarfsmengen duerfen den verfuegbaren offenen Bedarf nicht ueberschreiten. Freitextpositionen brauchen keine kuenstliche Produktzuordnung.
5. Kauf/Wareneingang, Bestand und Bedarf werden gemeinsam verbucht. ReceiptLine und StockMovement verhindern doppelte Buchungen.
6. Rueckgaengig erstellt eine nachvollziehbare Gegenbuchung und korrigiert die Bedarfsdeckung.
7. Mengen- und Statusaenderungen verwenden Versionspruefung oder geeignete Datenbanksperren, damit parallele Eingaben nicht verloren gehen.
8. Produktpreis und Lieferbarkeit sind zeitgebundene Snapshots. Beim Bestellen erneut pruefen.
9. Zugangsdaten, Auth-Token und Shop-Sitzungen gehoeren nicht in fachliche Objekte oder Logs.
10. Ein Standardbarcode identifiziert weder die individuelle Packung noch ihr Verbrauchsdatum. Chargen und Haltbarkeit sind ein spaeterer Ausbau.

## Spaetere Objekte

Recipe, RecipeIngredient, MealPlan und MealPlanEntry sowie optionale Chargen/Verbrauchsdaten und Verbrauchsschaetzungen. Beobachteter Bestand, schaetzungsbasierte Hinweise und Rezeptannahmen muessen unterscheidbar bleiben.

## Implementierter Ausschnitt

Household, User, Membership, Invitation, LoginThrottle, HouseholdItem, ShoppingNeed und Activity. Membership.user_id ist aktuell eindeutig: ein Haushalt pro Person. Invitation enthaelt ausschliesslich den Hash des Tokens, Empfaengeradresse, Ablauf, Widerruf, Verbrauch und Aussteller.

StockState ist vorerst als stock_status im HouseholdItem integriert. ShoppingNeed ist pro Artikel eindeutig und bleibt mit Menge null als erledigter Bedarf bestehen. Nachkauf- und Bedarfsmenge sind in dieser ersten Stufe positive ganze Packungen/Stuecke (offener Bedarf auch null), kein vorgetaeuschter Mengenbestand.

Activity speichert die Listenaktionen mit vorherigem/nachherigem Bestandsstatus und Bedarf, Item-Version, Urheber und eindeutiger Request-UUID pro Haushalt. Eine Ruecknahme verweist auf die Gegenbuchung. Receipt/StockMovement sind noch nicht eingefuehrt, da kein mengenbasierter Bestand oder Lieferprozess existiert.

Quelle und Warengruppe sind zunaechst Texte am Artikel. ItemProduct, PurchaseSource, ShopOffer, DeviceAccess und alle Bestellobjekte bleiben im Zielmodell. Vor deren Einfuehrung sind eigene Migrationen erforderlich.

## Erweiterung Artikelpflege

HouseholdItem besitzt is_favorite und archived (Boolean, nicht null, Default false auch fuer vorhandene Zeilen). Favoriten werden innerhalb des Haushalts geteilt. Archivierte Artikel erscheinen weder im aktiven Haushalt noch auf der Einkaufsliste und koennen wieder aktiviert werden. Offener Bedarf verhindert das Archivieren.

Activity speichert nun zusaetzlich Name, Warengruppe, Quelle, Einheit, Standard-Nachkaufmenge, Favoriten- und Archivstatus. Vorhandene alte Snapshots mit nur status/quantity werden bei Ruecknahme weiter unterstuetzt. Keine Historie wird geloescht.

Migration eebb352b7301 folgt auf e691ea9e9398 und wird getrennt vom Feature-Code committet. Sie ergaenzt die beiden Flags mit portablem SQL-false; bestehende Artikel und ihre Bedarfe bleiben erhalten. Downgrade entfernt ausschliesslich die neuen Flags und benoetigt fuer SQLite native DROP-COLUMN-Unterstuetzung ab 3.35. Produktive Migrationen weiterhin erst mit Backup und passender Betriebsfreigabe.

## Implementierte Barcode-Zuordnung

Product speichert household_id, item_id, Name, Marke, freie Packungsangabe und data_source (manual/openfoodfacts/openfoodfacts_staging). Ein Produkt gehoert aktuell genau zu einem Artikel; mehrere Produktvarianten pro Artikel sind moeglich. ItemProduct als allgemeine Mehrfachzuordnung bleibt spaeterer Ausbau. Packungsangabe ist keine automatische Einheitenumrechnung.

ProductBarcode speichert household_id, product_id, urspruenglichen code und kanonischen gtin (14 Stellen). Unique(household_id, gtin) verhindert doppelte Zuordnung, auch bei aequivalenten UPC-/EAN-Schreibweisen. Zuordnung und Suche pruefen alle Haushaltsbeziehungen im Service. Ein Scan eines archivierten Artikels fordert zuerst zur Wiederaktivierung auf.

CatalogCache speichert nur oeffentliche Katalogantworten mit Schluessel Umgebung:GTIN und expires_at. CatalogGate speichert je Umgebung next_allowed_at zur workeruebergreifenden Abrufbegrenzung. Keine privaten Haushaltsdaten in diesen beiden Tabellen.

Revision b8cf5f8bfc8c folgt auf eebb352b7301 und erstellt diese vier Tabellen in einem separaten Migrationscommit. Vorhandene Artikel, Bedarfe und Historie bleiben erhalten. Downgrade entfernt die Produktzuordnungen und Katalogdaten; kein Anwender-Schritt.


## Implementierte Kategorien, Einkaufsorte und Angebote

Revision 4b4e6934c1ee folgt auf b8cf5f8bfc8c (eigener Migrationscommit):

| Tabelle/Feld | Bedeutung |
| --- | --- |
| Category | Haushalts-Warengruppe: Name, normalisierter name_key, aliases, version |
| PurchaseSource | Haushalts-Einkaufsort mit denselben Namens-/Versionsregeln |
| ItemSource | Mehrfachzuordnung Artikel/Einkaufsort, zusammengesetzter Primaerschluessel |
| ShopOffer | Produkt/Einkaufsort eindeutig; HTTPS-Link, Shop-Artikelnummer, units_per_pack, preferred, active, version |
| Product.version | Optimistische Konflikterkennung bei Bearbeitung einer Variante |

ShopOffer.units_per_pack ist Numeric(12,3), >0 und <=999999. Household-/Produkt-/Quellenzugehoerigkeit wird serverseitig geprueft. Keine Aussage ueber aktuelle Verfuegbarkeit. Ein Produkt kann mehrere ShopOffer besitzen, ein Artikel mehrere Produkte. ProductBarcode bleibt unveraendert.

Backfill erzeugt je vorhandenem Haushalt Standardoptionen plus bestehende individuelle Namen und verknuepft den bisherigen Einkaufsort. Gross-/Kleinschreibvarianten ergeben einen Eintrag. Artikeltext, Versionen, Bestand, Bedarf, Barcodes und Activity bleiben erhalten. Alte Activity-Snapshots sind kompatibel; neue enthalten source_ids. Aktive Angebotsorte bleiben auch bei Ruecknahme erhalten.

Downgrade entfernt ausschliesslich die neuen Tabellen und Product.version, also neue Zuordnungen/Katalognamen. Artikel, Produkte und Barcodes bleiben erhalten. Kein Anwender-Reparaturschritt; vor Live-Migration Backup erstellen und Restore pruefen.


## Implementierte Einkaufsvorhaben

Revision d6e2f6837481 erstellt PurchasePlan: Haushalt, Einkaufsort (FK), eindeutige request_id je Haushalt, versionierter Status draft/ordered/closed/cancelled, optionale manuelle Bestellreferenz und JSON-Zeilensnapshots. Zeilen enthalten item_id, Namen/Einheit, urspruengliche quantity, verbleibende reserved-Menge sowie Produktname, expliziten Packungsinhalt und HTTPS-Link. JSON-Referenzen werden serverseitig gegen Haushalt und aktuelle Artikel-/Produkt-/Angebotsversionen geprueft. Keine separaten Order-/Lieferobjekte und keine Shop-Sitzungen.

Aktive Vorhaben reservieren zusammen hoechstens den aktuellen offenen Bedarf; Haushaltssperre serialisiert Erstellung und Artikelaktionen. Eine Kauf-/Entfernen-Aktion begrenzt Reservierungen auf verbleibenden Bedarf. Freigaben werden beim Rueckgaengigmachen nicht automatisch reaktiviert. Version des Vorhabens erhoeht sich auch bei solchen Mengenanpassungen. Alte Produkt-/Packungssnapshots werden nicht nachtraeglich umgerechnet. Bestellung ist eine ausdrueckliche manuelle Statusbestaetigung, keine behauptete Shop-Antwort.
