# Shop-Anmeldepilot in der gehosteten PWA

Implementiert, noch nicht auf Railway bereitgestellt oder aktiviert. Kein neuer
kostenpflichtiger API-Test in dieser Etappe. Der einmalig genehmigte
Gastwarenkorbtest bleibt der bisherige Live-Nachweis.

## Nutzerablauf

Nach bewusster Aktivierung erscheint in James **Shop-Anmeldung**. Die Seite
erklaert die API-Kosten, das fehlende garantierte Geldlimit und das
sechsminuetige Abbruch-/Bereinigungsbudget. Die Person bestaetigt jeden Test
mit einer eigenen Checkbox. Erst dieser CSRF-geschuetzte POST stellt einen
Auftrag in die Warteschlange. Ein GET startet keinen Browser. Gleiche
Anfragekennung erzeugt keinen zweiten Auftrag; ein offener/ungeklaerter Test
sperrt einen weiteren. Hoechstens zwei vorgemerkte Tests pro Person/UTC-Tag.

Der separate Pilotdienst uebernimmt genau einen Auftrag atomar und startet
den API-Browser. Sobald dieser eine registrierte Galaxus-Anmeldung anfordert,
erscheint das Eingabeformular auf der persoenlichen Statusseite. Die Person
aktualisiert die Seite bei Bedarf selbst, damit keine Eingaben durch einen
automatischen Refresh verloren gehen. Weitere Login-Schritte, etwa MFA,
erscheinen als neue Anforderungen. Eingaben werden nicht erneut vorausgefuellt.

Die Maske erlaubt nur den exakten Credential-Origin `https://www.galaxus.ch`.
Andere SSO-/Login-Origins stoppen den Pilot; sie werden nicht ungeprueft
freigegeben. Das Ziel und die Uebermittlung an den OpenAI-gehosteten Browser
muessen vor dem Absenden bestaetigt werden. Passwoerter und Codes gehoeren
niemals in den JayJay-Chat.

Der derzeitige Auftrag testet nur eine bestehende Anmeldung. Keine
Kontoerstellung, Aenderung von Kontoeinstellungen, Warenkorbaenderung oder
Bestellung. Ein abgeschlossener API-Turn oder eine angenommene Eingabe ist
kein unabhaengiger Beleg fuer einen erfolgreichen Login. Die Sitzung wird
nach dem Test geloescht. Kontoverknuepfung und persoenliche Warenkorbübergabe
sind damit noch nicht dauerhaft implementiert.

## Persistenz und Zugriff

`ShopLogin` speichert UUID-Referenz, Auftragskennung, Person, Haushalt,
Auth-Version, API-Sitzungs-/Anforderungsreferenzen, Kostenfreigabezeitpunkt,
Fristen und Zustand. Keine Anmeldedaten, Cookies, Modelltexte oder Bilder.
Ein eindeutiger aktiver Nutzer-Slot verhindert parallele Tests auch ueber
mehrere Webworker hinweg. Geschlossene Auftraege geben diesen Slot frei.

Jeder Zugriff prueft Person, Haushalt und Auth-Version erneut. Andere
Haushaltsmitglieder sehen die Anmeldung nicht. Vor einer Uebermittlung wird
die aktuelle API-Anforderung erneut gelesen und nach dem HTTP-Aufruf die
Identitaet und Frist nochmals geprueft. Eine atomare Reservierung auf
`submitting` verhindert doppelte Credential-POSTs. Kein DB-Lock bleibt
waehrend einer HTTP-Anfrage offen. Bei unklarem Ergebnis wird nicht erneut
uebermittelt. Rohantworten und Exceptiontexte werden nicht weitergegeben.

Privates HTML hat `Cache-Control: no-store`; die vorhandenen Service-Worker-
Regeln cachen die Loginseiten oder POSTs nicht. Das Abmelden markiert aktive
Tests als abgebrochen. Der separate Observer bemerkt auch Rechtewechsel,
Auth-Version-Wechsel und Fristablauf und fordert Cancellation an.

## Betrieb und Bereinigung

Der beaufsichtigte Dienst laeuft mit:

```bash
flask --app james shop-login-worker --watch
```

Er prueft die Queue etwa alle 30 Sekunden, bearbeitet jeweils einen Test und
gleicht abgebrochene, unklare und abgelaufene Sitzungen ab. Nach Neustart wird
ein bereits begonnener Auftrag **nicht** automatisch neu erstellt. Falls der
Prozess nach API-Erstellung, aber vor dem Speichern der Sitzungs-ID starb,
wird ueber eine eindeutige UUID in API-Metadaten abgeglichen. Ein ungeklaerter
Abgleich bleibt `cleanup_pending` und sperrt einen neuen Test dieser Person.
Der begrenzte Abgleich liest die letzten 100 Sitzungen; aeltere oder nicht
auffindbare Faelle brauchen Betreiberpruefung.

Cancellation und Loeschung sind getrennte API-Aufrufe. Eine Loeschung kann
bei noch aktivem Turn oder Netzfehler scheitern; dann bleibt die Bereinigung
offen und wird beim naechsten Durchlauf erneut geprueft. Das ist weiterhin
kein hartes Kostenlimit. Bei einem laufenden Pilot kann der Queue-Dienst
bis zum Testende beschaeftigt sein; beim Ausfall des gesamten Dienstes ist
die Bereinigung bis zu dessen Wiederanlauf verzoegert. Ein Betreiber muss
Fehler/Restart und `cleanup_pending` ueberwachen. Einmaliger Abgleich:

```bash
flask --app james shop-login-cleanup
```

Der API-Schluessel bleibt ausschliesslich in den bestehenden geschuetzten
Laufzeitvariablen. Der zusaetzliche Railway-Dienst verwendet Referenzen auf
dieselben James-Ressourcen; keine Geheimnisse in Konfigurationsdateien oder
Werkzeugausgaben. Er benoetigt keine oeffentliche Domain und keinen Zugriff
auf die persoenliche ChatGPT-Browsersitzung.

## Bereitstellung und Abnahme

`deployment/shop-login-worker.json` beschreibt die vorbereitete Zielkonfiguration,
wird aber nicht automatisch von Railway angewandt. Die Bereitstellung braucht
einen zusaetzlichen kleinen, dauerhaft beaufsichtigten Railway-Dienst und
verursacht dort Infrastrukturkosten. Er wurde noch nicht angelegt.

1. CI und Migration pruefen. Web-Code und neue Tabelle zunaechst bei
   `SHOP_LOGIN_PILOT_ENABLED=0` bereitstellen.
2. Den Pilotdienst mit einer Replik, Restart-Verhalten und denselben
   James-Konfigurationsreferenzen einrichten. Queue-/Restart-/Bereinigungs-
   pruefung ohne neue API-Sitzung durchfuehren.
3. Erst danach bewusst aktivieren. Der naechste bezahlte Loginversuch wird
   von der Person selbst in der PWA separat bestaetigt. Die bisherige
   Einzelgenehmigung deckt ihn nicht ab.
4. Login/MFA/Abbruch am echten Konto, Smartphone und Tablet pruefen. Dann
   erst angemeldeten Warenkorb, Wiederholungen und die Uebergabe auf das
   persoenliche Geraet untersuchen.

Der laufende James-Service, seine Konfiguration und die Datenbank wurden in
dieser Implementierungsetappe noch nicht veraendert. Die neue Migration
liegt als eigener Schema-Commit vor.
