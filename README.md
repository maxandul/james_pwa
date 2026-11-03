# James PWA

James unterstuetzt einen gemeinsam gefuehrten Haushalt beim Erfassen von Vorrat, Nachkaufen, Einkaufen und spaeter bei der Menueplanung.

**Stand: 01.11.2026. Eine lokale Erstversion ist implementiert und automatisiert getestet; Railway-Testumgebung eingerichtet, erste Betriebsabnahme noch offen.**

## Einstieg

| Dokument | Inhalt |
| --- | --- |
| [Konzept](docs/CONCEPT.md) | Zielbild, vereinbarte Richtung und Umfang der ersten Version |
| [Bedienablaeufe](docs/USER_FLOWS.md) | Kuechentablet, Handy, Nachkaufen, Einkauf und Lieferung |
| [Datenmodell](docs/DATA_MODEL.md) | Haushalt, Artikel, Produkte, Bestand und Einkaufsbedarf |
| [Architektur](docs/ARCHITECTURE.md) | Technischer Vorschlag, Railway und ChatGPT/MCP |
| [Shop-Machbarkeit](docs/SHOP_FEASIBILITY.md) | Dokumentation und Ergebnisse der bisherigen Browser-Tests |
| [Umsetzungsplan](docs/IMPLEMENTATION_PLAN.md) | Pakete, Abnahmekriterien und offene Entscheidungen |

## Erste Version starten

Siehe [Runbook](docs/RUNBOOK.md) fuer Installation, Datenbankmigration und Erstbenutzer. Anmeldung erfolgt mit E-Mail und Passwort; weitere Zugaenge entstehen ausschliesslich ueber persoenliche Einladungslinks.

Implementiert sind Artikelpflege mit Favoriten und Archiv, direkter einfacher Bestandsstatus, Nachkaufmenge, gemeinsame Einkaufsliste, Zusatz-/Teilmengen, Entfernen und Rueckgaengig. Barcodes unterstuetzen die Artikelanlage, das Nachkaufen und die Artikelpflege direkt im jeweiligen Ablauf. Manuelle Eingabe und bei Browserunterstuetzung Kamera-Erkennung sind verfuegbar; kein eigener Scan-Tab. Optional liefert Open Food Facts einen zu pruefenden Produktvorschlag. Tablet-Geraetezugang, Mengenbestand, Shop-Uebergabe und MCP folgen spaeter. PWA-Installation und Offline-Lesen sind implementiert; reale Geraeteabnahme bleibt offen. Kamera und Bedienung auf echten Zielgeraeten sind noch abzunehmen.

Weitere Umsetzungshinweise: [Zugang](docs/AUTH.md), [Konventionen](docs/CONVENTIONS.md), [UI](docs/UI.md).

## Produktprinzipien

- Das Erfassen im Alltag muss schneller sein als das spaetere Erinnern.
- Bestand darf ungefaehr oder unbekannt sein.
- Eine gemeinsame Einkaufsliste bedient Online-Shops und Ladeneinkaeufe.
- Bedarf, konkretes Produkt und Bezugsquelle bleiben getrennt.
- Bestellt bedeutet noch nicht geliefert.
- Jede Shop-Funktion wird nachgewiesen, bevor sie als verfuegbar gilt.

## Technische Richtung

PWA fuer Kuechentablet und Handy, Python-Backend mit Flask, Postgres und Railway. ChatGPT soll spaeter ueber einen authentifizierten MCP-Zugang auf dieselben Haushaltsfunktionen zugreifen.

Der erste praktische Browser-Test bestaetigt Produktsuche bei Coop und Galaxus sowie das Hinzufuegen eines Testartikels zu einem nicht angemeldeten Galaxus-Warenkorb. Eine angemeldete Shop-Anbindung, geraeteuebergreifende Warenkorbuebergabe und automatischer Bestellabschluss sind nicht nachgewiesen.

## Arbeit am Projekt

Vor Umsetzung das Konzept und die zum Paket passenden Dokumente lesen. Neue Entscheidungen und erreichte Abnahmekriterien in der Dokumentation nachfuehren. Shop-Tests immer mit Umgebung, Datum, Ergebnis und Grenzen dokumentieren.

Dokumentations- und Feature-Aenderungen ueber Branch und Pull Request. Keine Zugangsdaten, Cookies, privaten Haushaltsdaten oder Bestelldetails im Repository speichern.

## HTTPS-Vorschau vorbereiten

Dockerfile und deployment/railway-settings.json (Referenz, nicht automatisch angewendet) enthalten Produktionsstart, Pre-Deploy-Migration und Healthcheck. Die CI prueft das echte Containerimage gegen isoliertes Postgres. Die konkrete Einrichtung der getrennten Railway-Testumgebung steht im [Runbook](docs/RUNBOOK.md#konkrete-https-testumgebung-vorbereiten). Die Testadresse ist https://james-web-staging.up.railway.app. Deploymentstatus und verbleibende Abnahme siehe Runbook/VALIDATION.md; erster Owner wird interaktiv eingerichtet.

## Als App und ohne Empfang nutzen

James kann ueber das Browsermenue zum Startbildschirm hinzugefuegt/installiert werden. Nach Online-Anmeldung speichert es die Einkaufsliste auf diesem Geraet. Ohne Verbindung zeigt es den letzten Stand mit Zeitstempel ausschliesslich zum Lesen. Abmelden entfernt die Kopie. Installationshilfe und Speicherstatus stehen unten in der App; Praxistest siehe Runbook.


## Produkte und mehrere Einkaufsorte (vorbereitet)

Ein Haushaltsartikel kann bei mehreren Laeden gekauft werden. Warengruppen/Einkaufsorte sind erweiterbar und umbenennbar. Unter Artikel bearbeiten → Produkte und Einkaufsorte lassen sich konkrete Varianten und je Laden ein Vorzugsprodukt mit Packungsinhalt hinterlegen. Die gefilterte Einkaufsliste zeigt die passende Variante und gerundete Packungszahl; Bedarf bleibt einmalig. Keine automatische Bestellung in diesem Schritt. Auslieferung mit additiver Migration erst nach Datenbanksicherung; Details in docs/RUNBOOK.md.


## Viele Artikel übersichtlich nutzen

Die Haushaltsübersicht bietet kombinierbare Suche und Filter nach Warengruppe, Einkaufsort und Bestand. Zusätzliche Einkaufsorte und aktive Produktangebote werden berücksichtigt. Die Unicode-Suche verwendet die bereits eingesetzte Version Postgres 18. Pro Seite erscheinen höchstens 48 Artikel; Trefferzahl und Bereich bleiben sichtbar. Favoriten/Archiv sowie Liste/Karten lassen sich weiter umschalten. Filter, Seite und Listenposition bleiben bei Artikelaktionen und Bearbeitung erhalten. Die aktive Einkaufsliste bleibt eine zusammenhängende Arbeitsliste.
