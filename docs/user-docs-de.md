# Eyestream — Benutzerhandbuch

> Dieses Handbuch erklärt, wie du Videos hochlädst, verwaltest und auf der Website oder in der Wissensdatenbank einbindest.

> **Hinweis:** Der Zugriff auf die Video-Verwaltung ist auf freigegebene Personen beschränkt. Wenn du keinen Zugang hast, wende dich an die IT.

## Anmeldung

Öffne die Admin-URL und melde dich mit deinem Konto an.

> **Screenshot-Vorschlag:** Login-Splash-Screen mit Logo und Flammen-Animation.

## Videos hochladen

1. Klicke oben rechts auf **Video hochladen**
2. Ziehe die Videodatei in den Upload-Bereich oder klicke auf **Datei wählen**
3. Wähle den **Bereich** aus (z. B. "Marketing: Website" oder "Wissensdatenbank PSC")
4. Optional: Schreibe eine **Notiz** (z. B. wo das Video eingebunden wird)
5. Klicke auf **Upload starten**

> **Screenshot-Vorschlag:** Upload-Seite mit ausgewählter Datei, Bereich-Dropdown und Notiz.

Nach dem Upload wird das Video automatisch in verschiedenen Qualitätsstufen encodiert. Du kannst den Fortschritt live auf der Übersichtsseite verfolgen.

## Übersicht

Auf der Startseite siehst du alle Videos mit Vorschaubild, Titel und technischen Infos.

> **Screenshot-Vorschlag:** Video-Übersicht mit mehreren Video-Cards.

### Suchen und filtern

- **Suchfeld**: Tippe einen Begriff ein — es werden Vorschläge angezeigt
- **Bereich-Filter**: Wähle einen Bereich aus dem Dropdown, um nur Videos dieses Bereichs zu sehen

### Video bearbeiten

- **Titel ändern**: Doppelklicke auf den Titel oder klicke auf das Stift-Symbol
- **Notiz bearbeiten**: Klicke in das Notizfeld und tippe
- **Bereich ändern**: Klicke auf das orangefarbene Bereich-Dropdown und wähle einen anderen Bereich

### Vorschaubild ändern

1. Klicke auf das Vorschaubild, um den Player zu öffnen
2. Navigiere zur gewünschten Stelle im Video
3. **Pausiere** das Video
4. Klicke auf den Button **Vorschaubild setzen** (erscheint oben im Player)

Das Vorschaubild wird in hoher Qualität direkt aus dem Original-Video erzeugt.

> **Screenshot-Vorschlag:** Video-Player mit pausiertem Video und "Vorschaubild setzen"-Button.

## Videos einbinden

Für jedes Video gibt es zwei URLs:

### URL kopieren (für die Website)

Die Streaming-URL (`.m3u8`) für die technische Einbindung auf der Website. Das Vorschaubild lässt sich ableiten, indem `master.m3u8` durch `poster.jpg` ersetzt wird. Auf der Beispielseite (Link "Beispiel" oben im Header) findest du fertigen Code.

### Player URL kopieren (für die Wissensdatenbank)

Eine fertige Player-Seite mit Vorschaubild. Ideal für **Outline Wiki**:

1. Kopiere die Player-URL
2. Füge sie in Outline ein
3. Klicke auf **Embed**

Das Video wird mit Vorschaubild und Play-Button eingebettet. Beim Darüberfahren mit der Maus werden automatisch Vorschau-Bilder aus dem Video angezeigt.

> **Screenshot-Vorschlag:** Outline Wiki mit eingebettetem Video-Player.

Der **?**-Button neben den Kopier-Buttons öffnet eine Erklärung zu beiden Optionen.

## Video deaktivieren

Du kannst ein Video vorübergehend deaktivieren, ohne es zu löschen. Deaktivierte Videos sind auf der Website und in der Wissensdatenbank nicht mehr abrufbar.

1. Klicke bei dem Video auf **Deaktivieren**
2. Bestätige mit einem zweiten Klick

Das Video wird in der Übersicht mit einem "DEAKTIVIERT"-Banner und schraffiertem Hintergrund markiert. Du kannst es weiterhin abspielen und bearbeiten — nur die öffentliche Auslieferung ist gestoppt.

Zum Reaktivieren klicke auf **Aktivieren**.

## Bereiche

Bereiche helfen bei der Organisation. Jedes Video gehört zu einem Bereich (z. B. "Marketing: Website", "Wissensdatenbank PSC: Tomedo Schulung").

Bereiche verwaltest du unter **Einstellungen** (Zahnrad-Symbol im Header):
- Neuen Bereich anlegen
- Bestehende umbenennen oder löschen
- Klick auf einen Bereich öffnet die gefilterte Video-Übersicht

## Design-Modus

Klicke auf das Sonne/Mond-Symbol im Header, um zwischen hellem, dunklem und automatischem Design zu wechseln:
- ☀ Hell
- ☾ Dunkel
- ◐ Automatisch (folgt deinem System)

## Einträge pro Seite

Rechts in der Seitennavigation kannst du einstellen, wie viele Videos pro Seite angezeigt werden: 10, 20, 50, 100 oder Alle. Die Einstellung wird gespeichert.

## Statistiken

Klicke auf das Diagramm-Symbol im Header, um die Statistik-Seite zu öffnen:
- Anzahl der Videos und Gesamtdauer
- Speicherplatz-Übersicht (Kuchendiagramm)
- Aufrufe der letzten 4 Tage (Trend-Diagramm)
- Top-Websites, die eure Videos einbinden

> **Screenshot-Vorschlag:** Statistik-Seite mit Kacheln, Kuchendiagramm und Trend-Graph.

## Aktivitätslog

Über das Uhr-Symbol im Header erreichst du das Aktivitätslog. Hier siehst du, wer wann welches Video hochgeladen, bearbeitet, deaktiviert oder gelöscht hat.

> **Screenshot-Vorschlag:** Aktivitätslog mit farbigen Einträgen.

## Tipps

- **Vorschau beim Hover**: Bewege die Maus über ein Vorschaubild — es werden automatisch verschiedene Stellen aus dem Video gezeigt
- **Referer-Anzeige**: Die kleinen farbigen Badges auf dem Vorschaubild zeigen, wie oft und von welchen Websites das Video aufgerufen wurde
- **Dauer-Badge**: Unten links auf dem Vorschaubild siehst du die Video-Dauer
- **Schnelle Suche**: Tippe los — Vorschläge erscheinen sofort, auch für Bereiche
