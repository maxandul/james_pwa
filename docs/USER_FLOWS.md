# Bedienablaeufe

Stand: 01.11.2026. Soll-Ablaeufe mit erstem implementierten Ausschnitt. Text-Erfassung, persoenliche Einladungen, Nachkaufen, Zusatz-/Teilkauf und Ruecknahme sind umgesetzt. Barcode, Mengenbestand, Shop-Bestellung, Lieferung, Offline-Lesen, Geraetezugang und Menueplanung sind noch offen.

## Oberflaechen

| Bereich | Zweck |
| --- | --- |
| Start | Favoriten und Aktionen "Wird knapp", "Ist leer", "Hinzufuegen / Scannen", "Einkauf angekommen" |
| Einkauf | Gemeinsame Liste, Shop-/Ladenfilter, Warengruppen und Einkaufsstatus |
| Haushalt | Artikel, Produkte, Bestandsmodus und Nachkaufregeln |
| Kochen | Spaeter Rezepte, Vorschlaege und Menueplan |

Grosse Touch-Flaechen und kurze Wege am Tablet; gut lesbare Checkboxen auf dem Handy. Alltagsmeldungen brauchen keinen Verwaltungsdialog.

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
