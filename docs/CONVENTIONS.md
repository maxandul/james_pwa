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
