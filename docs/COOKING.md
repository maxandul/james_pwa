# Kochen

Die gemeinsame Rezeptsammlung gehört zum aktiven Haushalt. Alle aktiven Mitglieder können Rezepte erfassen, bearbeiten, favorisieren, mit datierten Notizen ergänzen und löschen. Zutaten und Notizen werden mit einem gelöschten Rezept entfernt; Haushaltsartikel und offener Einkaufsbedarf bleiben erhalten.

## Alltag ohne Mengenbuchhaltung

Rezeptmengen sind positive Dezimalzahlen (höchstens drei Nachkommastellen). Die Portionsauswahl skaliert die Anzeige, nicht den Haushaltsbestand oder die Nachkaufmenge. «Direkt kochbar» bedeutet, dass alle Zutaten dem Status nach vorhanden sind. Die tatsächlich ausreichende Menge muss vor dem Kochen geprüft werden. Knapp/unbekannt ergibt «Bestand prüfen», aufgebraucht ergibt «Zutaten fehlen». Archivierte Artikel gelten als zu prüfen.

Jede Zutat ist mit einem Haushaltsartikel verbunden. Automatische Zuordnung akzeptiert nur einen eindeutigen, Unicode-normalisierten Namen. Bei mehreren Treffern ist eine explizite Auswahl erforderlich. Neue Namen erzeugen einen Artikel mit unbekanntem Bestand, üblicher Nachkaufmenge 1 und den bestehenden Standardfeldern. Artikelzuordnungen werden bei jedem Speichern gegen den aktiven Haushalt geprüft. Als Grundvorrat markierte Rezeptzutaten mit unbekanntem Bestand werden als vorhanden angenommen; «knapp», «aufgebraucht» und Archivierung haben Vorrang.

## Einkauf und Bestandskorrektur

Fehlende Zutaten werden in der Rezeptansicht zum Einkauf vorausgewählt. Knappe/unbekannte Vorräte können nach Prüfung ausgewählt werden. Die Übernahme verwendet die übliche Nachkaufmenge des Artikels, erhält bestehenden offenen Bedarf und verändert keinen Bestandsstatus. Mehrfach vorkommende Zutaten werden pro Artikel einmal behandelt. Die Einkaufsliste zeigt Rezepttitel, gewählte Portionenzahl und benötigte Rezeptmengen als Orientierung. Mehrere Rezepte werden als Hinweise geführt; ohne exakte Vorratsmengen kann keine ausreichende Gesamtpackungsmenge berechnet werden.

Ein Kauf setzt wie bisher den Artikel auf vorhanden. Ist die offene Menge erledigt oder entfernt, werden die Rezepthinweise gelöscht; eine zulässige Activity-Rücknahme stellt sie wieder her. Die optionale Nach-dem-Kochen-Auswahl korrigiert ausschliesslich explizit ausgewählte Bestandszustände. Es gibt keinen automatischen Verbrauch und keine Gramm-/Stückbuchhaltung.

Listen- und Bestandsaktionen verwenden Haushalts-/Artikelsperren, ursprüngliche Versionsnummern, Activity-Historie und eine transaktionale UUID-Wiederholungssperre pro Formular. Geänderte Auswahl mit wiederverwendeter UUID ergibt Konflikt. Ein veralteter Artikel bricht die gesamte Übernahme ab. POSTs werden nicht automatisch wiederholt.

## Verwaltung, Fotos und Grenzen

Unter App-Verwaltung → Rezeptkategorien können Eigentümer Kategorien ergänzen, umbenennen, über Positionszahlen sortieren, deaktivieren und unbenutzte Kategorien löschen. Bestehende Rezepte dürfen ihre deaktivierte Kategorie behalten. Mindestens eine Kategorie bleibt erhalten. Startwerte sind Vorspeisen, Gerichte, Desserts, Snacks und Drinks.

Fotos: maximal 4 MB/20 Megapixel, mit Pillow eingelesen, orientiert, auf maximal 1400 × 1400 Pixel verkleinert und als JPEG ohne ursprüngliche Metadaten gespeichert. Auslieferung nur nach Haushaltsprüfung, ohne Cache. Rezepte sind online verfügbar; keine privaten Rezeptdaten im Service-Worker-Cache.

Web-/Foto-Rezeptimport, Wochenplanung und JayJay-Ersatzvorschläge sind spätere Erweiterungen. Die aktuelle Umsetzung ruft dafür keine KI auf und verändert weder KI-Zugangsdaten noch Shop-Testabläufe.

Validierung: Integrationstests für Bestand/Grundvorräte, Skalierung, Zuordnung, Einkauf, Teilkauf, Historie/Rücknahme, UUID-Wiederholung, konkurrierende Versionen, Haushaltsisolation, Rollen, CSRF, Bilder und Kategorien. Browserprüfung der gerenderten Ansichten mit Beispieldaten; Formularaktionen separat über Flask getestet.
