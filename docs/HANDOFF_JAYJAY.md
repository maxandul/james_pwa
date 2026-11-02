# Uebergabe: JayJay und Browser-Einkaufsagent

## Implementierter Stand

Die PWA besitzt Artikelpflege, Barcode-Kontexte, Offline-Lesen, Produkt-/Shop-Zuordnungen, Belegimport und manuelle Einkaufsvorhaben. Native automatische Warenkorbbefuellung bleibt offen.

Der Textbutler ist vorbereitet, bleibt bis zum bestandenen Live-Test deaktiviert. Die bisherige Validierung umfasst 156 Postgres-Tests, 17 JavaScript-Tests und simulierte Modellantworten. Diese Tests belegen keine erfolgreiche echte Modellantwort oder Shop-Uebergabe.

Wichtige Dateien: james/jayjay.py (Agentenschleife/Werkzeuge), james/chat.py (Dialog), james/services.py (Fachregeln), tests/test_jayjay.py und tests/test_postgres.py. Konzept: JAYJAY_VISION.md, Architektur: ARCHITECTURE.md, Shop-Nachweise: SHOP_FEASIBILITY.md.

## Unmittelbar fortsetzen

1. Den aktuellen privaten Chat zum Zugangstest lesen und die dort genannte Voraussetzung mit dem Nutzer klaeren. Den bisherigen fehlgeschlagenen Test nicht als Erfolg behandeln oder automatisch wiederholen. Keine Kontodaten oder Geheimnisse in dieses Repository uebernehmen.
2. Fuer den ersten Modelltest gpt-6-luna als Kandidaten anhand aktueller offizieller Dokumentation und tatsaechlichem Kontozugang pruefen. Einen kleinen Verbindungstest ohne Haushaltsinhalt ausfuehren (CLI jayjay-check).
3. Danach in isolierter Testdatenbank echte Agentenablaeufe mit synthetischen Artikeln pruefen: Lesen, Nachkaufen, Zusatzmenge, Neuanlage, Ruecknahme, Mehrdeutigkeit, mehrere Artikel und Fehler nach einer bereits gespeicherten Aenderung. Datenbankstand und nicht nur Antworttext pruefen.
4. Erst nach erfolgreichem Live-Test geschuetzte Laufzeitkonfiguration und Aktivierung vornehmen. Vorhandene Nutzerfreigaben beachten, Zugang sicher wiederverwenden und keine neuen Schluessel ohne Anlass erstellen. Geheimnisse nicht ueber normale Werkzeugausgaben oder Commits transportieren.
5. Tatsaechlichen Deploy, Readiness und Dialog aus der Zielumgebung pruefen. Erst dann Aktivierung behaupten.

## Fachliche Grenzen

Chatverlauf ist pro Person privat. Aktionen betreffen den gemeinsamen Haushalt. Fachregeln bleiben zentral; der Agent erhaelt keinen freien SQL-/Shell-Zugriff. Mitgliedschaft und Auth-Version vor Werkzeugen neu pruefen. Eine wiederholte Nachricht darf keine zweite Buchung erzeugen. Nach einem Verbindungsfehler bleiben bereits gespeicherte Aktionen sichtbar und werden nicht automatisch wiederholt.

Pilotlimits: 20 Nachrichten je Haushalt/UTC-Tag, vier Modellrunden, maximal vier Aenderungen, 1200 Ausgabetoken je Antwort und 20 Sekunden Laufzeitbudget. Das ist kein Geld-Kostendach. Mehrartikel-Auftraege und Latenz gezielt mit dem echten Modell pruefen.

## Danach mit frischem Kontext: Browser-Einkaufsagent

Ein zentraler Butler bleibt das Gegenueber. Spezialagenten werden bei Bedarf als Werkzeuge aufgerufen. OpenAI-Faehigkeiten verwenden statt Browserautomation vollstaendig selbst zu bauen. Keine automatische Uebernahme persoenlicher ChatGPT-Gespraeche, Erinnerungen oder Browser-/Shop-Sitzungen annehmen.

Browser-Prototyp ist noch nicht implementiert oder getestet. Aktuelle offizielle Agents-/Computer-Use-Dokumentation lesen, API-Zugang pruefen, dann oeffentliche Produktseite und interaktive Shop-Anmeldung testen. Genau drei vorgegebene Produkte einschliesslich Menge 2 im Warenkorb nachweisen. Vorhandene Inhalte respektieren, keine Duplikate bei Wiederholung, Sitzungsabbruch sauber behandeln und Warenkorb auf dem persoenlichen Geraet verifizieren. Kein Bestellabschluss im ersten Test.

Weitere offene Bausteine: Sprache/Butler-Stimme, MCP, Rezeptsammlung, Kalender, Wetter/Regenradar, Spotify, Wissensbasis und Entwicklungsspezialist. Handy/Tablet zuerst; Fold-Aussen-/Innendisplay und Orientierungswechsel beruecksichtigen. Reale Beleg- und Kameratests sowie Backup/Restore bleiben separat offen.
