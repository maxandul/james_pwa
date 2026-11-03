# Umsetzungsplan

Stand: 02.11.2026. Konzept zusammengefuehrt; ein erster durchgaengiger Ablauf ist implementiert. Die Paketabnahme bleibt differenziert: Teilschritte sind keine vollstaendigen Pakete.

## Paketfolge

| Paket | Ergebnis | Abnahme | Stand |
| --- | --- | --- | --- |
| K0 Konzept | Gemeinsame Dokumentationsgrundlage | Umfang, Datenmodell, Ablaeufe, Architektur und Testgrenzen beschrieben | Zusammengefuehrt (PR #1) |
| P1 Technische Basis | Flask-Vorschlag konkretisieren, Postgres, Migrationen, Entwicklungs-/Testsetup | App startet; isolierte Testdatenbank; Basis-Checks dokumentiert | Technische Basis und Postgres-CI geprueft; Docker-/Railway-Konfiguration und getrennte staging-Ressourcen eingerichtet; Betriebsabnahme offen |
| P2 Gemeinsamer Haushalt | Login, Mitgliedschaften und Tablet-Zugang | Zwei Personen sehen denselben Haushalt; fremde Haushaltsdaten gesperrt; Tablet-Rechte eingeschraenkt | Persoenliche Zugaenge/Einladungen fertig; Geraetezugang offen |
| P3 Artikel und Bestand | Text, Favoriten, zwei Bestandsmodi und Barcode-Zuordnung | Bekannter Scan findet Produkt; unbekannter Scan manuell erfassbar; unbekannter Bestand bleibt moeglich | Text, Favoriten, Artikelpflege und einfacher Status fertig; Barcode-Zuordnung und Kameraablauf implementiert; Hardwareabnahme/Mengenbestand offen |
| P4 Einkaufsliste | Nachkaufen, Zusatzmenge, Filter, Ladeneinkauf und Ruecknahme | Gleichzeitiges Nachkaufen erzeugt einen Bedarf; Einkauf/Ruecknahme verbucht Bestand und Bedarf konsistent | Nachkauf, Zusatz-/Teilkauf, Entfernen und Ruecknahme implementiert; visuelle Abnahme offen |
| P5 Alltag und PWA | Tablet-/Handybedienung, Aktualisierung, Offline-Lesen, Railway-Testbetrieb | Reale Geraete geprueft; gespeicherte Liste offline sichtbar; Offline-Schreiben klar blockiert; Backup/Restore geprueft | Railway online, Ersteinrichtung bestaetigt; Installation und Offline-Lesen implementiert. PWA-/Offline-Test vom Nutzer bestaetigt; Kamera-/Fold-Abnahme, Backup/Restore und eingeschraenkter Geraetezugang offen |
| P6 Einkaufsvorhaben | Produkt-/Shop-Zuordnung, Entwuerfe, Bestellstatus und Wareneingang | Bedarf nicht doppelt eingeplant; bestellt ist nicht geliefert; Teillieferung und doppelte Bestaetigung korrekt | Produkt-/Shop-Grundlage auf staging ausgeliefert; Belegimport ausgeliefert; manuelle Einkaufsvorhaben ausgeliefert; JayJay-Textgrundlage in Umsetzung |
| P7 Shop-Uebergabe | Pro Shop nachgewiesener Warenkorbweg | Angemeldeter Test, mehrere Mengen, Wiederholungen und Sitzungsablauf geprueft | Offen |
| P8 Wochenroutine | Serverseitiger Vorschlag und Benachrichtigung | Ein Vorschlag je Haushalt und Termin; keine Abhaengigkeit von geoeffneter PWA; manueller Start bleibt moeglich | Offen |
| P9 ChatGPT und Kochen | MCP, Rezepte und Menuevorschlaege | Gleiche Haushaltsrechte und Fachregeln; unsichere Bestaende sichtbar; Zutaten erst nach Bestaetigung erfasst | Offen |

**Erste alltagstaugliche Version: P1 bis P5.** Produktlinks und frei waehlbare Bezugsquellen koennen darin bereits enthalten sein. Shop-Automatisierung ist keine Voraussetzung fuer den Grundnutzen.

P6 bis P9 sind getrennte Ausbauschritte. Der automatische verbindliche Bestellabschluss gehoert noch zu keinem zugesagten Paket.

## Vor den jeweiligen Paketen festlegen

- P1: Flask umgesetzt und Pakete gepinnt; Zielumgebung/Deployment noch einrichten.
- P2: E-Mail/Passwort und Einladungen bestaetigt und umgesetzt; Tablet-Zugang noch entscheiden.
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

## Aktueller Ausbau nach Nutzerfeedback

Akzeptierte Reihenfolge: (1) Produkt-/Shop-Grundlage und eigene Kataloge, (2) Kassabon-/Digitalbelegimport mit Pruefansicht fuer mehrere Artikel, (3) nachgewiesene Warenkorbuebergabe, (4) integrierter James-Chat mit denselben Haushaltsregeln. Direkter verbindlicher Bestellabschluss bleibt ein gesonderter Funktions-/Freigabeschritt.

| Paket | Stand |
| --- | --- |
| Eigene Warengruppen/Einkaufsorte, mehrere Varianten/Laeden, Vorzug und Packungsmengen | Ausgeliefert auf staging, Migration und Healthcheck bestaetigt; neue Masken auf Zielgeraeten noch pruefen |
| Foto/PDF-Belege fuer alle Positionen | Implementiert: lokale PDF-/Foto-Texterkennung, manuelle Textalternative, Pruefansicht, atomare Buchung und Ruecknahme; auf staging ausgeliefert, 130 Postgres-Tests erfolgreich |
| Coop/Migros/Galaxus-Warenkoerbe | Manuelle Einkaufsvorbereitung implementiert; native automatische Uebergabe und angemeldeter Nachweis weiterhin offen |
| James-Chat mit Lesen/Aendern/Loeschen und Einkaufsvorbereitung | Textchat und begrenzte Haushaltswerkzeuge vorbereitet; ohne OpenAI-Zugang deaktiviert. Live-Test, Browseragent und Sprache offen |

Nutzer bestaetigt laufende Online-App und PWA-/Offline-Test. Kamera bei schlechtem Licht noch ohne Erfolg; reale Scan-/Fold-/Tablet-Abnahme und Backup/Restore bleiben offen. Eingeschraenkter Tablet-Zugang und Mengenbestand sind weiter offen.

Produkt-/Shop-Update am 02.11.2026 gemaess ausdruecklicher Nutzerfreigabe ohne Backup ausgeliefert: noch keine echten Daten. Backup/Restore bleibt vor echtem Alltagsbetrieb offen. Vision fuer JayJay siehe JAYJAY_VISION.md; sie veraendert die laufende Reihenfolge nicht.
