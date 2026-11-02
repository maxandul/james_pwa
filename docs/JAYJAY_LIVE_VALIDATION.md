# JayJay: Live-Pruefung vom 02.11.2026

Der synthetische Verbindungstest mit gpt-6-luna ist erfolgreich. Es wurden keine echten Haushaltsdaten fuer diese lokale Pruefung verwendet.

## Beobachtung und Korrektur

Mit der Standard-Denkstufe konnte ein Auftrag nach einer bereits gespeicherten Aenderung das bisherige 20-Sekunden-Budget erreichen. Auch reasoning.effort=low war fuer einzelne einfache Auftraege zu langsam.

Der begrenzte Haushaltspilot verwendet deshalb reasoning.effort=none. Mehrere Werkzeugaufrufe pro Modellrunde sind erlaubt; die App fuehrt sie weiterhin nacheinander aus und prueft jeden Aufruf. So koennen mehrere Artikel innerhalb der vier Modellrunden gelesen, geaendert und bestaetigt werden. Das Gesamtbudget betraegt 25 Sekunden, einzelne HTTP-Anfragen bleiben auf 20 Sekunden begrenzt. Vier Aenderungen, vier Modellrunden, 1200 Ausgabetoken und das Tageslimit bleiben bestehen. Kein automatischer Wiederholungsversuch.

## Nachweise

Echte Modellantworten in einer isolierten SQLite-Testdatenbank wurden fuer Lesen, Nachkaufen, Zusatzmenge, Neuanlage, Entfernen, mehrdeutige Artikelnamen und zwei Artikel geprueft. Gespeicherte Mengen wurden direkt aus der Datenbank gelesen. Bei Mehrdeutigkeit erfolgte eine Rueckfrage ohne Aenderung. Die Variante mit 20 Sekunden scheiterte einmal beim Abschluss eines bereits korrekt gespeicherten Mehrartikel-Auftrags; nach Erweiterung auf 25 Sekunden wurden ein Mehrartikel-Auftrag und ein Einzelauftrag erfolgreich abgeschlossen. Die letzten beiden Antworten benoetigten rund 16 und 24 Sekunden. Dies ist ein kleiner Funktionsnachweis und keine statistische Zuverlaessigkeitsmessung.

Nach einer echten, vom Modell ausgeloesten Speicherung wurde ausserdem ein Verbindungsabbruch kuenstlich ausgeloest: Die Aenderung blieb erhalten, der Dialog meldete den unvollstaendigen Abschluss, und dieselbe Anfragekennung erzeugte keinen neuen Auftrag.

Lokale Regression: 149 SQLite-Tests bestanden, neun Postgres-spezifische Tests uebersprungen; drei Migrationstests liefen nach Korrektur des aufgerufenen Python-Pfads erfolgreich erneut. Die 15 JayJay-Tests und drei Migrationstests wurden zusammen erneut ausgefuehrt. 17 JavaScript-Tests bestanden. Postgres und die Zielumgebung muessen beim Deploy separat nachgewiesen werden.

Die erfolgreiche lokale Pruefung bedeutet noch keine Aktivierung in der Zielumgebung. Sichere Laufzeitkonfiguration, erfolgreicher Deploy, Readiness und ein Dialog aus der Zielumgebung bleiben separat zu pruefen. Zugangsdaten gehoeren nicht in dieses Dokument oder das Repository.
