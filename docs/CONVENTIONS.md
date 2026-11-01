# Implementierte Konventionen

Stand: 01.11.2026.

- App Factory in `james/__init__.py`, Erweiterungen in `extensions.py`, Modelle in `models.py`.
- `services.py` enthaelt Fachregeln. Routes/CLI besitzen die Transaktion und rufen commit/rollback auf.
- Haushalt wird aus der aktiven Mitgliedschaft abgeleitet, nie aus einem frei waehlbaren Formularfeld.
- Zustandsaenderungen nur per POST mit globalem CSRF-Schutz. Jinja escaped Benutzereingaben.
- Mengen dieser ersten Version sind ganze Packungen/Stuecke von 1 bis 999. Mengenbestand und Packungsumrechnung folgen spaeter.
- Ein ShoppingNeed pro Artikel, Menge null bedeutet erledigt. Der Bestand bleibt ein einfacher Status.
- Jede Listenaktion hat eine UUID. Wiederholungen derselben UUID werden nicht erneut gebucht.
- PostgreSQL-Zeilensperre am Artikel und Versionspruefung schuetzen zusammenhaengende Aenderungen. Veraltete Formulare erhalten 409 statt stiller Ueberschreibung.
- Jede Listenaktion schreibt Activity mit vorherigem/nachherigem Zustand und Urheber. Ruecknahme geht nur fuer die letzte Version des Artikels und erzeugt eine Gegenbuchung.
- Zeitpunkte intern naive UTC; Ablaufpruefungen ausschliesslich mit `utcnow()`. Einladungen gelten sieben Tage. Die UI zeigt keine als lokale Zeit missverstandenen UTC-Uhrzeiten.
- Tests verwenden ausschliesslich Beispieldaten. Fremde Haushalte, CSRF, Einladungen, Replay, Teilkauf und Ruecknahme sind Pflichtfaelle.
- Schemaaenderungen mit Alembic; Migrationsdateien in eigenem Commit. Kein `create_all()` im normalen App-Start.
- Dokumente mit Umsetzungsstand pflegen. Noch offene Funktionen nicht als fertig kennzeichnen.
- Deutsch ohne Eszett. Keine extern geladenen Fonts oder Scripts.

Einladungslinks werden pro Haushalt unter einer Zeilensperre ausgestellt, damit auch gleichzeitiges Neuausstellen nur einen aktiven Link fuer dieselbe Adresse hinterlaesst. Der Postgres-Test prueft diesen Fall mit zwei Transaktionen.

## Artikelpflege

Favoriten gelten gemeinsam fuer den Haushalt. Archivieren ist ein logischer Status am Artikel, keine Loeschung. Ein Artikel mit offenem Einkaufsbedarf kann nicht archiviert werden; serverseitige Sperre und Versionspruefung erhalten diese Regel auch bei gleichzeitigen Eingaben.

Bestandskorrektur und Entfernen von der Einkaufsliste sind getrennte Aktionen. Eine Bestandskorrektur bucht keinen Kauf; Entfernen setzt nur den Bedarf auf null. Metadaten, Favoriten, Archiv und Bestand gehen in den Activity-Snapshot ein, damit die direkte Ruecknahme den vorherigen Zustand herstellen kann. Alte Snapshots ohne Metadaten bleiben lesbar.

Eine neue Nachkaufmenge veraendert bereits offenen Bedarf nicht. Einheitenwechsel ist bei offenem Bedarf gesperrt, da sonst vorhandene Mengen eine neue Bedeutung erhielten. Veraltete Bearbeitungsformulare erhalten 409 mit Aufforderung zum Neuladen; sie bekommen keine still aktualisierte Versionsnummer zum Ueberschreiben.

Listenfilter und Suchbegriff bleiben nach Kartenaktionen erhalten. Breiten-/Orientierungswechsel loesen kein Neuladen oder Zuruecksetzen von Formularen aus.

## Barcodes und Produktvorschlaege

- GTIN ausschliesslich als ASCII-Ziffernfolge mit Laenge 8/12/13/14 und gueltiger GS1-Pruefziffer. Fuehrende Nullen erhalten; kanonischer Vergleich mit links auf 14 Stellen aufgefuelltem Wert. Keine URL als Barcode akzeptieren.
- Ein Barcode pro Haushalt eindeutig. Alle Zugriffe pruefen Haushalt von Barcode, Produkt und Artikel. Erstregistrierung sperrt den Haushalt; parallele Requests erzeugen keine zweite Zuordnung. Vorhandene Zuordnung wird nicht still umgehaengt.
- Zuordnung und Entfernen der Zuordnung buchen keinen Bedarf oder Bestand. Entfernen behaelt Produkt und Artikel; erneutes Erfassen ist moeglich. Keine Activity-Ruecknahme fuer reine Barcode-Zuordnungen.
- Routes besitzen commit/rollback. Katalog-Gate vor HTTP committen, damit keine Zeilensperre waehrend des Netzwerkzugriffs gehalten wird. Cache enthaelt ausschliesslich oeffentliche Providerdaten; Herkunft bei bestaetigter Produktregistrierung erhalten.
- Kamera nur nach Benutzeraktion; Tracks auch bei Abbruch waehrend der Berechtigungsfrage, Hintergrundwechsel und Navigation beenden. Spaete asynchrone Ergebnisse ignorieren.
- Beim Sperren von Absende-Schaltflaechen den Namen/Wert von event.submitter als verstecktes Feld erhalten; sonst geht die explizite Katalogaktion verloren.

Scan-Kontext: flow ist ausschliesslich create/assign/replenish; Ruecksprungziele werden serverseitig aus benannten Routes erzeugt, keine freie Return-URL. context_item_id bei assign wird bei jedem GET/POST erneut gegen den Haushalt geprueft. Bei Registrierung hat dieses gepruefte Ziel Vorrang vor item_id. Kontext bleibt in Formularen einschliesslich Katalogsuche und Fehlerkorrektur erhalten. Erfassen/Zuordnen bietet keine Kaufbuchung an.

Deployment-Konfiguration wird mit dem Code versioniert: Dockerfile fuer die Laufzeit, deployment/railway-settings.json (Referenz, nicht automatisch angewendet) fuer Build/Migration/Healthcheck. Container kopieren nur explizite Laufzeitpfade; keine lokalen Daten oder Secrets. CI prueft den gebauten Container mit Produktionseinstellungen gegen ausschliesslich isoliertes Postgres. scripts/check_deployment.py fuehrt nur oeffentliche Lesezugriffe ohne Anmeldedaten aus.

Pre-Deploy bestaetigt nach db upgrade auch db current und db check. Die CI-Datenbankversion folgt der eingesetzten Railway-Hauptversion (aktuell 18).

/health ist ein Readinesscheck: erwartete Tabellen vorhanden und Alembic-Revision entspricht den ausgelieferten Heads. SELECT 1 allein ist kein Betriebsnachweis. Railway-Einstellungen aktiv am richtigen Service speichern und zuruecklesen; eine Referenzdatei im Repository ist kein Nachweis ihrer Anwendung. Nach Neu-Deployment Schema-Readiness erneut pruefen.

## Offline-Konventionen

- Service Worker nur fuer versionierte oeffentliche Dateien und eine identitaetsfreie Huelle. Niemals authentifiziertes HTML oder API-/POST-Antworten cachen.
- Offline-Snapshot separat, ein Benutzer/Haushalt pro Browserprofil. Aktive Mitgliedschaft serverseitig pruefen; private Antworten immer no-store.
- Abmelden/Kontowechsel loeschen den Snapshot. In-flight-Requests muessen Besitzer und Generationskennung vor jedem Speichern pruefen; aeltere Snapshots nicht ueber neuere schreiben.
- Offline-Daten ausschliesslich als Text rendern. Kein Offline-Schreiben ohne eigenen fachlichen Entwurf; keine automatische Wiederholung von POSTs.
- Bei Aenderung oeffentlicher Offline-Assets Referenzversionen und Worker-Cacheversion gemeinsam pflegen. Kein erzwungenes Neuladen waehrend Formulareingaben.



## Kataloge und Shop-Zuordnungen

- Warengruppen/Einkaufsorte gehoeren einem Haushalt. Namen normalisieren mit Unicode NFKC/casefold; alte Namen als Alias erhalten. Umbenennen aktualisiert Artikel und ihre Versionen; alte Activity-Snapshots werden bei Ruecknahme auf den aktuellen Namen abgebildet.
- Artikel behalten ihre Textfelder fuer kompatible Historie. ItemSource enthaelt die weiteren Orte. Bevorzugter Ort und aktive ShopOffer-Orte bleiben stets enthalten; zusaetzliche Orte sind frei waehlbar. Alle IDs erneut gegen den Haushalt pruefen.
- Pro Produkt/Einkaufsort genau eine Shop-Zuordnung. Pro Artikel/Einkaufsort hoechstens ein aktives Vorzugsprodukt, serialisiert ueber Household-Sperre. Ohne eindeutige Variante keine automatische Auswahl.
- units_per_pack ist eine ausdruecklich bestaetigte positive Dezimalmenge in der Artikeleinheit, maximal drei Nachkommastellen. Freier Verpackungstext bewirkt keine Umrechnung. Packungszahl aufrunden und Mehrmenge sichtbar machen. Kaufbuchung bleibt in der Artikeleinheit.
- Einheitenwechsel einschliesslich Ruecknahme ist bei aktiven Packungszuordnungen gesperrt; erst deaktivieren, Einheit aendern, Umrechnung neu bestaetigen.
- Versionierte Artikelaktionen laufen in no_autoflush, damit Katalog-/Linkabfragen keine halbe Aenderung speichern oder die Version doppelt erhoehen. Neue Katalogeintraege nur gezielt flushen; die ganze Aktion am Ende flushen.
- Produkt/Katalog/Angebotsformulare verwenden Versionspruefungen. Produktlinks nur HTTPS ohne eingebettete Zugangsdaten; keine Zugangsdaten speichern, keine Links automatisch aufrufen.
