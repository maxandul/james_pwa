# UI der ersten Version

Stand: 01.11.2026. Serverseitige Jinja-Templates, ein lokales Stylesheet und gezieltes JavaScript. Noch kein Service Worker und kein Installationsmanifest.

## Gestaltung

Warmer Papierhintergrund, dunkles Gruen fuer Hauptaktionen, ruhige Karten, klar erkennbare Bestandszustaende. Systemschrift ohne externe Ressourcen. Responsive Raster mit drei, zwei oder einer Artikelkarte pro Reihe. Touch-Aktionen mindestens 44 Pixel, sichtbare Fokusmarkierung und beschriftete Eingabefelder.

## Component Registry

| Klassen | Verwendung |
| --- | --- |
| header, brand, identity | Logo, persoenlicher Zugang und Abmelden |
| nav | Hauptnavigation mit aria-current |
| main, page-heading, section-heading | Inhaltsbreite und Seitenhierarchie |
| panel, form-panel, auth-panel | Eingabe- und Verwaltungsbereiche |
| auth-layout, auth-intro, illustration | Anmeldeseite und rein dekorative Beispiele |
| button, button--primary, button--outline, button--quiet, button--listed, button--full | Hauptaktion, Nebenaktion, Linkaktion, bereits erfasster Bedarf |
| form, form-grid, form-actions | Beschriftete Felder und Formularabschluss |
| summary, summary__label, summary__arrow | Einstieg in den gemeinsamen Einkauf |
| item-grid, item-card, item-card__top, item-card__category, item-card__actions, item-icon | Haushaltsartikel mit Nachkaufaktionen |
| pill und pill--unknown/available/low/empty | Rollen bzw. Bestand mit Text, nicht nur Farbe |
| shopping-group, shopping-list, shopping-row, shopping-row__name, purchase-form, quantity, extra | Einkauf nach Warengruppen, Teilmengen und Zusatzbedarf |
| filters, filter, filter--active | Bezugsquellenfilter |
| notice, notice--error, undo, undo__details, undo__label, undo__hint | Statusmeldung, Fehler und hervorgehobene letzte eigene Aenderung mit erklaerter Ruecknahme |
| empty, empty__symbol, count | Leere Ansichten und Mengenhinweise |
| two-columns, member-list, invitations | Haushalt und Einladungen |
| eyebrow, muted, small, sr-only, footer | Typografie und Hilfselemente |

Stylesheet und JavaScript werden mit Versionsparameter eingebunden. Bei Aenderungen beide passenden Versionswerte in base.html anheben. Authentifizierte Seiten werden nicht gecacht.

Auto-Aktualisierung nur auf Haushalt/Einkauf, alle 45 Sekunden und beim erneuten Sichtbarwerden. Keine Aktualisierung nach begonnenen Eingaben, waehrend Absenden oder bei geoeffneten Zusatzmengen. Offline-Formulare werden sichtbar blockiert; eine persistierte Offline-Liste ist noch offen.

Browserpruefung in dieser Arbeitsumgebung durch nicht erreichbaren lokalen Webserver blockiert. Desktop-/Tablet-/Handy-QA steht vor Alltagseinsatz noch aus.

## Bedienfeedback: Rueckgaengig auffindbar machen

Die erste Bedienpruefung des Users bestaetigt den Grundablauf; Rueckgaengig war nicht klar auffindbar. Deshalb bleibt auf Haushalt und Einkaufsliste eine hervorgehobene Box "Deine letzte Aenderung" mit Artikel, Aktion und Button "Rueckgaengig machen" sichtbar, auch nach Navigation, Filtern oder Neuladen. Nur die letzte eigene Listenaktion wird angeboten, solange ihre Artikelversion noch aktuell ist. Nach Ruecknahme oder Aenderung dieses Artikels durch ein anderes Mitglied verschwindet das Angebot. Kein Ausweichen auf eine aeltere Aktion.

Neue Unterklassen gliedern Beschriftung, Aktionsdetails und Erklaerung; sie begruenden die deutlichere Rueckmeldung auf Desktop und Handy. CSS-Version auf 2 angehoben. Aenderung mit Routentests fuer Navigation, Ruecknahme und gemeinsame Nutzung abgesichert; visuelle Abnahme nach Neustart der lokalen Vorschau offen.
