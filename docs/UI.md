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
| notice, notice--error, undo | Statusmeldung, Fehler und Ruecknahme |
| empty, empty__symbol, count | Leere Ansichten und Mengenhinweise |
| two-columns, member-list, invitations | Haushalt und Einladungen |
| eyebrow, muted, small, sr-only, footer | Typografie und Hilfselemente |

Stylesheet und JavaScript werden mit Versionsparameter eingebunden. Bei Aenderungen beide passenden Versionswerte in base.html anheben. Authentifizierte Seiten werden nicht gecacht.

Auto-Aktualisierung nur auf Haushalt/Einkauf, alle 45 Sekunden und beim erneuten Sichtbarwerden. Keine Aktualisierung nach begonnenen Eingaben, waehrend Absenden oder bei geoeffneten Zusatzmengen. Offline-Formulare werden sichtbar blockiert; eine persistierte Offline-Liste ist noch offen.

Browserpruefung in dieser Arbeitsumgebung durch nicht erreichbaren lokalen Webserver blockiert. Desktop-/Tablet-/Handy-QA steht vor Alltagseinsatz noch aus.

## Primaere Geraete und weitere Arbeit

Tablet und Handy sind die primaeren Oberflaechen; Desktop ist ergaenzend. Die weitere Artikelverwaltung und alle neuen Ablaeufe werden zuerst fuer Touch und kleine bzw. wechselnde Viewports gestaltet.

Der User nutzt ein Fold-Handy (als Z8 Fold bezeichnet). Keine festen Modellmasse angenommen: entscheidend sind die tatsaechlichen CSS-Viewportgroessen auf Aussen- und Innendisplay. Vor Abnahme beide Displays in Hoch-/Querformat sowie Auf-/Zuklappen waehrend eines begonnenen Formulars pruefen. Eingaben und Einkaufsstatus muessen dabei erhalten bleiben. Karten, Formulare, Navigation und Aktionen muessen sich ohne abgeschnittene Inhalte anpassen; Kernaktionen duerfen keinen Hover voraussetzen.

Die dauerhafte Box fuer die letzte Aenderung wurde auf Wunsch des Users zurueckgenommen. Rueckgaengig erscheint wieder nur im direkten Hinweis nach einer Listenaktion; beim normalen Oeffnen oder Wechseln der Seite wird keine permanente Box angeboten. CSS-Version nach der Ruecknahme: 3.

## Artikelpflege fuer Touch

- Gemeinsam gesetzte Favoriten ueber einen sichtbaren Stern mit aria-pressed; Ansicht Favoriten fuer den schnellen Kuechenzugriff.
- Ansicht Archiv mit Wieder-aktivieren-Aktion; keine endgueltige Loeschfunktion.
- Bearbeiten-Link auf jeder aktiven Karte. Im Bearbeitungsformular Name, Warengruppe, Quelle, Nachkaufmenge, Einheit, Bestand und Favorit.
- Bestand direkt auf der Karte unter "Bestand und Artikeldetails" setzen. Ein kurzer Hinweis trennt diese Korrektur vom Nachkaufen.
- "Von der Liste entfernen" auf jeder Einkaufsposition; Ruecknahme im gewohnten direkten Aktionshinweis.
- Suche nach Artikelname; Such- und Favoritenansicht bleibt nach Kartenaktionen erhalten.

| Neue Klassen | Zweck |
| --- | --- |
| item-search | Umbruchfaehige Suche mit beschriftetem Suchfeld |
| favorite-button | 44-Pixel-Touchziel fuer gemeinsamen Favoritenstatus |
| item-card__manage, status-form | Touch-erreichbare Bestandskorrektur, ohne Hover |
| item-edit-link | Sichtbarer Einstieg in die Artikelpflege |
| check-field | Beschriftete Favoriten-Checkbox mit grosser Zielflaeche |
| archive-section | Erklaerung und Aktion zum Archivieren |
| remove-form | Sichtbare Listenentfernung unter der Einkaufsposition |

Karten und Formularspalten nutzen auto-fit/minmax mit Mindestbreite innerhalb des verfuegbaren Platzes. Suche und Aktionszeilen brechen um; Eingabefelder auf kleinen Viewports haben 16 Pixel Schrift. Keine festen Modellmasse oder Aenderung der Eingaben beim Aufklappen. Visuelle Abnahme auf Aussen-/Innendisplay bleibt ein eigener Geraetetest. CSS- und JS-Referenzversion fuer dieses Paket: 4.
