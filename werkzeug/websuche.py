"""Werte aus Webseiten ermitteln – Deutschland (Vorschläge, vom Benutzer zu prüfen).

Lädt eine Seite (HTML oder JSON-Parameterdatei), wandelt sie in Text um und
sucht zu jedem Parameter Zahlen in der Nähe passender Schlüsselwörter.
Die Einkommensteuer-Formel (§ 32a EStG) wird als Ganzes aus dem Gesetzestext
bzw. aus Formelseiten gelesen. Damit nichts Falsches gefunden wird, muss jede
Zahl zum Typ passen (Betrag/Prozent), in einem plausiblen Bereich um den
aktuellen Wert liegen und bevorzugt im Umfeld des gesuchten Jahres stehen.
"""

import bisect
import html
import json
import re
import urllib.request

# (Name, URL mit {jahr}, Inhalt)
WEBQUELLEN = [
    ("Gesetz: § 32a EStG – Einkommensteuertarif", "https://www.gesetze-im-internet.de/estg/__32a.html",
     "Tarifformel, Grundfreibetrag, Tarifgrenzen"),
    ("Gesetz: § 3 SolzG – Solidaritätszuschlag", "https://www.gesetze-im-internet.de/solzg_1995/__3.html",
     "Soli-Freigrenze"),
    ("Gesetz: § 3 EStG – Übungsleiter/Ehrenamt", "https://www.gesetze-im-internet.de/estg/__3.html",
     "Übungsleiterfreibetrag, Ehrenamtspauschale"),
    ("finanz-tools.de – Steuerformeln {jahr}", "https://www.finanz-tools.de/einkommensteuer/berechnung-formeln/{jahr}",
     "Tarifformel des Jahres"),
    ("lohn-info.de – Sozialversicherung {jahr}", "https://lohn-info.de/sozialversicherungsbeitraege{jahr}.html",
     "KV-/PV-/RV-Sätze, Zusatzbeitrag, Beitragsbemessungsgrenzen, Bezugsgröße, Geringfügigkeitsgrenze"),
    ("Haufe – Beitragsbemessungsgrenzen", "https://www.haufe.de/sozialwesen/versicherungen-beitraege/"
     "beitragsbemessungsgrenze_240_421702.html", "Beitragsbemessungsgrenzen KV/PV und RV"),
    ("smart-rechner.de – Hinzuverdienst EM-Rente",
     "https://www.smart-rechner.de/erwerbsminderungsrente/ratgeber/hinzuverdienstgrenze.php",
     "Hinzuverdienstgrenzen volle/teilweise Erwerbsminderung"),
    ("steuertipps.de – Witwenrente",
     "https://www.steuertipps.de/altersvorsorge-rente-finanzen/witwenrente-hoehe-und-anrechnungsfreier-hinzuverdienst",
     "Freibetrag bei Witwen-/Witwerrenten"),
]

TARIF = ["est_g0", "est_g1", "est_g2", "est_g3", "est_a", "est_c1", "est_b", "est_c2", "est_t1",
         "est_k4", "est_k5", "est_s4", "est_s5"]

# key: (Schlüsselwort-Regex, Typ, Toleranz oder (min, max), Fenster in Zeichen)
REGELN = {
    "soli_freigrenze": (r"Solidaritätszuschlag\w*|Freigrenze\w*|in anderen Fällen", "betrag", 0.12, 400),
    "uebungsleiter_max": (r"Übungsleiter\w*", "betrag", (2500, 4500), 1500),
    "ehrenamt_max": (r"26a\. Einnahmen|Ehrenamt\w*", "betrag", (700, 1300), 800),
    "kv_satz": (r"allgemeine\w* Beitragssatz", "prozent", (13, 16), 150),
    "kv_satz_erm": (r"ermäßigte\w* (?:Beitrags)?[Ss]atz", "prozent", (12, 15.5), 150),
    "kv_zusatz": (r"(?:durchschnittliche\w* )?Zusatzbeitrag\w*", "prozent", (1.0, 5.0), 200),
    "pv_satz": (r"Pflegeversicherung", "prozent", (2.5, 5.0), 200),
    "pv_kinderlos": (r"Kinderlose\w*", "prozent", (0.45, 1.5), 250),
    "rv_satz": (r"Rentenversicherung", "prozent", (15.0, 22.0), 200),
    "kv_bbg": (r"Beitragsbemessungsgrenze\w*|BBG", "betrag", 0.08, 300),
    "rv_bbg": (r"Beitragsbemessungsgrenze\w*|BBG", "betrag", 0.08, 300),
    "bezugsgroesse": (r"Bezugsgr\w*", "betrag", 0.10, 200),
    "gfg_monat": (r"Geringfügigkeitsgrenze|Minijob\w*", "betrag", 0.12, 150),
    "em_voll_grenze": (r"volle[rn]? Erwerbsminderung\w*|3/8", "betrag", 0.10, 300),
    "em_teil_min": (r"teilweise[rn]? Erwerbsminderung\w*|6/8", "betrag", 0.10, 300),
    "witwe_freibetrag": (r"Freibetrag\w*", "betrag", 0.10, 200),
    "ku_vorjahr": (r"Kleinunternehmer\w*", "betrag", (20000, 35000), 300),
    "ku_laufend": (r"Kleinunternehmer\w*", "betrag", (80000, 130000), 300),
}

_ZAHL = re.compile(r"(?<![\d.,])(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d+))?(?!\d)(\s*(?:Mio\.?|Million\w*))?")
_PROZENT = re.compile(r"\s*(%|Prozent|vom Hundert)")
_JAHR = re.compile(r"(?<!\d)(20\d\d)(?!\d)")


class Seite:
    """Eine geladene Seite als Text mit vorab ermittelten Zahlen und Jahresangaben."""

    def __init__(self, name, url, text, titel=""):
        self.name, self.url, self.text = name, url, text
        self.titel_jahre = {int(j) for j in _JAHR.findall(titel or "")}
        self.zahlen = []  # (pos, ende, wert, ist_prozent)
        for m in _ZAHL.finditer(text):
            ganz = m.group(1).replace(".", "")
            wert = float(ganz + ("." + m.group(2) if m.group(2) else ""))
            if m.group(3):
                wert *= 1_000_000
            prozent = bool(_PROZENT.match(text, m.end()))
            self.zahlen.append((m.start(), m.end(), wert, prozent))
        self._pos = [z[0] for z in self.zahlen]
        self.jahre = [(m.start(), int(m.group(1))) for m in _JAHR.finditer(text)]
        self._jpos = [j[0] for j in self.jahre]

    def satzanfang(self, pos):
        a = max(self.text.rfind("\n", 0, pos), self.text.rfind(". ", 0, pos))
        return a + 1

    def jahr_score(self, pos, zieljahr):
        """+2: Jahresangabe im selben Satz passt, -2: anderes Jahr im Satz,
        sonst Seitentitel: +1 passt, -1 nur andere Jahre, 0 unbekannt."""
        anfang = self.satzanfang(pos)
        i = bisect.bisect_left(self._jpos, pos) - 1
        while i >= 0 and self.jahre[i][0] >= anfang:
            jp, j = self.jahre[i]
            zwischen = self.text[jp:pos]
            if zwischen.count(")") > zwischen.count("("):
                i -= 1
                continue
            return 2 if j == zieljahr else -2
        if zieljahr in self.titel_jahre:
            return 1 if len(self.titel_jahre) == 1 else 0
        return -1 if self.titel_jahre else 0


def html_zu_text(raw):
    raw = re.sub(r"(?is)<(script|style|noscript|svg).*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<(br|/p|/div|/tr|/li|/h\d|/td|/th|/dt|/dd)[^>]*>", "\n", raw)
    t = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    t = re.sub(r"[ \t\xa0\u202f\u2009]+", " ", t)
    # Tausendertrennung mit Leerzeichen (Gesetzestexte: „12 348 Euro“) → „12.348“
    alt = None
    while alt != t:
        alt = t
        t = re.sub(r"(?<![\d.,])(\d{1,3}(?:\.\d{3})*) (\d{3})(?!\d)", r"\1.\2", t)
    return re.sub(r"\n\s*\n+", "\n", t)


def titel_aus_html(raw):
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw)
    return " ".join(html.unescape(m.group(1)).split()) if m else ""


def laden(url, timeout=15):
    """Lädt URL oder Datei. Liefert ('json', objekt, '') oder ('text', text, titel)."""
    url = url.strip()
    if url.lower().startswith(("http://", "https://", "file:")):
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Pensionszuverdienstrechner-Deutschland",
            "Accept-Language": "de-DE,de;q=0.9"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            daten = r.read()
            zeichensatz = r.headers.get_content_charset() or "utf-8"
        roh = daten.decode(zeichensatz, "replace")
    else:
        with open(url, encoding="utf-8-sig") as f:
            roh = f.read()
    s = roh.lstrip("\ufeff \r\n\t")
    if s.startswith("{"):
        try:
            return "json", json.loads(s), ""
        except ValueError:
            pass
    return "text", html_zu_text(roh), titel_aus_html(roh)


def _passt(wert, prozent, typ, grenze, aktuell):
    if typ == "prozent" and not prozent:
        return False
    if typ == "betrag" and prozent:
        return False
    if isinstance(grenze, tuple):
        lo, hi = grenze
    else:
        lo, hi = aktuell * (1 - grenze), aktuell * (1 + grenze)
    return lo <= wert <= hi


def kandidaten(seite, p_aktuell, zieljahr):
    """{key: {wert: {"jahr": score, "stimmen": n, "abstand": d, "kontext": str}}}"""
    erg = {}
    for key, (kw, typ, grenze, fenster) in REGELN.items():
        aktuell = p_aktuell.get(key)
        if aktuell is None:
            continue
        werte = {}
        for m in re.finditer(kw, seite.text):
            von = bisect.bisect_left(seite._pos, m.end())
            bis = bisect.bisect_left(seite._pos, m.end() + fenster)
            for pos, ende, wert, prozent in seite.zahlen[von:bis]:
                if not _passt(wert, prozent, typ, grenze, aktuell):
                    continue
                score = seite.jahr_score(pos, zieljahr)
                w = werte.setdefault(round(wert, 4), {"jahr": score, "stimmen": 0,
                                                      "abstand": pos - m.end(), "kontext": ""})
                w["stimmen"] += 1
                if score > w["jahr"] or (score == w["jahr"] and pos - m.end() < w["abstand"]) or not w["kontext"]:
                    w["jahr"] = max(w["jahr"], score)
                    w["abstand"] = min(w["abstand"], pos - m.end())
                    a = max(m.start(), pos - 140)
                    w["kontext"] = " ".join(seite.text[a:ende + 50].split())
        if werte:
            erg[key] = werte
    return erg


# ---------------------------------------------------------------------------
# Einkommensteuer-Formel (§ 32a EStG) als Ganzes erkennen
# ---------------------------------------------------------------------------
_N = r"(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d+))?"
_MAL = r"\s*(?:•|·|×|\*|⋅|\\cdot)\s*"


def _zahl(g1, g2):
    return float(g1.replace(".", "") + ("." + g2 if g2 else ""))


def formel(seite, zieljahr):
    """Liefert ({key: wert}, score, kontext) oder None, wenn die Formel nicht vollständig ist."""
    t = seite.text
    t = re.sub(r"\\text\{([^}]*)\}", r"\1", t).replace("\\leq", "≤").replace("\\geq", "≥")
    t = t.replace("\\cdot", "·").replace("–", "-").replace("−", "-")
    w, pos = {}, None
    m = re.search(r"\(\s*" + _N + _MAL + r"y\s*\+\s*" + _N + r"\s*\)" + _MAL + r"y", t)
    if m:
        w["est_a"], w["est_c1"], pos = _zahl(m[1], m[2]), _zahl(m[3], m[4]), m.start()
    m = re.search(r"\(\s*" + _N + _MAL + r"z\s*\+\s*" + _N + r"\s*\)" + _MAL + r"z\s*\+\s*" + _N, t)
    if m:
        w["est_b"], w["est_c2"], w["est_t1"] = _zahl(m[1], m[2]), _zahl(m[3], m[4]), _zahl(m[5], m[6])
    for key_k, key_s, satz in (("est_k4", "est_s4", "0,42"), ("est_k5", "est_s5", "0,45")):
        m = re.search(satz + _MAL + r"(?:x|zvE)\s*-\s*" + _N, t)
        if m:
            w[key_k], w[key_s] = _zahl(m[1], m[2]), float(satz.replace(",", ".")) * 100
    # Eckwerte: Grundfreibetrag und Zonengrenzen aus „von A Euro bis B Euro“ bzw. „A Euro ≤ zvE ≤ B Euro“
    pos_g0 = None
    m = re.search(r"bis\s+" + _N + r"\s*Euro\s*\(Grundfreibetrag\)", t) or \
        re.search(r"y\s*=\s*\(\s*zvE\s*-\s*" + _N + r"\s*\)", t)
    if m:
        w["est_g0"], pos_g0 = _zahl(m[1], m[2]), m.start()
    paare = {}
    for m in re.finditer(r"(?:von\s+)?" + _N + r"\s*Euro\s*(?:bis|≤\s*zvE\s*≤)\s*" + _N + r"\s*Euro", t):
        paare[_zahl(m[1], m[2])] = _zahl(m[3], m[4])
    if "est_g0" in w:
        g = w["est_g0"]
        for key in ("est_g1", "est_g2", "est_g3"):
            if g + 1 in paare:
                g = paare[g + 1]
                w[key] = g
    if not all(k in w for k in ("est_g0", "est_g1", "est_g2", "est_a", "est_c1", "est_b", "est_c2", "est_t1", "est_k4")):
        return None
    score = max(seite.jahr_score(p, zieljahr) for p in (pos_g0, pos) if p is not None)
    kontext = " ".join(t[pos:pos + 220].split()) if pos is not None else ""
    return w, score, kontext


def seiten_laden(zieljahr, fortschritt=None, cache=None):
    """Lädt alle vordefinierten Webquellen für ein Jahr. Liefert (seiten, fehler)."""
    cache = {} if cache is None else cache
    seiten, fehler = [], []
    for i, (name, url, _inhalt) in enumerate(WEBQUELLEN):
        n, u = name.format(jahr=zieljahr), url.format(jahr=zieljahr)
        if fortschritt:
            fortschritt(i, len(WEBQUELLEN), n)
        try:
            if u not in cache:
                cache[u] = laden(u)
            art, inhalt, titel = cache[u]
            if art == "text":
                seiten.append(Seite(n, u, inhalt, titel))
        except Exception as ex:  # Netzwerk, HTTP-Fehler
            fehler.append(f"{n}: {ex}")
    return seiten, fehler


def ermitteln(p_aktuell, param_jahr, heute=None, fortschritt=None, mindest_bestaetigt=20):
    """Sucht aktuelle Werte in allen Quellen und wählt das passende Jahr.
    Ab Oktober wird zuerst das Folgejahr versucht – es gilt nur, wenn dafür mindestens
    `mindest_bestaetigt` Werte (inkl. Steuertarif) mit passender Jahresangabe vorliegen;
    sonst würden Werte zweier Jahre vermischt. Liefert (jahr, ergebnis, quellen, fehler)."""
    import datetime
    h = heute or datetime.date.today()
    basis = max(int(param_jahr or h.year), h.year)
    jahre = [basis + 1, basis] if (h.month >= 10 and basis == h.year) else [basis]
    cache = {}
    for j in jahre:
        seiten, fehler = seiten_laden(j, fortschritt, cache)
        erg = auswerten(seiten, p_aktuell, j)
        if j == jahre[-1] or sum(1 for v in erg.values() if v["jahr_ok"]) >= mindest_bestaetigt:
            return j, erg, [s.name for s in seiten], fehler
    return jahre[-1], {}, [], []


def auswerten(seiten, p_aktuell, zieljahr):
    """Ermittelt je Parameter den besten Wert über alle Seiten.
    Liefert {key: {"wert", "quellen": [namen], "kontext", "jahr_ok", "stimmen"}}."""
    gesammelt = {}
    formeln = []  # (score, werte, seite, kontext)
    for s in seiten:
        f = formel(s, zieljahr)
        if f:
            formeln.append((f[1], f[0], s.name, f[2]))
        for key, werte in kandidaten(s, p_aktuell, zieljahr).items():
            for wert, info in werte.items():
                g = gesammelt.setdefault(key, {}).setdefault(
                    wert, {"jahr": -9, "stimmen": 0, "abstand": 10**9, "quellen": [], "kontext": ""})
                g["stimmen"] += info["stimmen"]
                if s.name not in g["quellen"]:
                    g["quellen"].append(s.name)
                if (info["jahr"], -info["abstand"]) > (g["jahr"], -g["abstand"]):
                    g["jahr"], g["abstand"] = info["jahr"], info["abstand"]
                    g["kontext"] = f"{s.name}: …{info['kontext']}…"
    ergebnis = {}
    for key, werte in gesammelt.items():
        wert, g = max(werte.items(),
                      key=lambda kv: (kv[1]["jahr"], len(kv[1]["quellen"]), kv[1]["stimmen"], -kv[1]["abstand"]))
        if g["jahr"] < 0:
            continue
        ergebnis[key] = {"wert": wert, "quellen": g["quellen"], "kontext": g["kontext"],
                         "jahr_ok": g["jahr"] > 0, "stimmen": g["stimmen"]}
    # Steuerformel: nur vollständig von EINER Seite; beste Jahresangabe, dann meiste Bestätigungen
    if formeln:
        def gleich(a, b):
            return all(a[1].get(k) == b[1].get(k) for k in ("est_g0", "est_g1", "est_a", "est_b"))
        score, werte, _name, kontext = max(formeln, key=lambda f: (f[0], sum(1 for u in formeln if gleich(u, f))))
        if score >= 0:
            quellen = [u[2] for u in formeln if gleich(u, (score, werte))]
            for key, wert in werte.items():
                ergebnis[key] = {"wert": wert, "quellen": quellen, "kontext": f"{quellen[0]}: …{kontext}…",
                                 "jahr_ok": score > 0, "stimmen": len(quellen)}
    return ergebnis
