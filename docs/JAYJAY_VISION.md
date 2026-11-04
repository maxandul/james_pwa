# James – JayJay: Gedanken und Ausbaurichtung

Nutzernotiz vom 02.11.2026. Diese Vision erweitert das Zielbild; sie aendert die laufende Reihenfolge nicht.

- James, Spitzname JayJay, soll per Sprache steuerbar sein und wie ein Butler antworten. Gewuenscht ist eine Stimme mit britischem Akzent; Sprache und konkrete Stimme spaeter praktisch ausprobieren.
- Eigene Rezeptsammlung. Rezeptvorschlaege sollen im Internet Inspiration aus der gehobenen Kueche suchen, etwa bei GaultMillau. Quellen verlinken; keine ungepruefte Uebernahme kompletter fremder Rezepttexte.
- Geplante Mahlzeiten um vorhandene bzw. unsichere Bestaende abgleichen und fehlende Zutaten zur Einkaufsliste ergaenzen. Mengen, Portionen und Einheiten explizit pruefen.
- Eigene Kalender einbinden und morgens oder auf Abruf einen Tagesplan vorschlagen. Noch keine Uhrzeit oder regelmaessige Automation vereinbart.
- Wetter und Regenradar fuer die Planung der Spaziergaenge mit den Hunden beruecksichtigen.
- Spotify steuern und Musik auf einem gewaehlten Geraet abspielen.
- Gewuenschte App-Aenderungen ueber JayJay beauftragen koennen. Umsetzung ueber einen nachvollziehbaren Entwicklungs-, Test- und Auslieferungsweg; getrennt von normalen Haushaltsaktionen.
- Moeglicherweise eine persoenliche Wissensbasis im Sinn eines LLM-Wikis: bestaetigte Praeferenzen, Routinen, Rezepte und Quellen mit Herkunft und Korrekturmoeglichkeit.
- Unteragenten als moegliche spaetere Architektur untersuchen, wenn getrennte Aufgaben davon profitieren. Noch keine Festlegung auf ein Mehragentensystem.

## Naechste Schritte bleiben

Produkt-/Shop-Grundlage ist ausgeliefert. Es folgen Belegimport mit Pruefansicht, nachgewiesene Warenkorbuebergabe und James-Chat mit denselben Haushaltsrechten und Buchungsregeln. Weitere Integrationen erst anschliessend konkretisieren.


## Architekturentscheid vom 02.11.2026

Bestaetigt: Ein zentraler Butler in der PWA spricht und schreibt mit dem Haushalt. Er ruft direkt Haushaltswerkzeuge und bei Bedarf spaeter Spezialagenten auf. Dieselben Haushaltsservices sollen auch per MCP fuer ChatGPT erreichbar werden. Spezialagenten fuer Einkauf/Browser, Kueche, Alltag und Entwicklung werden erst mit konkreten Aufgaben angeschlossen. Die neue Chat-Grundlage ist textbasiert; Sprache und britische Stimme folgen.

API-Zugang ist noch nicht eingerichtet. Keine Annahme, dass die PWA vorhandene ChatGPT-Chats, Erinnerungen oder Browser-/Shop-Sitzungen uebernimmt. Eigene Rechte, Haushaltsdaten und Agentenzustaende verwalten.

## Chatoberfläche – vereinbart am 04.11.2026

JayJay ist der zentrale persönliche Zugang zu James. Das schwebende Icon öffnet auf dem Smartphone einen fast bildschirmfüllenden Chat, auf grösseren Geräten ein erweiterbares Seitenpanel. Die bestehenden App-Bereiche bleiben erreichbar. Farben, Felder und Buttons verwenden die vorhandene CSS-Basis; Änderungen gehören nach `static/css/jayjay.css`.

Die erste Etappe ergänzt getrennte persönliche Gespräche mit Titeln aus der ersten Nachricht, Verlaufssuche, Umbenennen und Löschen. Modellkontext wird auf das gewählte Gespräch beschränkt. Die Migration gruppiert bisherige Nachrichten je Benutzer/Haushalt als «Bisheriger Verlauf». Gespeicherte Haushaltsaktionen bleiben beim Löschen eines Chats bestehen. Unbestätigte Aufträge lassen sich nicht löschen.

Die Eingabe bleibt unter dem scrollbaren Gespräch. Nachrichtentwürfe bleiben während dieser geöffneten Seite auch beim Wechsel zwischen Chats erhalten; sie werden nicht dauerhaft im Browser gespeichert. Nur die offene Ansicht und eine Gesprächskennung werden pro Benutzer/Sitzung gemerkt. Fehlende Bestätigungen lösen keine automatische Wiederholung eines Auftrags aus.

Ergebniskarten zeigen zunächst nachweislich gespeicherte Artikeländerungen mit Detailansicht und Links zum bestehenden Rücknahmeprozess. Webrecherche, Produkt-/Rezeptkarten und externe Aufträge benötigen ihre jeweiligen Werkzeuge. Die neue Oberfläche schaltet diese Fähigkeiten nicht automatisch frei. Laufende synchrone Haushaltsaufträge dürfen geschlossen, aber noch nicht gezielt gestoppt werden; kein wirkungsloser Stoppknopf.

Nächste Etappen: Diktieren schreibt editierbaren Text in die Eingabe. «Mit JayJay sprechen» startet später ein laufendes Sprachgespräch mit gesprochenen Antworten, Unterbrechung und sichtbaren Mikrofonzuständen. Beide verwenden denselben Gesprächskontext und dieselben Berechtigungen. Bis dahin erscheinen keine scheinbar funktionsfähigen Sprach- oder Anhangbuttons.
