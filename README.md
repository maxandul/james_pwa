# James PWA

James unterstuetzt einen gemeinsam gefuehrten Haushalt beim Erfassen von Vorrat, Nachkaufen, Einkaufen und spaeter bei der Menueplanung.

**Stand: 01.11.2026. Eine lokale Erstversion ist implementiert und automatisiert getestet; noch kein Railway-Deployment.**

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

Implementiert sind Artikel mit einfachem Bestandsstatus, Nachkaufmenge, gemeinsamer Einkaufsliste, Zusatz- und Teilmengen sowie Rueckgaengig. Tablet-Geraetezugang, Barcode, Mengenbestand, PWA-Installation/Offline-Lesen, Shop-Uebergabe und MCP folgen spaeter.

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
