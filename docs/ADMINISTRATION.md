# Verwaltung und Einkaufsansichten

Stand: 03.11.2026. Die folgenden Regeln ersetzen die frühere reine Einladungs- und Katalogverwaltung.

## Bereiche und Rechte

Unter Mehr → Verwaltung liegen Mein Profil, Haushalt & Personen, Warengruppen, Einkaufsorte, Einkaufsansichten und App-Einstellungen. Mitglieder sehen nur ihr Profil und die Einkaufsansichten. Die Sekundärnavigation nutzt auf breiten Displays eine Seitenspalte, darunter ein natives Auswahlfeld; ohne JavaScript bleiben normale Navigationslinks erreichbar.

| Bereich | Mitglied | Verwaltung |
| --- | --- | --- |
| Eigenes Profil, E-Mail, Passwort, persönliche Vorgaben | Bearbeiten | Bearbeiten |
| Haushaltsname, Personen, Rollen, Einladungen | Kein Zugriff | Verwalten |
| Warengruppen und Einkaufsorte | Auswählen | Hinzufügen, umbenennen, entfernen, zusammenführen, aktivieren |
| Eigene Einkaufsansichten | Verwalten | Verwalten |
| Gemeinsame Einkaufsansichten | Anwenden | Verwalten |
| Persönliche Ansichten anderer Personen | Kein Zugriff | Kein Zugriff |
| Gemeinsame App-Vorgaben | Verwenden | Bearbeiten |

Personennamen und Rollen lassen sich gemeinsam speichern. Entfernen entzieht den Haushaltszugriff; Wiederaktivieren vergibt zunächst die Rolle Mitglied. Mindestens eine aktive Person mit aktivem Konto behält die Verwaltung. Rollen- und Zugangsänderungen invalidieren alte Sitzungen, widerrufen offene Einladungen dieser Person und brechen noch offene private Shop-Anmeldungen ab. Artikel und Historie bleiben erhalten. Konten werden nicht physisch gelöscht.

Eigene Zugangsdaten erfordern das aktuelle Passwort und unterliegen dem vorhandenen Versuchslimit. Andere Sitzungen werden abgemeldet. Passwortwerte werden nicht zurück ins Formular geschrieben. Es gibt weiterhin keine offene Registrierung und keinen automatischen E-Mail-Versand; Einladungslinks werden manuell weitergegeben. Betreiber-Wiederherstellung bleibt über die bestehende CLI möglich.

## Katalogeinträge entfernen

Unbenutzte Einträge werden endgültig gelöscht. Referenzen durch aktuelle oder archivierte Artikel, frühere Aktionen, Einkaufsansichten, zusätzliche Ortszuordnungen, Angebote und Vorhaben führen stattdessen zur Deaktivierung. Eine interne Merkliste verhindert, dass gelöschte Standardbezeichnungen beim nächsten Artikel wieder erscheinen. Explizites erneutes Hinzufügen bleibt möglich.

Mit Ersatzzuordnung werden aktuelle Artikel, zusätzliche Einkaufsorte und Ansichtsfilter/-reihenfolgen auf den aktiven Ersatz übertragen. Doppelte Ortszuordnungen werden zusammengeführt. Gleichzeitige Produktangebote desselben Produkts an beiden Orten führen zu einem erklärten Konflikt und vollständigem Rollback; sie werden nicht still überschrieben. Ein vorhandener bevorzugter Artikel am Ziel hat Vorrang. Historische Vorhaben und Aktionssnapshots werden nicht umgeschrieben. Alte Bezeichnungen bleiben über Alias-/Weiterleitungszuordnungen auflösbar, auch nach mehreren Zusammenführungen.

Deaktivierte Einträge sind bei neuen Zuordnungen nicht wählbar. Bestehende Artikel bleiben bedienbar und Rücknahmen erhalten historische Bezeichnungen. Beim Deaktivieren eines Einkaufsorts werden dessen Produktangebote deaktiviert. Wiederaktivieren eines Orts aktiviert Angebote nicht automatisch. Betroffene Artikelversionen ändern sich, damit alte Bearbeitungsformulare keine Zuordnungen zurückschreiben.

## Einkaufsansichten

Eine Ansicht verbindet einen optionalen Einkaufsort, optionale Warengruppenfilter, eine geordnete Liste stabiler Warengruppen-IDs und die Artikelsortierung A–Z, Z–A oder Favoriten zuerst. Keine Filterauswahl bedeutet alle Warengruppen. Noch nicht eingeordnete Gruppen folgen alphabetisch. Pfeiltasten und Ziehen ändern dieselbe Formularreihenfolge; die Pfeiltasten funktionieren auch auf Touchgeräten und melden die neue Position für Screenreader.

Ansichten sind persönlich oder gemeinsam. Nur die Verwaltung kann gemeinsame Ansichten ändern. Es gibt je Sichtbarkeit und Einkaufsort höchstens einen Standard; Schreibvorgänge werden über die Haushaltszeile serialisiert. Die Default-Reihenfolge beim Öffnen ohne explizite Ansicht lautet:

1. Persönlich gewählte Standardansicht im Profil.
2. Gemeinsam gewählte Standardansicht in den App-Einstellungen.
3. Persönlicher, danach gemeinsamer Standard für den gewählten Einkaufsort; ohne Ortswahl der Standard für alle Einkaufsorte.

Eine ausdrückliche Auswahl hat Vorrang. `view_id=0` deaktiviert gespeicherte Ansichten für diesen Aufruf. Beim Wechsel des Einkaufsorts wird dessen Standard ausgewertet. Inaktive Orte werden nicht automatisch als Standard verwendet. Entfernen oder Privatisieren einer gemeinsamen Ansicht bereinigt ungültig gewordene Standardverweise.

Ansichten verändern ausschliesslich die Anzeige, keine Bedarfsmengen oder Bestände. Ausgeblendete Artikel werden gezählt und können über Alle Warengruppen anzeigen wieder eingeblendet werden. Aktionen, Aktualisierungen und Rücknahmen behalten `view_id` und Einkaufsort. Die Offline-Gerätekopie enthält weiterhin die gesamte Einkaufsliste; gespeicherte Ansichtsfilter werden offline noch nicht angewendet.

## Organisation und Betrieb

`settings.py` besitzt die HTTP-Routen und Transaktionen, `administration.py` die Berechtigungs-/Änderungsregeln, `shopping_views.py` die Auswahl und Darstellung der Einkaufsansichten. Alle Zugriffe bleiben haushaltsbezogen. Schreibzugriffe sind CSRF-geschützt; Rollen werden vor administrativen Änderungen unter einer frischen Haushaltssperre erneut geprüft. Versionen schützen vor veralteten Formularen, die Haushaltssperre vor paralleler Entfernung der letzten Verwaltung und konkurrierenden Standards.

Gemeinsame Vorgaben liegen in `Household.settings`, persönliche in `User.preferences`; beide JSON-Felder werden durch Zuweisung neuer Dictionaries geändert. `ShoppingView` ist versioniert und referenziert Haushalt, optional Person und Einkaufsort. Warengruppenreihenfolge/-filter nutzen IDs. Bestehende Artikelbezeichnungen bleiben aus Kompatibilitätsgründen Textwerte.

CSS gehört in die eigene `settings`-Ebene von `static/css/settings.css`; gemeinsame Formulare und Buttons bleiben im bestehenden Komponentensystem. `settings.js` ergänzt nur die mobile Navigation und den Laufweg-Editor. Die neuen öffentlichen Styles sind in Shell-Cache v8 enthalten. Private Verwaltungsseiten und Schreibaktionen werden nicht gecacht.

Revision `5d9a21f067ce` ergänzt ausschliesslich Spalten mit kompatiblen Defaults und eine neue Tabelle. Vor Deployment: `flask --app james db upgrade`, `db current`, `db check`. Bestehende Daten werden nicht gelöscht oder umgeschrieben. Bei einer Code-Rücknahme das additive Schema stehen lassen; kein Live-Downgrade, da dieses gespeicherte Ansichten und Einstellungen entfernen würde. Der bestehende Shop-Worker kann mit dem erweiterten Schema weiterarbeiten.

Automatische Prüfungen umfassen Berechtigungen/fremde Haushalte, Sessions, letzte Verwaltung, veraltete Formulare, Kataloglebenszyklus und Historie, Zusammenführungen inklusive Konflikt-Rollback, persönliche/gemeinsame Ansichten, Standards, Reihenfolge, Filter, Aktionen und Rücknahme. Der Paralleltest der letzten Verwaltung läuft mit Postgres 18. JavaScript-Tests prüfen zugängliche Reihenfolgeänderung und Offline-Lebenszyklus. Chromium-Prüfung mit gerenderten Originaltemplates: 344, 390, 700, 820, 1024 und 1280 CSS-Pixel ohne horizontalen Seitenüberlauf; echte Android-/iOS-Tastatur, Falten im Betrieb und Installation bleiben Geräteabnahme.
