# Machbarkeit der Shop-Anbindungen

Pruefstand: 01.11.2026. Kleine explorative Stichprobe, kein Integrationstest unter Produktionsbedingungen.

## Nachweisstufen

- **Praktisch bestaetigt:** Im angegebenen Browserablauf beobachtet.
- **Dokumentiert:** Aussage eines Anbieters oder Open-Source-Projekts, nicht selbst ausgefuehrt.
- **Offen:** Kein erfolgreicher praktischer Nachweis.

## Praktische Ergebnisse

Umgebung: von dieser Arbeit gesteuerter Browser; bei beiden Shops nicht angemeldet. Kein Zugriff auf persoenliche Shop-Konten. Testartikel sind Beispiele, keine Produktpraeferenzen des Haushalts.

| Shop / Funktion | Ergebnis | Grenze |
| --- | --- | --- |
| Coop: Suche "Barilla Spaghetti" | Praktisch bestaetigt; mehrere Varianten sichtbar | Kein API-Test und kein Nachweis fuer Railway |
| Coop: Produktdetails | 500-g-Produkt mit Artikelnummer 3032108 geoeffnet; 1-kg-Variante 3033241 separat sichtbar | Shop-Artikelnummer ist nicht gleich Barcode |
| Coop: In den Warenkorb | Klick fuehrt zur Anmeldeauswahl Supercard ID / Shop Login | Warenkorb nicht erfolgreich befuellt; angemeldeter Ablauf offen |
| Galaxus: Suche "waschmittel" | Praktisch bestaetigt; Produktauswahl sichtbar | Keine Aussage zur Vollstaendigkeit des Katalogs |
| Galaxus: konkrete Variante | bluu Universal Waschstreifen, 60 Waschgaenge, Produktkennung 14684120 ausgewaehlt | Andere Packungen/Duefte besitzen andere Kennungen |
| Galaxus: Warenkorb | Eine Packung hinzugefuegt; Warenkorb mit Menge 1 und Produkt bestaetigt | Nicht angemeldete Browsersitzung, keine Uebergabe auf ein anderes Geraet |
| Galaxus: Aufraeumen | Eigener Testartikel entfernt; leerer Warenkorb bestaetigt | Keine Bestellung ausgeloest |
| Beide: Bestellung abschliessen | Offen; nicht getestet | Kein Nachweis fuer Zahlung, Liefertermin oder Bestellbestaetigung |

Preiswerte wurden im Browser angezeigt. Sie sind keine fuer spaetere Einkaeufe garantierten Angebote und werden hier nicht als dauerhafte Stammdaten dokumentiert.

Ein direkter Python-HTTP-Aufruf zur dokumentierten Coop-Suchroute scheiterte in der lokalen Arbeitsumgebung an DNS-Aufloesung. Auch Abrufe ueber das Recherchewerkzeug lieferten keinen verwertbaren Schnittstellen-Nachweis. Das ist eine Umgebungsgrenze und kein Beleg dafuer, dass Coop oder Galaxus serverseitige Anfragen generell blockieren.

## Dokumentierte Ansaetze

| Quelle | Dokumentierte Funktion | Einordnung |
| --- | --- | --- |
| [Coop MCP](https://github.com/ElianCPastor/coop-mcp) | Produktsuche, Produktdaten, Filialbezug; beobachtete interne Coop-Routen | Inoffiziell; laut README keine Bestellung, Zahlung oder Anmeldung implementiert |
| [Galaxus MCP](https://github.com/LeonardoRO/galaxus-mcp) | Suche, Produktdetails, Preis-/Verfuegbarkeitsabfragen ueber interne GraphQL-Operationen | Inoffiziell; keine dokumentierte Warenkorb-/Bestellfunktion; Operationskennungen koennen wechseln |
| [Pepesto MCP](https://github.com/pepesto-solutions/pepesto-mcp) | Zutaten Produkten zuordnen, Preisangaben, Weiterleitung; Coop wird als Shop aufgefuehrt | Nicht praktisch getestet; README trennt Produktzuordnung und Checkout |
| [Pepesto Coop-Beispiel](https://www.pepesto.com/built-with-pepesto/coop-ch/) | Anbieter beschreibt einen vorbereiteten Coop-Warenkorb ueber Weiterleitung | Anbieterangabe, keine von uns bestaetigte native Coop-Warenkorbsitzung |
| [Galaxus E-Procurement](https://www.galaxus.ch/de/page/e-procurement-bei-digitec-galaxus-weil-kurz-mal-schnell-bestellen-im-b2b-leider-oft-nicht-reicht-42525) | Offizieller B2B-Prozess mit Punchout und Bestelldokumenten | Eignung fuer privaten Haushalt nicht nachgewiesen |

Die Marketingbeschreibung einer Weiterleitung reicht nicht als Nachweis, dass ein nativer Warenkorb im persoenlichen Shop-Konto befuellt wird. Drittanbieter benoetigen einen gesonderten Test einschliesslich Kosten, Zugang und exakter Produktwahl.

Keine fremde MCP-Software wurde installiert oder ausgefuehrt. Die Tests erfolgten ueber die sichtbare Shop-Oberflaeche; das Lesen von Quelltext ist kein Funktionstest.

## Folgerung fuer James

Die erste Version kann Einkaufsliste und konkrete Produktlinks verlaesslich aus eigenen Daten bereitstellen. Browserunterstuetztes Warenkorbbefuellen ist bei Galaxus an einem Artikel praktisch belegt.

Noch nicht zugesagt werden koennen: stabiler API-Zugriff, angemeldeter Coop-Warenkorb, automatische Uebernahme auf persoenliche Geraete, dauerhafter Hintergrundbetrieb und autonomer Bestellabschluss.

## Naechste Tests und Abnahme

| Test | Erfolgskriterium |
| --- | --- |
| Angemeldeter Coop-Ablauf | Vorgegebene Artikel/Varianten und Mengen landen im richtigen Konto; keine Bestellung |
| Galaxus-Uebergabe | Im vorbereiteten Warenkorb liegen exakt die Testpositionen; Zielperson kann denselben Warenkorb im normalen Browser pruefen |
| Mehrere Positionen / Mengen | Drei explizit gewaehlte Produkte, darunter Menge 2, werden korrekt uebernommen |
| Nicht verfuegbarer Artikel | Position wird sichtbar als offen gemeldet; kein stiller Ersatz |
| Wiederholte Uebergabe | Keine unbeabsichtigte Verdopplung; vorhandene Warenkorbinhalte werden respektiert |
| Abgelaufene Sitzung | Anmeldebedarf wird erkennbar; nach Anmeldung sichere Fortsetzung ohne doppelte Positionen |
| Zielumgebung Railway | Kleine Produktabfrage und ggf. gewaehlter Browserweg aus der tatsaechlichen Zielumgebung nachgewiesen |
| Bestellnachweis | Spaeter: manuelle bzw. technische Bestaetigung eindeutig von Warenkorbstatus getrennt |
| Drittanbieter | Nur falls weiterverfolgt: Kosten und exakte Warenkorbfunktion mit Testkonto nachgewiesen |

Angemeldete Tests benoetigen eine von der Person eingerichtete Sitzung. Passwoerter, Cookies und sonstige Zugangsdaten werden nicht im Chat oder Repository hinterlegt. Checkout wird erst in einem gesondert autorisierten Test behandelt.

Pro weiterem Test Datum, Umgebung, konkrete Produkte, beobachtetes Ergebnis, Aufraeumen und Grenzen ergaenzen.


## Aktualisierung 02.11.2026: manuelle Vorbereitung

Offizielle Anbieterbeschreibungen bestaetigen geteilte Listen/Warenkoerbe, liefern aber in unserer Recherche keinen nachgewiesenen externen James-Import. Das ist keine Aussage, dass eine Integration unmoeglich ist. Angemeldeter Native-Warenkorbtest bleibt offen.

- Migros: https://support.migros.ch/hc/de/articles/32901177026194-Kann-ich-die-Produkte-auf-der-Einkaufsliste-auch-einfach-online-bestellen
- Migros geteilte Warenkoerbe: https://support.migros.ch/hc/de/articles/32900760025106-Ich-will-etwas-bestimmtes-auf-die-Einkaufsliste-setzen-und-finde-es-nicht
- Coop: https://www.coop.ch/de/ihr-online-supermarkt/einkaufsliste.html

James erhaelt deshalb zuerst speicherbare Einkaufsvorhaben mit geprueften Produkt-/Packungsvorschlaegen, vorhandenen Shoplinks und kopier-/teilbarer Textliste. Diese Funktion befuellt keinen nativen Shop-Warenkorb. Nach externem Checkout kann der Haushalt die Bestellung manuell markieren; Liefer-/Kaufbuchung erfolgt separat ueber Einkaufsliste oder Beleg. Keine Zugangsdaten, Shop-API oder Browserautomation hinzugefuegt.
