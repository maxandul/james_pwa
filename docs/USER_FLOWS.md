# Bedienablaeufe

Stand: 01.11.2026. Soll-Ablaeufe mit erstem implementierten Ausschnitt. Text-Erfassung, persoenliche Einladungen, Nachkaufen, Zusatz-/Teilkauf und Ruecknahme sind umgesetzt. Mengenbestand, Shop-Bestellung, Lieferung, Offline-Lesen, Geraetezugang und Menueplanung sind noch offen.

## Oberflaechen

| Bereich | Zweck |
| --- | --- |
| Start | Favoriten und Aktionen "Wird knapp", "Ist leer", "Hinzufuegen / Scannen", "Einkauf angekommen" |
| Einkauf | Gemeinsame Liste, Shop-/Ladenfilter, Warengruppen und Einkaufsstatus |
| Haushalt | Artikel, Produkte, Bestandsmodus und Nachkaufregeln |
| Kochen | Spaeter Rezepte, Vorschlaege und Menueplan |

Tablet und Handy sind die primaeren Geraete. Grosse Touch-Flaechen und kurze Wege am Tablet; gut lesbare Checkboxen auf dem Handy. Beim Fold-Handy Aussen-/Innendisplay, Orientierung und Groessenwechsel im laufenden Ablauf pruefen. Alltagsmeldungen brauchen keinen Verwaltungsdialog.

## 1. Letzte Reserve angebrochen

1. Person tippt einen Favoriten an und waehlt "Nachkaufen".
2. James legt die Standard-Nachkaufmenge als offenen Bedarf an oder verweist auf bereits offenen/geplanten Bedarf.
3. Sichtbare Rueckmeldung zeigt Artikel und Menge; Rueckgaengig ist erreichbar.
4. Eine zweite Person sieht dieselbe Position.

Wiederholtes Antippen oder ein Netzwerk-Retry darf keine weitere Position erzeugen. Eine gewuenschte Zusatzmenge wird ausdruecklich erfasst. Bei einem bereits bestellten Artikel zeigt James den Lieferstatus; neuer Bedarf bleibt bewusst hinzufuegbar.

## 2. Produkt ist leer

1. Favorit waehlen oder Barcode scannen.
2. "Leer" bestaetigt den einfachen Bestandsstatus und sorgt fuer offenen Nachkaufbedarf.
3. Im Mengenmodus wird ein Verbrauch oder eine Bestandskorrektur angeboten; kein stilles Zuruecksetzen mehrerer Reservepackungen.

Ein Scan allein veraendert keinen Bestand: Die Ansicht zeigt erkennbar, ob gerade nachgekauft, verbraucht oder eingelagert wird.

## 3. Unbekannten Artikel erfassen

1. Text eingeben oder Barcode scannen.
2. Zuerst lokale Zuordnungen suchen; eine externe Quelle kann Daten vorschlagen.
3. Unbekannt: Name erfassen, optional Foto und Packungsangabe. Externe Dienste sind keine Pflicht.
4. Bestandsmodus und Nachkaufmenge mit einfachen Vorgaben anbieten.
5. Optional ein bevorzugtes Shop-Produkt zuordnen; Zuordnung bestaetigen.

Barcode-Fehler oder eine abgelehnte Kamera-Berechtigung fuehren zur Texteingabe. Lose Ware wird direkt als Artikel erfasst. Ein freier Einkaufswunsch kann vorerst ohne Aufnahme in den dauerhaften Artikelstamm gespeichert werden.

## 4. Einkauf vorbereiten

1. Liste nach Bezugsquelle filtern.
2. Offene Bedarfe auswaehlen, Mengen und konkrete Produkte pruefen.
3. James erstellt einen Entwurf und reserviert die zugeordneten Bedarfsmengen fuer dieses Vorhaben.
4. Aenderungen anderer Personen nach Erstellung bleiben sichtbar; der Entwurf wird nicht unbemerkt ueberschrieben.

Bedarfe zusammenfassen, nicht dieselbe Menge zweimal einplanen. Nicht zugeordnete Mengen bleiben offen. Ein abgebrochener Entwurf gibt seine Zuordnungen wieder frei.

## 5. Online-Warenkorb und Bestellung

1. Berechtigte Person startet die unterstuetzte Shop-Uebergabe.
2. James zeigt, welche Positionen erfolgreich uebertragen wurden und welche fehlen.
3. Shop-Anmeldung oder eine zusaetzliche Pruefung wird bei Bedarf von der Person erledigt.
4. Produkte, Mengen, Ersatz, Versand, Liefertermin und Gesamtsumme pruefen.
5. Person schliesst im Shop ab; bestaetigte Bestellung wird in James erfasst.

Ein geoeffneter Shop-Link oder befuellter Warenkorb gilt nicht als Bestellung. In der ersten manuellen Variante kann die Person "Im Shop bestellt" samt optionaler Referenz bestaetigen; die Quelle der Bestaetigung wird gespeichert.

Bei Timeout nach einem spaeter automatisierten Absenden: Status "Ergebnis unklar", keine automatische zweite Bestellung. Erst im Shop abgleichen.

## 6. Im Laden einkaufen

1. Liste auf dem Handy oeffnen, nach Warengruppen ordnen.
2. Gekauften Artikel mit tatsaechlicher Menge abhaken.
3. Die Aktion erfuellt den Bedarf und erhoeht im Mengenmodus den Bestand; im einfachen Modus wird "vorhanden" gesetzt.
4. Andere Geraete sehen die Aenderung. Rueckgaengig korrigiert beide Buchungen.

In der ersten Version sind gespeicherte Listen offline lesbar. Schreibaktionen bleiben bei fehlender Verbindung erkennbar blockiert. Eine spaetere Offline-Warteschlange muss klar zwischen lokal vorgemerkt und serverseitig gespeichert unterscheiden.

## 7. Lieferung angekommen

1. Bestellung waehlen.
2. Standardmaessig die noch offenen Liefermengen vorschlagen.
3. Fehlende Positionen, Teilmengen und Ersatzprodukte korrigieren.
4. Wareneingang bestaetigen; Bestand und Bedarfszuordnung gemeinsam aktualisieren.

Wiederholte Bestaetigung bucht nicht doppelt. Teillieferungen bleiben offen; stornierte Restmengen koennen wieder Einkaufsbedarf werden. Ein Ersatzprodukt wird bewusst einem passenden Haushaltsartikel zugeordnet.

## 8. Kuechentablet

Ein widerrufbarer Geraetezugang bleibt im Haushaltsmodus angemeldet. Eingaben erhalten "Kuechentablet" als Quelle; ohne Personenwahl wird keine bestimmte Person als Urheber behauptet.

Der Geraetezugang darf keine Mitglieder, Shop-Zugaenge oder Bestellberechtigungen verwalten und keine kostenpflichtige Bestellung ausloesen. Die konkrete Einrichtung und Entsperrung ist vor Implementierung festzulegen.

## 9. Menueplanung und ChatGPT (spaeter)

"Plane drei Abendessen fuer zwei Personen und verwende zuerst frische Lebensmittel."

James liefert dazu beobachteten Bestand mit Zeitpunkt und Unsicherheit. Vorschlaege benennen zu pruefende Zutaten. Fehlende Zutaten werden nach Bestaetigung als Bedarf erfasst. Ein geplanter oder gekochter Menuevorschlag zieht im ersten Ausbau keine unbestaetigten Mengen automatisch ab.

## Artikelpflege (implementiert)

Auf der Karte den Stern antippen, um einen gemeinsamen Favoriten zu setzen; unter Favoriten erscheinen nur aktive markierte Artikel. Name per Suchfeld finden. Bestandsstatus ueber "Bestand und Artikeldetails" korrigieren; dies veraendert die Einkaufsliste nicht.

"Artikel bearbeiten" oeffnet das Formular fuer Name, Warengruppe, Quelle, gewohnte Nachkaufmenge, Einheit und Bestand. Die Einheit ist bei offenem Einkaufsbedarf gesperrt. Neue Standardmengen wirken erst auf kuenftigen Bedarf. Bei einer zwischenzeitlichen Aenderung verlangt James ein Neuladen, statt alte Felder ueber neuere Werte zu schreiben.

Ein Artikel ohne offenen Einkaufsbedarf kann im Bearbeitungsformular archiviert werden. Er bleibt im Archiv erhalten und kann dort wieder aktiviert werden. Noch offener Bedarf muss zuerst gekauft oder mit "Von der Liste entfernen" geloescht werden. Letzteres setzt keinen Bestand auf vorhanden und gilt nicht als Kauf.

Alle Pflegeaktionen ausser der erstmaligen Erfassung sind ueber den direkten Aktionshinweis rueckgaengig machbar, solange die Artikelversion noch aktuell ist. Keine permanente Rueckgaengig-Box.

## Implementierter Barcode-Ablauf

1. In Neuer Artikel die Hilfe Mit Barcode erfassen, im Haushalt Nachkaufen per Barcode oder in Artikel bearbeiten die Barcode-Zuordnung oeffnen. Code eintippen oder Kamera bewusst starten. EAN-8/13, UPC-A und GTIN-14 werden mit Pruefziffer validiert.
2. Bekannter Code zeigt die gespeicherte Produktvariante und den Haushaltsartikel. Erst Nachkaufen bzw. Leer und nachkaufen bucht Bedarf. Archivierte Artikel zuerst wieder aktivieren.
3. Unbekannten Code manuell erfassen: Produktname, optional Marke/Packungsangabe, bestehender Haushaltsartikel oder neuer Artikel. Speichern allein aendert weder Bestand noch Liste.
4. Optional Produktvorschlag anfordern: Nur der Barcode geht an Open Food Facts. Vorschlag pruefen; vorhandene Eingaben werden nicht ueberschrieben. Ausfall oder fehlender Treffer laesst manuelle Erfassung offen.
5. Erneutes Scannen erzeugt keine doppelten Artikel. Falsche Zuordnung unter Artikel bearbeiten entfernen und neu erfassen; Artikel und Einkaufsbedarf bleiben erhalten.

Kamera endet bei erkanntem Code, Stoppen, Navigation und Hintergrundwechsel. Keine Bilder gespeichert oder hochgeladen. Reale Geraeteabnahme unter HTTPS bleibt offen.

Die Scan-Hilfe ist kein eigener Tab. Nach Artikelanlage oder Zuordnung wird die Artikelpflege geoeffnet; nach bestaetigtem Nachkaufen der Haushalt. Abbrechen kehrt zur Ausgangsseite zurueck. Bereits bekannte Produkte werden beim Erfassen angeboten, ohne neue Artikel anzulegen. Ein Barcode, der schon zu einem anderen Artikel gehoert, wird beim Zuordnen als Konflikt gezeigt und niemals automatisch umgehaengt. Beim Abhaken eines Einkaufs bleibt Antippen der normale Weg.

## Implementiert: Installation und Offline-Lesen

Online und angemeldet wird die gesamte offene Einkaufsliste auf diesem Geraet gespeichert. Die Ansicht zeigt den Speicherzeitpunkt. Ueber den Hilfebereich oder bei Verbindungsverlust beim Oeffnen von Haushalt/Einkauf erscheint die gespeicherte Liste ohne Schreibaktionen. Bei erneutem Online-Oeffnen wird sie aktualisiert. Beim Abmelden/Kontowechsel wird die alte Kopie entfernt. Installation erfolgt ueber Browsermenue oder den angebotenen Installieren-Button. Echte Kamera- und Installationsabnahme auf Zielgeraeten bleiben offen.


## Milch bei mehreren Laeden

1. Artikel Milch einmalig erfassen, Einheit beispielsweise Liter. Bevorzugten Einkaufsort und weitere moegliche Orte waehlen. Eigene Warengruppen/Orte lassen sich hinzufuegen und umbenennen.
2. In der Artikelpflege Produkte und Einkaufsorte oeffnen. Konkrete Milchvarianten anlegen oder vorhandene Barcode-Produkte bearbeiten.
3. Variante mit Coop/Migros oder mehreren Einkaufsorten verknuepfen. Ausdruecklich angeben, wie viele Artikeleinheiten eine Shop-Packung enthaelt; Link/Artikelnummer optional. Je Laden ein Vorzugsprodukt setzen.
4. Nachkaufen erzeugt weiterhin einen gemeinsamen Bedarf. Im Filter Coop oder Migros erscheint derselbe Artikel mit der dort passenden Variante. Ohne eindeutige Auswahl fordert James zur Variantenpflege auf.
5. Beispiel: 3 Liter Bedarf, 2 Liter je Shop-Packung ergibt 2 Packungen und 1 Liter Mehrmenge. Dies ist eine Vorbereitung, keine Bestellung. Kauf weiter in Litern bestaetigen; vorhandene Kauf-/Ruecknahmeregeln gelten.

Automatische Warenkoerbe/Bestellungen, Belegimport und James-Chat sind weitere Pakete. Bestehende Coop-/Migros-App-Konten werden dadurch noch nicht angebunden.
