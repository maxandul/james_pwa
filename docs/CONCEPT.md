# Produktkonzept

Stand: 01.11.2026. Dieses Dokument beschreibt das Zielbild; es ist kein Implementierungsnachweis.

## Ausgangslage und Ziel

James soll wiederkehrende Einkaeufe vereinfachen: Bedarf entsteht beim Verbrauch, wird sofort erfasst und anschliessend gemeinsam im Laden oder online erledigt. Ein Kuechentablet dient als leicht erreichbare Eingabe; Handys dienen auch unterwegs als Einkaufsliste.

Erfolg bedeutet: weniger vergessene Artikel, weniger doppelte Einkaeufe und wenig Pflegeaufwand. Eine vollstaendige Erstinventur ist optional.

## Status der Entscheidungen

| Thema | Status |
| --- | --- |
| Eigene Haushalts-PWA mit gemeinsamem Datenbestand | Im Gespraech vereinbarte Richtung |
| Persoenliche Handy-Zugaenge und gemeinsames Kuechentablet | Bestandteil des akzeptierten Konzepts |
| Einfache und mengenbasierte Bestandsfuehrung | Bestandteil des akzeptierten Konzepts |
| Postgres und Railway | Gewuenschte technische Richtung |
| Flask | Technischer Vorschlag; urspruenglich als Option genannt |
| ChatGPT ueber MCP | Gewuenschte spaetere Erweiterung; konkrete Verfuegbarkeit zu pruefen |
| Woechentlicher oder manuell gestarteter Einkauf | Gewuenschtes Ziel; Tag und Zeit noch offen |
| Vollautomatische Shop-Bestellung | Langfristiger Wunsch, technisch noch offen |

Weitere technische Details sind Vorschlaege bis zur Umsetzung des jeweiligen Pakets.

## Umfang der ersten alltagstauglichen Version

- Ein gemeinsam verwalteter Haushalt, persoenliche Mitgliedschaften.
- Kuechentablet mit Haushaltsansicht fuer schnelle Eingaben.
- Artikel erfassen durch Text und Barcode; einfache Korrektur unbekannter Produkte.
- Favoriten mit Bild oder gut erkennbarem Namen.
- Bestandsmodi einfach und Menge; unbekannter Bestand ist zulaessig.
- Nachkaufmenge und bevorzugte Bezugsquelle je Artikel.
- Gemeinsame Liste, nach Shop/Laden und Warengruppe filterbar.
- Doppelte Nachkaufmeldungen erzeugen keinen doppelten Grundbedarf.
- Einkauf bestaetigen und Bestand uebernehmen; Teilmengen korrigieren.
- Nachvollziehbare, rueckgaengig zu machende Alltagsaenderungen.
- Synchronisation zwischen Geraeten; gespeicherte Liste ohne Empfang lesbar.

Offline-Aenderungen mit automatischem Abgleich folgen als eigenes Paket. Bis dahin zeigt die App deutlich, wenn Eingaben mangels Verbindung nicht gespeichert werden koennen.

## Bestandsfuehrung

| Modus | Verwendung | Verhalten |
| --- | --- | --- |
| Einfach | Waschmittel, Pflege, viele Lebensmittel | Vorhanden / knapp / leer / unbekannt; keine erfundene Stueckzahl |
| Menge | Ungeoeffnete Packungen oder zaehlbare Artikel | Menge mit definierter Einheit; Korrektur oder unbekannter Stand moeglich |

Im einfachen Modus erzeugt eine wiederholte Meldung "Nachkaufen" einen gemeinsamen Bedarf mit der hinterlegten Einkaufsmenge. "Zusaetzliche Menge" ist eine eigene Aktion.

Im Mengenmodus gilt zunaechst die Packung oder das Stueck als Einheit. Teilverbrauch in Gramm und automatische Umrechnung zwischen unterschiedlichen Packungen sind Erweiterungen.

## Artikel, Produkte und Bezugsquellen

"Spaghetti" ist ein Haushaltsartikel. "Barilla Spaghetti No. 5, 500 g" ist ein konkretes Produkt. Ein Angebot bei Coop verbindet dieses Produkt mit Shop-Artikelnummer und URL.

Standardprodukte koennen einmal ausgewaehlt und wiederverwendet werden. Lose Ware oder spontane Bedarfe brauchen kein konkretes Produkt. Ein einmal zugeordneter Barcode soll anschliessend ohne neue externe Suche funktionieren.

## Einkaufen und Bestellen

Alle Bedarfe erscheinen gemeinsam. Filter teilen die Liste fuer Coop, Galaxus oder Ladeneinkauf auf, ohne getrennte Kopien anzulegen. Ein Bedarf darf nicht gleichzeitig in mehreren aktiven Einkaufsvorhaben vollstaendig eingeplant werden.

Zunaechst werden Bestellvorschlaege manuell vorbereitet. Spaeter erstellt ein Serverauftrag woechentlich einen Vorschlag. Preis, Packungsvariante, Lieferbarkeit, Versand und Ersatzprodukte muessen vor einer verbindlichen Bestellung geprueft werden.

Das Kuechentablet kann Bedarf erfassen und Vorschlaege vorbereiten. Kostenpflichtige Bestellungen erfordern einen persoenlich berechtigten Zugang. Bestellberechtigungen werden im passenden Paket konkretisiert.

## Spaetere Erweiterungen

- Warenkorb automatisch befuellen, soweit pro Shop nachgewiesen.
- Woechentliche Vorschlaege und persoenliche Benachrichtigungen.
- Spracheingabe, Verpackungsfotos und Belegimport mit bestaetigbaren Vorschlaegen.
- Rezepte, Menueplan und fehlende Zutaten auf der Liste.
- Verbrauchsschaetzungen; Vorschlaege bleiben von beobachtetem Bestand unterscheidbar.
- Automatischer Bestellabschluss fuer ausgewaehlte Artikel nach separater Machbarkeitspruefung.

Menuevorschlaege sollen frische Artikel bevorzugen und unsichere Bestaende kenntlich machen. Eine allgemeine Fotoerkennung darf keine exakte Produkterkennung oder Haltbarkeit vortaeuschen.

## Noch zu klaeren

Vor dem jeweils betroffenen Paket: Tablet und Betriebssystem, Login-Verfahren, Einladungsweg fuer weitere Mitglieder, Standard-Bestandsmodus, Bestellberechtigte, bevorzugte Shops und Ersatzregeln. Vor Regelbetrieb zudem Backup/Restore und Benachrichtigungskanal festlegen.
