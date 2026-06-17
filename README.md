# Todo-Listen-Verwaltung – Deployment auf einem Raspberry Pi Server

Diese Anleitung beschreibt Schritt für Schritt, wie die Web-Applikation
**Todo-Listen-Verwaltung** auf einem Raspberry Pi mit dem Betriebssystem
**Raspberry Pi OS (Linux)** in Betrieb genommen wird.

Frontend (HTML-Oberfläche) und Backend (REST-API) sind in dieser App nicht
getrennt: Die Python-/Flask-Anwendung liefert beides aus einem einzigen
Docker-Container aus. Es wird also **kein externer Dienst** (z. B. Vercel)
benötigt – das gesamte Repository wird auf den Pi geklont, als Container
gestartet und ist anschließend im Browser über eine URL erreichbar.

Die komplette Einrichtung erfolgt über die Konsole. Alle Einstellungen bleiben
nach einem Neustart erhalten.

---

## Inhaltsverzeichnis

1. [Voraussetzungen](#1-voraussetzungen)
2. [Statische IP-Adresse einrichten](#2-statische-ip-adresse-einrichten)
3. [Benutzer anlegen](#3-benutzer-anlegen)
4. [SSH-Dienst einrichten](#4-ssh-dienst-einrichten)
5. [Docker installieren](#5-docker-installieren)
6. [Repository klonen und Image bauen](#6-repository-klonen-und-image-bauen)
7. [Container starten](#7-container-starten)
8. [Funktionstest im Browser](#8-funktionstest-im-browser)
9. [Hinweise und Fehlerbehebung](#9-hinweise-und-fehlerbehebung)

---

## 1. Voraussetzungen

- Raspberry Pi mit frisch installiertem, **unverändertem Raspberry Pi OS**
- Netzwerkverbindung (LAN) zum lokalen Subnetz
- Zugang zur Konsole, entweder direkt (Monitor + Tastatur) oder per SSH

> **Hinweis zu den IP-Adressen:** In dieser Anleitung wird das Subnetz
> `192.168.24.0/24` verwendet und dem Server die feste Adresse
> `192.168.24.112` zugewiesen. In deinem Netzwerk können IP-Adresse, Gateway
> und DNS-Server abweichen – passe die Werte entsprechend an.

Erster Login (noch über die vom DHCP vergebene Adresse des Pi, hier als
Beispiel `192.168.24.144`):

```bash
ssh pi@192.168.24.144
```

---

## 2. Statische IP-Adresse einrichten

Damit der Server immer unter derselben Adresse erreichbar ist, wird eine
statische IP vergeben. Aktuelles Raspberry Pi OS verwaltet das Netzwerk mit dem
**NetworkManager**, der über das Werkzeug `nmcli` gesteuert wird.

Zuerst den Namen der aktiven Netzwerkverbindung herausfinden:

```bash
nmcli con show
```

In der Spalte `NAME` steht der Verbindungsname (z. B. „Wired connection 1").
Diesen Namen im folgenden Befehl anstelle von `[name]` einsetzen:

```bash
sudo nmcli connection modify "[name]" \
  ipv4.method manual \
  ipv4.addresses 192.168.24.112/24 \
  ipv4.gateway 192.168.24.254 \
  ipv4.dns "172.28.28.3 192.168.24.254" \
  ipv4.dns-search "r324.local" \
  ipv6.method disabled \
  connection.autoconnect yes
```

Bedeutung der Optionen:

| Option | Bedeutung |
|--------|-----------|
| `ipv4.method manual` | IP-Adresse wird fest vergeben (kein DHCP-Server soll die Adresse wieder ändern) |
| `ipv4.addresses` | Feste IP-Adresse inkl. Subnetzmaske (`/24`) |
| `ipv4.gateway` | Standard-Gateway (Router) |
| `ipv4.dns` | DNS-Server für die Namensauflösung |
| `ipv4.dns-search` | Lokale Such-Domäne |
| `ipv6.method disabled` | IPv6 wird deaktiviert |
| `connection.autoconnect yes` | Verbindung wird nach dem Neustart automatisch aufgebaut |

Die Einstellungen werden dauerhaft gespeichert und bleiben nach einem Neustart
erhalten. Zum Übernehmen die Verbindung neu aufbauen:

```bash
sudo nmcli connection down "[name]"
sudo nmcli connection up "[name]"
```

Anschließend den Pi neu starten und über die neue Adresse verbinden:

```bash
sudo reboot
```

```bash
ssh pi@192.168.24.112
```

---

## 3. Benutzer anlegen

Es werden zwei lokale Benutzer angelegt:

- **`willi`** – normaler Benutzer **ohne** Administratorrechte
- **`fernzugriff`** – Benutzer für die Administration von außen **mit**
  sudo-Rechten

Normalen Benutzer anlegen (interaktiv wird ein Passwort abgefragt):

```bash
sudo adduser willi
```

Administrativen Benutzer anlegen und ihm sudo-Rechte geben:

```bash
sudo adduser fernzugriff
sudo usermod -aG sudo fernzugriff
```

Der Befehl `usermod -aG sudo` fügt den Benutzer der Gruppe `sudo` hinzu. Nur
Mitglieder dieser Gruppe dürfen administrative Befehle ausführen. `willi` bleibt
bewusst außen vor und hat damit keine Administratorrechte. Eigentlich mag ich willi aber, also kannst du ihm ja auch Adminrechte gben wenn du willst.

---

## 4. SSH-Dienst einrichten

Über SSH kann der Server aus der Ferne über die Konsole administriert werden.

Den SSH-Dienst dauerhaft aktivieren (Autostart) und sofort starten:

```bash
sudo systemctl enable ssh
sudo systemctl start ssh
```

`enable` sorgt dafür, dass der Dienst auch nach einem Neustart automatisch
läuft. Anschließend die Konfiguration anpassen:

```bash
sudo nano /etc/ssh/sshd_config
```

Folgende Einträge setzen bzw. anpassen:

```text
PermitRootLogin no
PasswordAuthentication yes
AllowUsers fernzugriff
```

Bedeutung:

| Eintrag | Bedeutung |
|---------|-----------|
| `PermitRootLogin no` | Direkter Login als `root` ist verboten (Sicherheit) |
| `PasswordAuthentication yes` | Anmeldung per Passwort ist erlaubt |
| `AllowUsers fernzugriff` | Nur der Benutzer `fernzugriff` darf sich per SSH anmelden |

Datei in `nano` speichern mit `Strg + O`, bestätigen mit `Enter`, schließen mit
`Strg + X`. Danach den Dienst neu starten, damit die Änderungen greifen:

```bash
sudo systemctl restart ssh
```

Ab jetzt erfolgt die Administration über den Benutzer `fernzugriff`:

```bash
ssh fernzugriff@192.168.24.112
```

---

## 5. Docker installieren

Die Web-App wird als **Docker-Container** betrieben. Dafür wird Docker
installiert.

Optional: Falls die Systemuhr falsch ist (z. B. ohne Internet beim ersten
Start), kann das Datum manuell gesetzt werden. Eine korrekte Uhrzeit ist nötig,
damit `apt` und Docker keine Zertifikatsfehler werfen:

```bash
sudo date --set='2026-06-17 10:00:00'
```

Paketquellen aktualisieren und Docker installieren:

```bash
sudo apt update
sudo apt install docker.io
```

Docker-Dienst dauerhaft aktivieren (Autostart nach Neustart) und starten:

```bash
sudo systemctl enable docker
sudo systemctl start docker
```

Installation testen:

```bash
sudo docker run hello-world
```

Wenn eine Begrüßungsmeldung erscheint, funktioniert Docker korrekt.

### Was tun, wenn der Docker-Test fehlschlägt?

Erscheint **keine** Begrüßungsmeldung, helfen folgende Prüfschritte:

- **Docker-Dienst läuft nicht** – Status prüfen und ggf. starten:

  ```bash
  sudo systemctl status docker
  sudo systemctl start docker
  sudo systemctl enable docker
  ```

- **Kein Internet / DNS-Problem** (das Image kann nicht heruntergeladen werden):

  ```bash
  ping -c 3 8.8.8.8        # Internet vorhanden?
  ping -c 3 google.com     # DNS funktioniert?
  ```

  Geht die IP-Adresse, aber nicht der Name, die DNS-Einstellungen aus Schritt 2
  prüfen.

- **Zertifikatsfehler (`x509` / `certificate`)** durch eine falsche Systemuhr –
  Datum manuell setzen:

  ```bash
  sudo date --set='2026-06-17 10:00:00'
  ```

- **„permission denied"** – `sudo` wurde vergessen:

  ```bash
  sudo docker run hello-world
  ```

- **Genaue Fehlerursache ansehen** im Docker-Log:

  ```bash
  sudo journalctl -u docker -n 50
  ```

---

## 6. Repository klonen und Image bauen

Das gesamte Projekt (Frontend, Backend, Dockerfile, OpenAPI-Spezifikation) wird
direkt aus dem Git-Repository auf den Server geholt.

Falls `git` noch nicht installiert ist:

```bash
sudo apt install git
```

Repository klonen (URL durch die Adresse deines Repositorys ersetzen):

```bash
git clone <REPO-URL>
```

In das geklonte Verzeichnis wechseln und den Inhalt prüfen:

```bash
cd ToDoListenVerwaltungsFreakApp
ls
```

Erwarteter Inhalt (Auszug):

```text
DockerFile  TodoListManagement.py  Todolistenverwaltung_Vorlage.yaml
OpenAPISpecifications  static/  templates/  README.md
```

Docker-Image aus dem `DockerFile` bauen. Der Punkt am Ende steht für das
aktuelle Verzeichnis als Build-Kontext, `-t app` vergibt den Namen („Tag")
`app`:

```bash
sudo docker image build -t app -f DockerFile .
```

> **Hinweis:** Die Datei heißt in diesem Repository `DockerFile` (mit großem
> „F") und nicht `Dockerfile`. Deshalb wird sie mit `-f DockerFile` explizit
> angegeben.

Gebautes Image prüfen:

```bash
sudo docker images
```

In der Liste sollte ein Eintrag `app` mit dem Tag `latest` erscheinen.

---

## 7. Container starten

Den Container aus dem Image starten:

```bash
sudo docker run -p 5000:5000 -d --restart=always app
```

Bedeutung der Optionen:

| Option | Bedeutung |
|--------|-----------|
| `-p 5000:5000` | Leitet Port 5000 des Pi auf Port 5000 im Container (die App lauscht dann auf diesen Port) |
| `-d` | Startet den Container im Hintergrund (detached) |
| `--restart=always` | Startet den Container nach einem Neustart oder Absturz automatisch neu |

Die Option `--restart=always` ist wichtig, damit die Web-App – wie gefordert –
auch nach einem Neustart des Servers automatisch wieder verfügbar ist.

Laufende Container anzeigen:

```bash
sudo docker ps
```

---

## 8. Funktionstest im Browser

Die App ist nun im lokalen Netzwerk über die statische IP-Adresse und Port
`5000` erreichbar. Auf einem beliebigen Rechner im selben Netzwerk im Browser
aufrufen:

```text
http://192.168.24.112:5000
```

Es sollte die Startseite der Todo-Listen-Verwaltung mit den vorhandenen Listen
und Einträgen erscheinen.

**Neustart-Test:** Zur Kontrolle der Persistenz den Pi neu starten und die URL
erneut aufrufen – die App muss ohne weiteres Zutun wieder erreichbar sein:

```bash
sudo reboot
```

---

## 9. Hinweise und Fehlerbehebung

- **Container-Logs ansehen** (bei Problemen hilfreich):

  ```bash
  sudo docker ps          # Container-ID herausfinden
  sudo docker logs <ID>   # Ausgabe der App anzeigen
  ```

- **Seite lädt, aber Oberfläche fehlt / Template-Fehler:** Das `DockerFile`
  kopiert im Auslieferungszustand den Ordner `template/`, der eigentliche Ordner
  im Repository heißt aber `templates/`. Wird die Oberfläche nicht angezeigt,
  im `DockerFile` die Zeile

  ```dockerfile
  COPY template/ template/
  ```

  in

  ```dockerfile
  COPY templates/ templates/
  ```

  ändern und das Image neu bauen (Schritt 6).

- **Port bereits belegt:** Läuft bereits ein Container auf Port 5000, diesen
  zuerst stoppen:

  ```bash
  sudo docker ps
  sudo docker stop <ID>
  ```

- **App lauscht intern auf Port 5000:** In `TodoListManagement.py` ist
  `host='0.0.0.0', port=5000` gesetzt. `0.0.0.0` bedeutet, dass die App von
  außen (nicht nur lokal) erreichbar ist – Voraussetzung für den Zugriff über
  das Netzwerk.

- **Geklontes Repository wieder löschen:** Solltest du mal Mist bauen beim anlegen der Dateien, kannsts du auch die Dateien wieder        löschen. Um das zu tun musst du gezielt den Projektordner löschen. Also musst du zuerst eine Ebene
  über das Git-Verzeichnis wechseln (z. B. ins Home-Verzeichnis):

  ```bash
  cd ..
  rm -rf ToDoListenVerwaltungsFreakApp
  ```

  `rm -rf` löscht das angegebene Verzeichnis samt allen Unterordnern und Dateien
  ohne Rückfrage. `rmdir` allein funktioniert hier **nicht**, weil es nur
  **leere** Verzeichnisse entfernt.

- **Uhrzeit nach Neustart wieder falsch:** Der Raspberry Pi besitzt **keine
  batteriegepufferte Echtzeituhr (RTC)**. Ohne Internetverbindung steht nach
  jedem Neustart wieder ein falsches Datum, wodurch `apt` und Docker
  Zertifikatsfehler werfen können. Entweder eine Internetverbindung
  sicherstellen (dann wird die Zeit per NTP automatisch gesetzt) oder das Datum
  nach jedem Start manuell setzen (siehe Schritt 5):

  ```bash
  sudo date --set='2026-06-17 10:00:00'
  ```

- **Kein SSH-Login mehr möglich:** Durch `AllowUsers fernzugriff` darf sich nur
  noch dieser Benutzer per SSH anmelden – ein Tippfehler im Namen oder in der
  Datei `sshd_config` sperrt dich aus. Vor dem Neustart des Dienstes die
  Konfiguration immer testen:

  ```bash
  sudo sshd -t
  ```

  Meldet der Befehl keinen Fehler, ist die Datei in Ordnung. Im Notfall die
  Korrektur direkt am Gerät (Monitor + Tastatur) vornehmen.

- **Zu wenig Speicherplatz auf der SD-Karte:** Bricht der Image-Bau mit
  `no space left on device` ab, ist die Karte voll. Belegung prüfen und nicht
  mehr benötigte Docker-Daten (alte Images, gestoppte Container) entfernen:

  ```bash
  df -h                          # freien Speicher anzeigen
  sudo docker system prune -a    # ungenutzte Images/Container löschen
  ```

- **Container läuft nicht / beendet sich sofort:** `sudo docker ps` zeigt nur
  **laufende** Container. Mit `-a` werden auch gestoppte angezeigt; die Logs
  verraten die Ursache:

  ```bash
  sudo docker ps -a
  sudo docker logs <ID>
  ```

- **Daten gehen nach Neuaufbau verloren:** Die Todo-Daten liegen **innerhalb**
  des Containers. Wird der Container gelöscht und neu gestartet, sind die
  Einträge weg. Sollen die Daten dauerhaft erhalten bleiben, muss ein Docker-
  **Volume** eingebunden werden (`-v`), das die Daten außerhalb des Containers
  speichert.

- **Statische IP-Adresse bereits vergeben:** Liegt die gewählte Adresse bereits
  bei einem anderen Gerät oder im DHCP-Bereich des Routers, kommt es zu
  Adresskonflikten (zeitweise nicht erreichbar). Vor der Vergabe von einem
  anderen Rechner prüfen, ob die Adresse frei ist:

  ```bash
  ping 192.168.24.112
  ```

  Antwortet niemand, ist die Adresse vermutlich frei.

- **Firewall blockiert Port 5000:** Ist eine Firewall wie `ufw` aktiv, kann der
  Zugriff aus dem Netzwerk blockiert sein. Port freigeben:

  ```bash
  sudo ufw allow 5000/tcp
  ```

---

## Projektstruktur

| Datei / Ordner | Inhalt |
|----------------|--------|
| `TodoListManagement.py` | Python-/Flask-Anwendung (Backend + Auslieferung des Frontends) |
| `DockerFile` | Bauanleitung für das Docker-Image |
| `templates/` | HTML-Seiten der Weboberfläche |
| `static/` | CSS / statische Dateien |
| `OpenAPISpecifications`, `Todolistenverwaltung_Vorlage.yaml` | OpenAPI-Spezifikation der REST-API |
| `README.md` | Diese Anleitung |
