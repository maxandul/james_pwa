# UI der ersten Version

Stand: 01.11.2026. Serverseitige Jinja-Templates, ein lokales Stylesheet und gezieltes JavaScript. Installationsmanifest und Service Worker fuer eine oeffentliche Offline-Huelle sind vorhanden.

## Responsive foundation · 03.11.2026

This section supersedes the earlier layout/refresh/version descriptions below.

- Shared navigation: Haushalt / Einkauf / Mehr; bottom navigation below 1100 CSS px, side navigation when there is enough horizontal space. Fold layouts follow available CSS width rather than model names. Safe areas, visible keyboard focus, native zoom and 16px form fields remain supported.
- Default article presentation is a compact list; cards remain available through `layout=cards`. The list context (view, query, layout; shopping source) survives actions, undo and article editing. Breadcrumbs are rendered centrally by `_breadcrumbs.html`.
- `app.css?v=11` declares ordered cascade layers and imports six owned stylesheets from `static/css`: tokens, base, layout, components, pages, jayjay. Change the owning rule/responsive block; do not append competing overrides. Recurring spacing and shell dimensions use design tokens. Native tap highlight is replaced by a pressed state; `focus-visible` remains.
- `app.js?v=10` progressively enhances only list mutations and undo. POST/redirect remains the server contract and no-JS fallback. Successful responses update the list without document navigation, preserve a visible row anchor and offer contextual undo. Failures remain beside the form; writes are never automatically replayed.
- Shared `JamesPage.refresh()` replaces timer/visibility reloads and the separate JayJay list-replacement path. Generation checks discard reads that predate a mutation. Inputs that become dirty during a read prevent its application. Draft forms preserve their original version identifiers even when another action updates the same article. All draft destinations are checked before replacing anything.
- Session-only row anchors restore position after visiting article editing. No credentials or HTML snapshots are stored by this feature.
- Public offline shell v6 precaches the CSS imports as well as app.css; authenticated pages and writes are still excluded.

Validation: Python regression tests plus DOM-based JavaScript lifecycle tests (`npm ci --prefix tests --ignore-scripts && node --test tests/*.test.cjs`). Rendered fixture pages are checked in Chromium at narrow, Fold-like and tablet widths. The preview runtime cannot execute Python, so browser checks use isolated rendered fixtures; actual POST behavior and concurrency are tested separately. Real iOS/Android keyboards, installation and folding mid-input still need device acceptance. Server-side catalogue filtering and bounded pages are covered by the catalogue-browsing section below.

## Artikelsuche und grosse Listen · 03.11.2026

- Suche, Warengruppe, Einkaufsort und Bestand werden gemeinsam in der Datenbank gefiltert. Trefferzahl und Haushaltszähler werden separat aggregiert; höchstens 48 Artikelobjekte werden je Katalogseite geladen. Favoriten stehen weiterhin zuerst, danach Name und ID als stabile Sortierung. Keine Datenbankmigration.
- Die Suche bleibt eine wörtliche Teilstringsuche: `%` und `_` sind keine Platzhalter. SQLite nutzt für lokale Unicode-Suche eine verbindungslokale Funktion; Postgres 18 nutzt `casefold(... COLLATE pg_unicode_fast)` für Unicode-Faltung. Damit bleiben auch Einheitenzeichen und Ligaturen suchbar. [Postgres-Dokumentation](https://www.postgresql.org/docs/18/functions-string.html).
- Einkaufsort umfasst bevorzugten Ort, zusätzliche Ortszuordnungen und aktive Produktangebote. Filterauswahl und Metadaten bleiben haushaltsbezogen. Die Optionen stammen aus dem gesamten aktiven bzw. archivierten Katalog und verschwinden nicht durch andere gesetzte Filter.
- Filter liegen in einem aufklappbaren Bereich. Aktive Kriterien, Trefferzahl und Bereich (z.B. 49–96 von 252) sind sichtbar. Neue Suche, geänderte Filter und Wechsel der Artikelansicht starten auf Seite 1; Liste/Karten behalten die aktuelle Seite. Zurücksetzen entfernt Suchbegriff und Kriterien, behält aber Ansicht und Darstellung.
- Seitennavigation, Bearbeiten, Listenaktionen und Rückgängig erhalten den Kontext. Entfernt eine Aktion den letzten Treffer der letzten Seite, wird auf die letzte gültige Seite gewechselt. Die Aktualisierung übernimmt diese kanonische Adresse; ungespeicherte Formulare bleiben geschützt.
- Kontextfelder heissen `filter_category`, `filter_source`, `filter_stock` und `page`. Sie überschreiben keine eigentlichen Artikelfelder wie `source`, `category` oder `stock_status`.
- Scrollanker verwenden die kanonische Listenadresse, damit leere GET-Parameter beim Zurückkehren keine andere Position ergeben. Geöffnete, unveränderte Filter dürfen im Hintergrund aktualisiert werden; Änderungen im Filterformular verhindern dies weiterhin.
- Die Einkaufsliste bleibt zusammenhängend. Einkaufsorte und aktive Angebote werden in drei gebündelten Abfragen geladen statt je Artikel separat; Produkt- und Ortsbezeichnungen werden vorgeladen.
- Assets: CSS v12, App-JS v11, öffentliche Offline-Hülle v7. Alle sechs CSS-Importe bleiben im Offline-Precache.

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

Auto-Aktualisierung nur auf Haushalt/Einkauf, alle 45 Sekunden und beim erneuten Sichtbarwerden. Keine Aktualisierung nach begonnenen Eingaben, waehrend Absenden oder bei geoeffneten Zusatzmengen. Offline-Formulare werden sichtbar blockiert; eine separat gespeicherte, nur lesbare Offline-Liste ist vorhanden.

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

## Scanner und Produktzuordnung

Kein eigener Scan-Tab. Scannen ist eine Hilfsfunktion in Artikelanlage, Nachkaufen und Artikelpflege. Manuelle Eingabe bleibt immer verfuegbar. Kamera startet nur per Schaltflaeche, bietet Stoppen und endet bei Navigation, Hintergrund oder erkanntem Code. Bei fehlendem BarcodeDetector klare Rueckmeldung statt externer SDK-Abhaengigkeit.

Bekannter Barcode zeigt Produkt und Haushaltsartikel mit ausdruecklichen Nachkaufaktionen. Unbekannten Barcode einem bestehenden Artikel zuordnen oder samt neuem Artikel erfassen. Optionaler Open-Food-Facts-Vorschlag mit Herkunft, Lizenzlink und Testkatalog-Hinweis; Formularentwurf bleibt erhalten. Zuordnungen lassen sich in der Artikelpflege entfernen.

| Neue Klassen | Zweck |
| --- | --- |
| scan-entry, scan-layout | Einstieg und flexibles Kamera-/Eingaberaster |
| camera-preview, camera-guide, camera-actions | Lokales Kamerabild, Scanbereich und Touch-Aktionen |
| barcode-code, scan-result, scan-result__actions | Code, Produkt-/Artikelergebnis und Nachkauf |
| barcode-new-item, catalog-lookup | Neuer Artikel und optionale Katalogsuche |
| barcode-mappings | Zuordnungen in der Artikelpflege |

CSS-/App-JS-Version 6, Scanner-JS-Version 1. Kontextueller Rueckgaengig-Hinweis bleibt erhalten. Hardwaretest unter HTTPS: Verpackung/Licht, verweigerte Berechtigung, Hintergrundwechsel, Fold-Aussen-/Innendisplay und Tablet. Simulierte Browser-APIs ersetzen diese Abnahme nicht.

### Scan im jeweiligen Ablauf

- Neuer Artikel: Mit Barcode erfassen; nach Speichern zum Artikel zurueck. Bekannte Produkte anbieten, ohne Duplikat oder Nachkaufaktion.
- Haushalt: Nachkaufen per Barcode; bekannte Artikel zeigen Nachkaufen/Leer und nachkaufen. Die bestaetigte Aktion fuehrt wie gewohnt zum Haushalt mit kontextuellem Rueckgaengig-Hinweis.
- Artikelpflege: Barcode zu diesem Artikel hinzufuegen. Zielartikel fest vorgegeben; Zuordnung zu einem anderen Artikel wird als Konflikt erklaert. Nach Erfolg zur selben Artikelpflege zurueck.
- Abbrechen fuehrt zur jeweiligen Ausgangsseite. Ueberschrift und Hilfetext nennen den aktuellen Zweck. Bestehende Komponenten wiederverwendet; keine neuen CSS-Klassen.

## Installation und Offline-Liste

CSS-/App-JS-Version 7; PWA-JS-Version 2, Store-JS-Version 1; Shell-Cache james-shell-v2. Manifest mit 192-/512-Pixel-Icons, eigenstaendigem App-Fenster und ohne feste Orientierung. Ein Installieren-Button erscheint nur, wenn der Browser einen passenden Installationsdialog anbietet. Ansonsten erklaert der aufklappbare Hilfebereich das Browsermenue. Keine automatische Aufforderung oder neue Hauptnavigation.

| Neue Klassen | Verwendung |
| --- | --- |
| pwa-help | Zurueckhaltender Bereich mit Installationshilfe, Speicherstatus und Offline-Link |
| pwa-actions | Umbruchfaehige Online-/Entfernen-Aktionen in der Offline-Ansicht |

Die Offline-Ansicht zeigt Haushaltsname, Mengen, Einheiten, Kategorie, Bezugsquelle und Zeitpunkt des gespeicherten Stands. Keine Abhak-/Schreibfelder; Rueckweg zur Online-Liste und explizites Entfernen der Geraetekopie. Leere Liste und noch nicht gespeicherte Liste sind verschiedene Zustaende. Texte werden ueber textContent eingesetzt, kein HTML aus Artikelnamen.

Die globale hidden-Regel erzwingt versteckte Elemente auch gegen display-Regeln der Button-/Rasterkomponenten. Reale Installation, Flugmodus-Neustart und beide Fold-Displays bleiben auf den Zielgeraeten abzunehmen.

Der Speicherstatus meldet Offline bereit erst nach erfolgreicher Installation der oeffentlichen Offline-Huelle; vorher wird die Vorbereitung angezeigt.


## Mehrere Produkte und Einkaufsorte

Warengruppe und bevorzugter Einkaufsort sind echte Auswahlfelder. Weitere Orte werden als Checkboxen angeboten; aktive Produktzuordnungen sind sichtbar fest zugeordnet. Warengruppen und Einkaufsorte lassen sich ueber einen verlinkten Verwaltungsbereich hinzufuegen/umbenennen. Keine neue Hauptnavigation.

Artikelpflege fuehrt zu Produkte und Einkaufsorte: Varianten mit Marke/Packung/optionalem Barcode, pro Variante aufklappbare Shop-Zuordnungen mit Inhalt in Artikeleinheiten und optionalem Vorzug. Kleine Displays stapeln Felder und Aktionen; kein festes Fold-Format. Archivierte Artikel zeigen nur lesbare Zuordnungen.

| Neue Klassen | Zweck |
| --- | --- |
| catalogue-row | Umbruchfaehige Umbenennungszeile |
| variant-card, variant-card__heading | Variantenkarte mit Bearbeitungsaktion |
| offer-details, offer-form | Aufklappbare Shop-Zuordnung und Formularraster |
| source-options | Mehrfachauswahl von Einkaufsorten |
| shopping-product | Gewaehlte Variante, Packungszahl und sichtbare Mehrmenge |

CSS-/App-JS-Referenzversion 8, PWA-JS 2, Store-JS 1, Shell-Cache james-shell-v3. Offline-Snapshot zeigt alle Einkaufsorte als Text. Produkt-/Shop-Auswahl ist online; keine neuen Offline-Schreibaktionen. Geraeteabnahme fuer dieses Paket bleibt offen.


## Einkaufsvorhaben

Kein neuer Haupttab: Einstieg in der Einkaufsliste. Einkaufsort waehlen, offene Artikel mit frei verfuegbarer Menge markieren, Vorschlag speichern. Karten mit originaler und noch eingeplanter Menge, gerundeten Packungszahlen aus explizitem Inhalt und Produktlinks. Textliste kopieren oder per nativer Teilen-Funktion weitergeben. Bei fehlender Zuordnung bleibt die Produktwahl sichtbar offen. Bestellbestaetigung ist ein eigener aufklappbarer Schritt mit expliziter Checkbox; Kauf und Wareneingang bleiben getrennt. Auf Handy/Tablet bestehende gestapelte Formularkarten verwenden.

## Verwaltung · 03.11.2026

Die zentrale Verwaltung ersetzt die bisherigen separaten Seiten Zusammen nutzen und Katalogverwaltung. Bereiche, Rechte, Einkaufsansichten und Kataloglebenszyklus sind in [ADMINISTRATION.md](ADMINISTRATION.md) dokumentiert. Aktuell: `app.css?v=13`, sieben CSS-Ebenen inklusive `settings`, `settings.js?v=1`, öffentlicher Shell-Cache v8. Bestehende Legacy-Adressen bleiben als Weiterleitungen bzw. POST-Verträge erhalten.

## Schreibweise · 03.11.2026

Sichtbare deutsche Texte verwenden echte Umlaute und Schweizer ss-Schreibweise. Das gilt auch für Status-/Fehlermeldungen, Offline-Hilfe, ARIA, Beleg-/Scanabläufe, Shop-Testseiten und JayJay. Die verbindliche Regel steht in `AGENTS.md` und `docs/CONVENTIONS.md`. Aktuelle Sprachkorrektur: öffentlicher Shell-Cache v9, PWA-Script v4, JayJay-Script v3 und Vorhaben-Script v2; Styles unverändert v13.

Die Revision `61d8f0ac39b2` korrigiert die frühere Standard-Warengruppe Getraenke zu Getränke unter Beibehaltung ihrer ID. Artikelzuordnungen werden mitgeführt; frühere Bezeichnungen bleiben als Alias auflösbar. Bereits umbenannte oder entfernte Standardgruppen bleiben umbenannt bzw. entfernt. Eine eigenständig angelegte gleichnamige Gruppe wird nicht zusammengeführt. Ein Downgrade lässt die reine Schreibkorrektur bestehen.
