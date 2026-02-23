# =============================================================================
# FiveM Cache Cleaner
# -----------------------------------------------------------------------------
# Löscht die FiveM-Cache-Ordner und startet FiveM danach automatisch neu.
#
# Gelöscht werden NUR:  cache | server-cache | server-cache-priv
# Unverändert bleibt:   game-storage  (kein erneuter Spieldaten-Download)
#
# Pfad-Erkennung (Reihenfolge):
#   1. Windows-Standardpfad  (%LOCALAPPDATA%\FiveM)
#   2. Gespeicherter Pfad    (%APPDATA%\FiveMCacheCleaner\config.json)
#   3. Vollständiger PC-Scan aller vorhandenen Laufwerke
# =============================================================================

import os
import sys
import shutil
import subprocess
import json
import string
import time
from pathlib import Path


# ── Konstanten ────────────────────────────────────────────────────────────────

VERSION = "1.0.0"

# Nur diese drei Ordner werden gelöscht – game-storage bleibt unangetastet.
CACHE_FOLDERS = ["cache", "server-cache", "server-cache-priv"]

# Standard-Installationspfad von FiveM unter Windows.
DEFAULT_FIVEM_PATH = Path(os.environ.get("LOCALAPPDATA", "")) / "FiveM"

# Speicherort für die Konfigurationsdatei (gefundener FiveM-Pfad).
CONFIG_DIR  = Path(os.environ.get("APPDATA", "")) / "FiveMCacheCleaner"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Systemordner, die beim PC-Scan übersprungen werden (irrelevant + langsam).
SKIP_DIRS = {"windows", "system32", "syswow64", "$recycle.bin", "recovery", "perflogs"}


# ── Ausgabe-Hilfsfunktionen ───────────────────────────────────────────────────

def print_header():
    """Gibt den Programm-Header mit Versionsnummer in der Konsole aus."""
    print("=" * 55)
    print(f"   FiveM Cache Cleaner  v{VERSION}")
    print("   github.com/xmaxxi02/Fivem-Cache-Cleaner")
    print("=" * 55)
    print()


def print_status(symbol: str, message: str):
    """Gibt eine formatierte Statuszeile aus, z. B. '  [OK] Cache gelöscht'."""
    print(f"  [{symbol}] {message}")


# ── Konfiguration ─────────────────────────────────────────────────────────────

def save_config(fivem_path: Path):
    """
    Speichert den gefundenen FiveM-Pfad in der Konfigurationsdatei.
    Verhindert, dass beim nächsten Programmstart ein erneuter PC-Scan
    nötig ist.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps({"fivem_path": str(fivem_path)}, indent=2),
        encoding="utf-8",
    )


def load_config() -> Path | None:
    """
    Liest den gespeicherten FiveM-Pfad aus der Konfigurationsdatei.
    Gibt None zurück, wenn die Datei fehlt, beschädigt ist oder
    der gespeicherte Pfad nicht mehr existiert.
    """
    if not CONFIG_FILE.exists():
        return None
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        path = Path(data.get("fivem_path", ""))
        # Sicherheitscheck: Pfad muss noch gültig sein
        if (path / "FiveM.exe").exists():
            return path
    except (json.JSONDecodeError, OSError):
        # Beschädigte oder nicht lesbare Config wird stillschweigend ignoriert
        pass
    return None


# ── Laufwerke ermitteln ───────────────────────────────────────────────────────

def get_all_drives() -> list[str]:
    """
    Gibt eine Liste aller vorhandenen Laufwerksbuchstaben zurück (A–Z).
    Nicht vorhandene Laufwerke werden übersprungen.
    Beispiel-Rückgabe: ['C:\\', 'D:\\', 'E:\\']
    """
    return [
        f"{letter}:\\"
        for letter in string.ascii_uppercase
        if os.path.exists(f"{letter}:\\")
    ]


# ── FiveM-Pfad ermitteln ──────────────────────────────────────────────────────

def find_fivem_path() -> Path | None:
    """
    Sucht den FiveM-Installationspfad in drei Stufen:

    1. Standardpfad  – schnellste Prüfung, trifft für die meisten User zu.
    2. Config-Datei  – gespeichertes Ergebnis eines früheren Scans.
    3. PC-Scan       – durchsucht alle Laufwerke nach 'FiveM.exe'.
                       Das Ergebnis wird für künftige Starts gespeichert.

    Gibt den Pfad zum FiveM-Verzeichnis zurück oder None, falls nicht gefunden.
    """

    # Stufe 1: Standardpfad prüfen (%LOCALAPPDATA%\FiveM)
    if (DEFAULT_FIVEM_PATH / "FiveM.exe").exists():
        return DEFAULT_FIVEM_PATH

    # Stufe 2: Gespeicherten Pfad aus vorherigem Scan laden
    saved = load_config()
    if saved:
        print_status("i", f"FiveM-Pfad aus Konfiguration geladen: {saved}")
        return saved

    # Stufe 3: Vollständiger PC-Scan aller vorhandenen Laufwerke
    print_status("!", "FiveM nicht im Standardpfad gefunden.")
    print_status("~", "Starte Suche auf allen Laufwerken...")
    print()

    for drive in get_all_drives():
        # Aktuell durchsuchtes Laufwerk anzeigen (\r überschreibt die Zeile)
        print(f"  Durchsuche {drive} ...", end="\r", flush=True)
        try:
            for root, dirs, files in os.walk(drive, followlinks=False):
                # Irrelevante Systemordner aus der Suche ausschließen.
                # Die In-Place-Änderung von dirs[] steuert, welche
                # Unterordner os.walk als nächstes besucht.
                dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS]

                if "FiveM.exe" in files:
                    found = Path(root)
                    # Leerzeichen am Ende überschreiben den \r-Statustext
                    print(f"  Durchsuche {drive} ...          ")
                    # Pfad speichern – kein Re-Scan beim nächsten Start
                    save_config(found)
                    return found

        except PermissionError:
            # Gesperrte Systemverzeichnisse einfach überspringen
            continue

    print()
    return None  # FiveM auf keinem Laufwerk gefunden


# ── Cache löschen ─────────────────────────────────────────────────────────────

def clean_cache(fivem_path: Path) -> int:
    """
    Löscht die drei Cache-Ordner innerhalb von FiveM.app.
    game-storage wird bewusst NICHT gelöscht, damit der User
    die Spieldaten nicht neu herunterladen muss.

    Gibt die Anzahl der erfolgreich gelöschten Ordner zurück.
    """
    # Alle Cache-Ordner liegen unter FiveM.app\
    app_dir = fivem_path / "FiveM.app"
    deleted = 0

    if not app_dir.exists():
        print_status("!", f"FiveM.app-Verzeichnis nicht gefunden: {app_dir}")
        return 0

    for folder_name in CACHE_FOLDERS:
        folder = app_dir / folder_name
        if folder.exists():
            try:
                shutil.rmtree(folder)  # Ordner inkl. aller Unterordner löschen
                print_status("OK", f"{folder_name} gelöscht")
                deleted += 1
            except OSError as exc:
                # z. B. wenn FiveM noch läuft und Dateien gesperrt sind
                print_status("ERR", f"{folder_name} konnte nicht gelöscht werden: {exc}")
        else:
            # Ordner existiert nicht – kein Fehler, einfach überspringen
            print_status("--", f"{folder_name} nicht vorhanden (bereits leer)")

    return deleted


# ── FiveM starten ─────────────────────────────────────────────────────────────

def launch_fivem(fivem_path: Path) -> bool:
    """
    Startet FiveM.exe als eigenständigen Prozess (non-blocking).
    Das Tool wartet NICHT darauf, dass FiveM beendet wird.
    Gibt True bei Erfolg zurück, False bei einem Fehler.
    """
    exe = fivem_path / "FiveM.exe"
    try:
        # Popen startet den Prozess und kehrt sofort zurück
        subprocess.Popen([str(exe)], cwd=str(fivem_path))
        return True
    except OSError as exc:
        print_status("ERR", f"FiveM konnte nicht gestartet werden: {exc}")
        return False


# ── Einstiegspunkt ────────────────────────────────────────────────────────────

def main():
    # Konsole auf UTF-8 umstellen, damit Umlaute korrekt angezeigt werden
    if sys.platform == "win32":
        os.system("chcp 65001 > nul")

    print_header()

    # ── Schritt 1: FiveM-Pfad ermitteln ───────────────────────────────────────
    fivem_path = find_fivem_path()
    if not fivem_path:
        print()
        print_status("ERR", "FiveM wurde auf keinem Laufwerk gefunden.")
        print()
        print("  Stelle sicher, dass FiveM installiert ist und versuche")
        print("  es erneut. Falls das Problem weiterhin besteht, öffne")
        print("  ein Issue auf GitHub.")
        print()
        input("  Enter drücken zum Beenden...")
        sys.exit(1)

    print_status("OK", f"FiveM gefunden: {fivem_path}")
    print()

    # ── Schritt 2: Cache löschen ──────────────────────────────────────────────
    print("  Cache wird gelöscht...")
    print()
    deleted_count = clean_cache(fivem_path)
    print()

    if deleted_count > 0:
        print_status("OK", f"{deleted_count} Cache-Ordner erfolgreich gelöscht.")
    else:
        print_status("--", "Kein Cache gefunden – bereits sauber.")

    print()

    # ── Schritt 3: FiveM starten ──────────────────────────────────────────────
    print("  Starte FiveM...")
    if launch_fivem(fivem_path):
        print_status("OK", "FiveM wurde gestartet.")
    print()
    print("=" * 55)
    print()

    # Countdown, damit der User die Ausgabe noch lesen kann
    for remaining in range(3, 0, -1):
        print(f"  Fenster schließt sich in {remaining} Sekunde(n)...", end="\r", flush=True)
        time.sleep(1)


if __name__ == "__main__":
    main()
