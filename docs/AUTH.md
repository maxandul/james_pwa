# Zugang und Einladungen

Stand: 01.11.2026. E-Mail und Passwort mit einladungsbasierter Registrierung wurden im Gespraech bestaetigt.

## Eingefuehrter Ablauf

1. Betreiber legt mit `flask --app james init-household` den ersten Haushalt und Owner an. Passwort wird verdeckt und mit Wiederholung abgefragt, nicht als Befehlsargument.
2. Owner erstellt auf "Zusammen nutzen" eine an eine E-Mail gebundene Einladung.
3. Der einmal angezeigte Link wird vom Owner persoenlich weitergegeben. Es werden keine E-Mails automatisch versandt.
4. Eingeladene Person richtet mit derselben E-Mail, Name und Passwort den Zugang ein und meldet sich danach an.

Pro User wird in dieser ersten Oberflaeche genau eine Mitgliedschaft unterstuetzt. Weitere Haushalte/Haushaltswechsel und Beitritt mit einem bestehenden User sind noch nicht implementiert.

## Schutz und Rechte

- Passwort 12 bis 128 Zeichen; Werkzeug-Scrypt mit individuellem Salt. Kein Klartextpasswort in der Datenbank.
- Anmeldung gibt fuer unbekannte Adresse und falsches Passwort dieselbe Fehlermeldung. Dauerhafte Datenbanklimits: hoechstens acht Versuche pro Adresse und 40 pro Socket-IP innerhalb von 15 Minuten. Erfolgreiche Versuche zaehlen ebenfalls; wechselnde Prozesse umgehen das Limit nicht.
- Hinter einem Proxy kann die Socket-IP gemeinsam sein. Vor Deployment Proxy-Topologie pruefen; untrusted X-Forwarded-For wird nicht ausgewertet. Gegebenenfalls nur dokumentierte, vertrauenswuerdige Proxy-Hops konfigurieren und Limits passend pruefen.
- Sitzungen sind HttpOnly und SameSite=Lax, in Produktion Secure. Sie enthalten User-ID und Auth-Version, keine Shop-Zugaenge. Neue Anmeldung leert die bisherige Sitzung.
- Einladungen nutzen einen zufaelligen 256-Bit-Token; nur dessen SHA-256 steht in der DB. Einmal verwendbar, sieben Tage gueltig, widerrufbar. Neuausstellen fuer dieselbe Adresse im Haushalt widerruft vorherige offene Einladungen.
- Link traegt den Token im Fragment, damit er nicht im normalen HTTP-URL-Log landet. Das lokale Script uebernimmt ihn ins Formular und entfernt das Fragment aus der aktuellen Browser-History. Akzeptieren erfolgt per CSRF-geschuetztem POST.
- Offene Einladung ist nur gueltig, solange die ausstellende Owner-Mitgliedschaft aktiv ist. Einladungserstellung und Widerruf sind nur fuer Owner zulaessig.
- Mitglieder koennen gemeinsame Artikel und Liste verwalten. Alle Datenzugriffe pruefen den Haushalt auf dem Server.
- Reset und Sperre siehe Runbook. Nach Passwortreset werden bestehende Sitzungen durch erhoehte Auth-Version ungueltig.

## Bewusst noch offen

Kein automatischer Mailversand, kein "Passwort vergessen" per E-Mail, kein Tablet-Geraetezugang und keine Shop-/Bestellrechte. Bis dahin kann das Tablet nur mit einem persoenlichen Zugang verwendet werden; ein gemeinsam angemeldeter persoenlicher Zugang erfuellt die geplante Geraetetrennung noch nicht.

Die Basis ist vor einem oeffentlichen Alltagseinsatz auf der tatsaechlichen HTTPS-/Proxy-Umgebung und den Zielgeraeten zu pruefen. Keine echten Zugangsdaten in Demo-Fixtures einsetzen.
