"""Ermittelt die aktuellen Rechenwerte aus allen Webquellen und schreibt sie
als werte.json – für die Webversion (Deutschland) (läuft z. B. täglich über GitHub Actions).

Aufruf:  python werte_ermitteln.py [ziel.json]
Basis für die Plausibilitätsgrenzen sind die zuletzt ermittelten Werte
(falls die Zieldatei existiert), sonst die eingebauten Standardwerte.
"""

import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import berechnung  # noqa: E402
import websuche  # noqa: E402

FORMAT = "pensionszuverdienstrechner-de-werte"


def main():
    ziel = sys.argv[1] if len(sys.argv) > 1 else "werte.json"
    basis = dict(berechnung.PARAMETER_STANDARD)
    basis_jahr = 2026
    try:
        with open(ziel, encoding="utf-8") as f:
            alt = json.load(f)
        if alt.get("format") == FORMAT:
            basis_jahr = int(alt.get("jahr") or basis_jahr)
            for k, v in alt.get("werte", {}).items():
                if k in basis and v.get("jahr_ok"):
                    basis[k] = float(v["wert"])
    except (OSError, ValueError):
        pass

    jahr, erg, quellen, fehler = websuche.ermitteln(
        basis, basis_jahr, fortschritt=lambda i, n, name: print(f"[{i + 1}/{n}] {name}"))
    daten = {
        "format": FORMAT,
        "version": 1,
        "erstellt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "jahr": jahr,
        "quellen": quellen,
        "fehler": fehler,
        "werte": {k: {"wert": v["wert"], "jahr_ok": v["jahr_ok"], "kontext": v["kontext"][:400],
                      "quellen": v["quellen"]} for k, v in erg.items()},
    }
    if not daten["werte"]:
        print("Keine Werte gefunden – Datei bleibt unverändert.", fehler)
        return 1
    with open(ziel, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=1)
    bestaetigt = sum(1 for v in erg.values() if v["jahr_ok"])
    print(f"{len(erg)} Werte für {jahr} gefunden ({bestaetigt} mit passender Jahresangabe) -> {ziel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
