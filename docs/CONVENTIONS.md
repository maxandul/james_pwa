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
