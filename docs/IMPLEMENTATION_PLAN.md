# Umsetzungsplan

Stand: 01.11.2026. Alle Implementierungspakete sind offen. Die Reihenfolge ist ein Vorschlag; keine App-Implementierung ist mit diesem Dokument abgeschlossen.

## Paketfolge

| Paket | Ergebnis | Abnahme | Stand |
| --- | --- | --- | --- |
| K0 Konzept | Gemeinsame Dokumentationsgrundlage | Umfang, Datenmodell, Ablaeufe, Architektur und Testgrenzen beschrieben | Entwurf erstellt, Review offen |
| P1 Technische Basis | Flask-Vorschlag konkretisieren, Postgres, Migrationen, Entwicklungs-/Testsetup | App startet; isolierte Testdatenbank; Basis-Checks dokumentiert | Offen |
| P2 Gemeinsamer Haushalt | Login, Mitgliedschaften und Tablet-Zugang | Zwei Personen sehen denselben Haushalt; fremde Haushaltsdaten gesperrt; Tablet-Rechte eingeschraenkt | Offen |
| P3 Artikel und Bestand | Text, Favoriten, zwei Bestandsmodi und Barcode-Zuordnung | Bekannter Scan findet Produkt; unbekannter Scan manuell erfassbar; unbekannter Bestand bleibt moeglich | Offen |
| P4 Einkaufsliste | Nachkaufen, Zusatzmenge, Filter, Ladeneinkauf und Ruecknahme | Gleichzeitiges Nachkaufen erzeugt einen Bedarf; Einkauf/Ruecknahme verbucht Bestand und Bedarf konsistent | Offen |
| P5 Alltag und PWA | Tablet-/Handybedienung, Aktualisierung, Offline-Lesen, Railway-Testbetrieb | Reale Geraete geprueft; gespeicherte Liste offline sichtbar; Offline-Schreiben klar blockiert; Backup/Restore geprueft | Offen |
| P6 Einkaufsvorhaben | Produkt-/Shop-Zuordnung, Entwuerfe, Bestellstatus und Wareneingang | Bedarf nicht doppelt eingeplant; bestellt ist nicht geliefert; Teillieferung und doppelte Bestaetigung korrekt | Offen |
| P7 Shop-Uebergabe | Pro Shop nachgewiesener Warenkorbweg | Angemeldeter Test, mehrere Mengen, Wiederholungen und Sitzungsablauf geprueft | Offen |
| P8 Wochenroutine | Serverseitiger Vorschlag und Benachrichtigung | Ein Vorschlag je Haushalt und Termin; keine Abhaengigkeit von geoeffneter PWA; manueller Start bleibt moeglich | Offen |
| P9 ChatGPT und Kochen | MCP, Rezepte und Menuevorschlaege | Gleiche Haushaltsrechte und Fachregeln; unsichere Bestaende sichtbar; Zutaten erst nach Bestaetigung erfasst | Offen |

**Erste alltagstaugliche Version: P1 bis P5.** Produktlinks und frei waehlbare Bezugsquellen koennen darin bereits enthalten sein. Shop-Automatisierung ist keine Voraussetzung fuer den Grundnutzen.

P6 bis P9 sind getrennte Ausbauschritte. Der automatische verbindliche Bestellabschluss gehoert noch zu keinem zugesagten Paket.

## Vor den jeweiligen Paketen festlegen

- Vor P1: Flask und minimale technische Abhaengigkeiten bestaetigen, Deployment-Konfiguration waehlen.
- Vor P2: Login, Einladungsweg und Einrichtung des Tablet-Zugangs entscheiden.
- Vor P3/P5: Geraet/Betriebssystem und Kameraposition praktisch pruefen; keinen Tablet-Kauf allein auf Annahmen stuetzen.
- Vor P6/P7: Beispielprodukte, Bestellberechtigte und Ersatzregeln festlegen; angemeldete Testsitzung einrichten.
- Vor P7: Standort des Browsers und Uebergabe in den persoenlichen Shop-Warenkorb nachweisen.
- Vor P8: Wochentag, Zeitzone Europe/Zurich, Uhrzeit und Benachrichtigungsempfaenger festlegen.
- Vor P9: Konkrete ChatGPT-/MCP-Verfuegbarkeit und Datenzugriffe pruefen.

## Tests mit hohem fachlichem Nutzen

- Haushaltsgrenzen und eingeschraenkter Geraetezugang.
- Zwei gleichzeitige Nachkaufmeldungen, bewusste Zusatzmenge und wiederholte Requests.
- Unterschiedliche Packungsgroessen und fuehrende Nullen im Barcode.
- Bestandsaenderung, Bedarfsdeckung und Ruecknahme als zusammenhaengende Buchung.
- Teillieferung, Stornierung offener Restmengen und doppelt bestaetigter Wareneingang.
- Netzwerkverlust mit erkennbarer Rueckmeldung; spaeter Konflikte einer Offline-Warteschlange.
- Shop-Uebergabe mit vorhandenen Warenkorbinhalten, abgelaufener Sitzung und unklarem Ergebnis.

Browser-Tests belegen die konkrete Oberflaeche zum Testzeitpunkt. Sie ersetzen keine automatisierten Pruefungen der eigenen Fachlogik oder einen Test aus der Zielumgebung.

## Naechster Arbeitsschritt nach Konzeptreview

P1 und die Entscheidungen fuer P2 vorbereiten. Parallel im normalen Arbeitsablauf die offenen Shop-Tests durchfuehren, sobald eine passende angemeldete Sitzung vorhanden ist. Das sind getrennte Aufgaben; ein fehlender Shop-Zugang blockiert die grundlegende Einkaufsliste nicht.

## Bewusste Grenzen dieses Auftrags

Dieser Stand enthaelt nur Dokumentation. Keine Railway-Ressourcen, Secrets, Datenbanken, Shop-Konten, Hintergrundauftraege oder kostenpflichtigen Bestellungen wurden eingerichtet.
