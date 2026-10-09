"""Rechenkern Pensionszuverdienstrechner Deutschland 2026.

Gesetzliche Rente (Altersrente, Erwerbsminderungsrente, Witwen-/Witwerrente)
plus selbständiger Zuverdienst (Freiberufler oder Gewerbe):
Kranken-/Pflegeversicherung, ggf. Rentenversicherung, Gewerbesteuer,
Einkommensteuer (§ 32a EStG) mit Soli und Kirchensteuer, Hinzuverdienst-
regeln bei EM-Rente und Einkommensanrechnung bei Witwenrente.
Alle Zahlen kommen aus dem Parameter-Dictionary und sind einstellbar.
"""

import math

STEUERJAHR = 2026

# (Schlüssel, Gruppe, Bezeichnung, Standardwert, Einheit)
PARAMETER_DEF = [
    # Einkommensteuer-Tarif § 32a EStG (2026)
    ("est_g0", "Einkommensteuer-Tarif", "Grundfreibetrag", 12348.0, "€"),
    ("est_g1", "Einkommensteuer-Tarif", "Ende Progressionszone 1", 17799.0, "€"),
    ("est_g2", "Einkommensteuer-Tarif", "Ende Progressionszone 2 (danach 42 %)", 69878.0, "€"),
    ("est_g3", "Einkommensteuer-Tarif", "Ende 42-%-Zone (danach 45 %)", 277825.0, "€"),
    ("est_a", "Einkommensteuer-Tarif", "Formel Zone 1: Faktor vor y", 914.51, ""),
    ("est_c1", "Einkommensteuer-Tarif", "Formel Zone 1: Konstante (Eingangssatz)", 1400.0, ""),
    ("est_b", "Einkommensteuer-Tarif", "Formel Zone 2: Faktor vor z", 173.10, ""),
    ("est_c2", "Einkommensteuer-Tarif", "Formel Zone 2: Konstante", 2397.0, ""),
    ("est_t1", "Einkommensteuer-Tarif", "Formel Zone 2: Steuer am Zonenbeginn", 1034.87, "€"),
    ("est_k4", "Einkommensteuer-Tarif", "Formel 42-%-Zone: Abzugsbetrag", 11135.63, "€"),
    ("est_k5", "Einkommensteuer-Tarif", "Formel 45-%-Zone: Abzugsbetrag", 19470.38, "€"),
    ("est_s4", "Einkommensteuer-Tarif", "Spitzensteuersatz", 42.0, "%"),
    ("est_s5", "Einkommensteuer-Tarif", "Reichensteuersatz", 45.0, "%"),
    # Solidaritätszuschlag
    ("soli_satz", "Solidaritätszuschlag", "Soli-Satz", 5.5, "%"),
    ("soli_freigrenze", "Solidaritätszuschlag", "Freigrenze (Einzelveranlagung, ESt)", 20350.0, "€"),
    ("soli_milderung", "Solidaritätszuschlag", "Milderungszone: max. % des Unterschieds", 11.9, "%"),
    # Pauschalen und Freibeträge
    ("wk_rente", "Pauschalen & Freibeträge", "Werbungskostenpauschale Renten", 102.0, "€"),
    ("sa_pausch", "Pauschalen & Freibeträge", "Sonderausgaben-Pauschbetrag", 36.0, "€"),
    ("uebungsleiter_max", "Pauschalen & Freibeträge", "Übungsleiterfreibetrag (§ 3 Nr. 26)", 3300.0, "€/Jahr"),
    ("ehrenamt_max", "Pauschalen & Freibeträge", "Ehrenamtspauschale (§ 3 Nr. 26a)", 960.0, "€/Jahr"),
    ("ba_neben_satz", "Pauschalen & Freibeträge", "BA-Pauschale nebenberuflich (Lehre, Schreiben …)", 25.0, "%"),
    ("ba_neben_max", "Pauschalen & Freibeträge", "BA-Pauschale nebenberuflich: Höchstbetrag", 900.0, "€"),
    ("ba_haupt_satz", "Pauschalen & Freibeträge", "BA-Pauschale hauptberufl. Schriftsteller/Journalist", 30.0, "%"),
    ("ba_haupt_max", "Pauschalen & Freibeträge", "BA-Pauschale hauptberuflich: Höchstbetrag", 3600.0, "€"),
    # Kranken- und Pflegeversicherung
    ("kv_satz", "Kranken- & Pflegeversicherung", "KV allgemeiner Beitragssatz", 14.6, "%"),
    ("kv_satz_erm", "Kranken- & Pflegeversicherung", "KV ermäßigter Beitragssatz (freiwillig)", 14.0, "%"),
    ("kv_zusatz", "Kranken- & Pflegeversicherung", "KV Zusatzbeitrag (Ihre Kasse)", 2.9, "%"),
    ("pv_satz", "Kranken- & Pflegeversicherung", "Pflegeversicherung Beitragssatz", 3.6, "%"),
    ("pv_kinderlos", "Kranken- & Pflegeversicherung", "PV-Zuschlag Kinderlose", 0.6, "%"),
    ("kv_bbg", "Kranken- & Pflegeversicherung", "Beitragsbemessungsgrenze KV/PV", 69750.0, "€/Jahr"),
    ("bezugsgroesse", "Kranken- & Pflegeversicherung", "Bezugsgröße (jährlich)", 47460.0, "€/Jahr"),
    # Rentenversicherung (Pflicht für bestimmte Selbständige)
    ("rv_satz", "Rentenversicherung", "RV-Beitragssatz", 18.6, "%"),
    ("rv_bbg", "Rentenversicherung", "Beitragsbemessungsgrenze RV", 101400.0, "€/Jahr"),
    ("gfg_monat", "Rentenversicherung", "Geringfügigkeitsgrenze", 603.0, "€/Monat"),
    # Gewerbesteuer
    ("gew_freibetrag", "Gewerbesteuer", "Freibetrag Gewerbeertrag (Einzelunternehmen)", 24500.0, "€"),
    ("gew_messzahl", "Gewerbesteuer", "Steuermesszahl", 3.5, "%"),
    ("gew_anrechnung", "Gewerbesteuer", "Anrechnung auf ESt: Faktor × Messbetrag", 4.0, "×"),
    # Hinzuverdienst Erwerbsminderungsrente
    ("em_voll_grenze", "Erwerbsminderungsrente", "Hinzuverdienstgrenze volle EM-Rente", 20763.75, "€/Jahr"),
    ("em_teil_min", "Erwerbsminderungsrente", "Hinzuverdienstgrenze teilweise EM (mindestens)", 41527.50, "€/Jahr"),
    ("em_anrechnung", "Erwerbsminderungsrente", "Anrechnung des übersteigenden Betrags", 40.0, "%"),
    # Witwen-/Witwerrente
    ("witwe_freibetrag", "Witwen-/Witwerrente", "Freibetrag (26,4 × aktueller Rentenwert)", 1122.53, "€/Monat"),
    ("witwe_anrechnung", "Witwen-/Witwerrente", "Anrechnung des übersteigenden Einkommens", 40.0, "%"),
    ("witwe_abzug_selbst", "Witwen-/Witwerrente", "Pauschaler Abzug Arbeitseinkommen (§ 18b SGB IV)", 39.8, "%"),
    # Umsatzsteuer
    ("ku_vorjahr", "Umsatzsteuer", "Kleinunternehmer: Umsatzgrenze Vorjahr", 25000.0, "€"),
    ("ku_laufend", "Umsatzsteuer", "Kleinunternehmer: Umsatzgrenze laufendes Jahr", 100000.0, "€"),
    # Tabelle
    ("tab_von", "Tabelle", "Tabelle: Start (Std/Woche)", 1.0, "h"),
    ("tab_bis", "Tabelle", "Tabelle: Ende (Std/Woche)", 30.0, "h"),
    ("tab_schritt", "Tabelle", "Tabelle: Schrittweite (Std/Woche)", 1.0, "h"),
    ("tab_umsatz_von", "Tabelle", "Tabelle: Start (Umsatz)", 2000.0, "€"),
    ("tab_umsatz_bis", "Tabelle", "Tabelle: Ende (Umsatz)", 60000.0, "€"),
    ("tab_umsatz_schritt", "Tabelle", "Tabelle: Schrittweite (Umsatz)", 2000.0, "€"),
]
PARAMETER_STANDARD = {k: v for k, _, _, v, _ in PARAMETER_DEF}
TARIF_ECKWERTE = ("est_g0", "est_g1", "est_g2", "est_g3")

RENTENARTEN = {
    "regelalter": "Regelaltersrente",
    "langjaehrig": "Altersrente für langjährig Versicherte (vorgezogen)",
    "besonders": "Altersrente für besonders langjährig Versicherte (45 Jahre)",
    "schwerbehindert": "Altersrente für schwerbehinderte Menschen",
    "em_voll": "Rente wegen voller Erwerbsminderung",
    "em_teil": "Rente wegen teilweiser Erwerbsminderung",
    "witwe": "Witwen-/Witwerrente (große, neues Recht)",
}
ALTERSRENTEN = ("regelalter", "langjaehrig", "besonders", "schwerbehindert")
RENTE_MODI = {
    "brutto_monat": "Brutto pro Monat (laut Rentenbescheid)",
    "brutto_jahr": "Brutto pro Jahr",
    "netto_monat": "Netto pro Monat (Zahlbetrag, wird zurückgerechnet)",
}
KV_ARTEN = {
    "kvdr": "Gesetzlich – pflichtversichert als Rentner (KVdR)",
    "freiwillig": "Gesetzlich – freiwillig versichert",
    "privat": "Privat versichert",
}
ZUV_MODI = {
    "stunden": "Stundensatz × Stunden × Wochen",
    "umsatz_jahr": "Jahresumsatz",
    "umsatz_monat": "Monatsumsatz (× 12)",
    "gewinn_jahr": "Gewinn direkt (Jahr)",
}
BA_MODI = {
    "betrag_jahr": "Tatsächliche Ausgaben € / Jahr",
    "betrag_monat": "Tatsächliche Ausgaben € / Monat",
    "prozent": "Prozent vom Umsatz",
    "pausch_neben": "Pauschale nebenberuflich (25 %, max. 900 €)",
    "pausch_haupt": "Pauschale Schriftsteller/Journalist (30 %, max. 3.600 €)",
}
KIRCHENSTEUER = {"0": "keine", "8": "8 % (Bayern, Baden-Württemberg)", "9": "9 % (übrige Länder)"}

EINGABEN_STANDARD = {
    "rentenart": "regelalter",
    "rente_modus": "brutto_monat",
    "rente_betrag": 1500.0,
    "rentenbeginn": 2024.0,
    "rentenfreibetrag": 0.0,
    "geburtsjahr": 1958.0,
    "em_grenze_indiv": 0.0,
    "witwe_sonstiges": 0.0,
    "zuv_modus": "stunden",
    "stundensatz": 50.0,
    "std_woche": 5.0,
    "wochen": 46.0,
    "umsatz_jahr": 12000.0,
    "umsatz_monat": 1000.0,
    "gewinn_jahr": 10000.0,
    "steuerfrei_pausch": 0.0,
    "ba_modus": "betrag_jahr",
    "ba_betrag": 1000.0,
    "ba_prozent": 10.0,
    "gewerbe": False,
    "hebesatz": 400.0,
    "kv_art": "kvdr",
    "pkv_beitrag": 0.0,
    "kinderlos": False,
    "rv_pflicht": False,
    "kirchensteuer": "0",
    "zusammen": False,
    "partner_zve": 0.0,
}


# ---------------------------------------------------------------------------
# Einkommensteuer
# ---------------------------------------------------------------------------
def tarif(zve, p):
    """Tarifliche Einkommensteuer nach § 32a Abs. 1 EStG (Grundtarif)."""
    x = math.floor(max(0.0, zve))
    if x <= p["est_g0"]:
        return 0.0
    if x <= p["est_g1"]:
        y = (x - p["est_g0"]) / 10000.0
        st = (p["est_a"] * y + p["est_c1"]) * y
    elif x <= p["est_g2"]:
        z = (x - p["est_g1"]) / 10000.0
        st = (p["est_b"] * z + p["est_c2"]) * z + p["est_t1"]
    elif x <= p["est_g3"]:
        st = p["est_s4"] / 100.0 * x - p["est_k4"]
    else:
        st = p["est_s5"] / 100.0 * x - p["est_k5"]
    return float(math.floor(st))


def tarif_veranlagung(zve, e, p):
    if e.get("zusammen"):
        return 2.0 * tarif((zve + max(0.0, e.get("partner_zve", 0.0))) / 2.0, p)
    return tarif(zve, p)


def grenzsteuersatz(zve, e, p):
    a = tarif_veranlagung(zve, e, p)
    b = tarif_veranlagung(zve + 100.0, e, p)
    return (b - a)


def koeffizienten_ableiten(p):
    """Leitet die Tarifformel aus den Eckwerten ab (bei neuen Tarifgrenzen).
    Annahme wie im Gesetz: Eingangssatz 14 %, Grenzsteuersatz steigt linear
    bis zum Ende der Zone 1, dann linear bis zum Spitzensteuersatz."""
    q = dict(p)
    g0, g1, g2 = p["est_g0"], p["est_g1"], p["est_g2"]
    y1 = (g1 - g0) / 10000.0
    # Grenzsteuersatz am Übergang Zone 1/2 bleibt wie bisher (= Konstante der Zone 2 / 10.000)
    m1 = p["est_c2"] / 10000.0
    q["est_a"] = round((m1 * 10000.0 - p["est_c1"]) / (2 * y1), 2)
    q["est_c2"] = round(m1 * 10000.0)
    z2 = (g2 - g1) / 10000.0
    q["est_b"] = round((p["est_s4"] * 100.0 - q["est_c2"]) / (2 * z2), 2)
    q["est_t1"] = round((q["est_a"] * y1 + p["est_c1"]) * y1, 2)
    st_g2 = (q["est_b"] * z2 + q["est_c2"]) * z2 + q["est_t1"]
    q["est_k4"] = round(p["est_s4"] / 100.0 * g2 - st_g2, 2)
    st_g3 = p["est_s4"] / 100.0 * p["est_g3"] - q["est_k4"]
    q["est_k5"] = round(p["est_s5"] / 100.0 * p["est_g3"] - st_g3, 2)
    return q


def soli(est, e, p):
    freigrenze = p["soli_freigrenze"] * (2 if e.get("zusammen") else 1)
    if est <= freigrenze:
        return 0.0
    return min(est * p["soli_satz"] / 100.0, (est - freigrenze) * p["soli_milderung"] / 100.0)


def besteuerungsanteil(beginn):
    """Besteuerungsanteil der gesetzlichen Rente nach Jahr des Rentenbeginns (§ 22 EStG)."""
    j = int(beginn)
    if j <= 2005:
        return 50.0
    if j <= 2020:
        return 50.0 + 2.0 * (j - 2005)
    if j == 2021:
        return 81.0
    if j == 2022:
        return 82.0
    return min(100.0, 82.5 + 0.5 * (j - 2023))


def altersentlastung(einkuenfte, e, steuerjahr=STEUERJAHR):
    """Altersentlastungsbetrag (§ 24a EStG) auf positive Einkünfte außer Renten."""
    gj = int(e.get("geburtsjahr") or 0)
    if not gj or gj + 64 >= steuerjahr or einkuenfte <= 0:
        return 0.0
    jahr = max(2005, gj + 65)
    if jahr <= 2020:
        satz, hoechst = 40.0 - 1.6 * (jahr - 2005), 1900 - 76 * (jahr - 2005)
    elif jahr <= 2022:
        satz, hoechst = {2021: (15.2, 722), 2022: (14.4, 684)}[jahr]
    else:
        satz, hoechst = max(0.0, 14.4 - 0.4 * (jahr - 2022)), max(0, 684 - 19 * (jahr - 2022))
    return min(einkuenfte * satz / 100.0, hoechst)


# ---------------------------------------------------------------------------
# Kranken-, Pflege-, Rentenversicherung
# ---------------------------------------------------------------------------
def _pv_satz(e, p):
    return p["pv_satz"] + (p["pv_kinderlos"] if e.get("kinderlos") else 0.0)


def kvpv_rente(rente_jahr, e, p):
    """Eigener KV/PV-Anteil auf die Rente (Rentner trägt PV voll, KV zur Hälfte)."""
    art = e.get("kv_art", "kvdr")
    r = min(max(0.0, rente_jahr), p["kv_bbg"])
    if art == "privat":
        beitrag = max(0.0, e.get("pkv_beitrag", 0.0)) * 12
        zuschuss = min(r * (p["kv_satz"] + p["kv_zusatz"]) / 200.0, beitrag / 2)
        return {"kv": beitrag - zuschuss, "pv": 0.0, "zuschuss": zuschuss}
    if art == "freiwillig":
        kv = r * (p["kv_satz_erm"] + p["kv_zusatz"]) / 100.0 - r * (p["kv_satz"] + p["kv_zusatz"]) / 200.0
    else:
        kv = r * (p["kv_satz"] + p["kv_zusatz"]) / 200.0
    return {"kv": kv, "pv": r * _pv_satz(e, p) / 100.0, "zuschuss": 0.0}


def kv_freigrenze_jahr(p):
    """KVdR: Arbeitseinkommen + Versorgungsbezüge beitragsfrei bis 1/20 der Bezugsgröße pro Monat."""
    return p["bezugsgroesse"] / 20.0


def sv_zuverdienst(arbeitseinkommen, rente_jahr, e, p):
    """Zusätzliche KV/PV- und RV-Beiträge durch den Zuverdienst (Jahr)."""
    a = max(0.0, arbeitseinkommen)
    art = e.get("kv_art", "kvdr")
    r = {"kv": 0.0, "pv": 0.0, "rv": 0.0, "kv_pflicht": False, "rv_pflicht": False, "basis_kv": 0.0}
    if art == "kvdr":
        if a > kv_freigrenze_jahr(p):
            basis = max(0.0, min(a, p["kv_bbg"] - min(rente_jahr, p["kv_bbg"])))
            r.update(kv_pflicht=True, basis_kv=basis, kv=basis * (p["kv_satz"] + p["kv_zusatz"]) / 100.0,
                     pv=basis * _pv_satz(e, p) / 100.0)
    elif art == "freiwillig":
        mindest = p["bezugsgroesse"] / 3.0  # 90. Teil der monatl. Bezugsgröße × 30 Tage × 12

        def beitrag(eink):
            basis = min(max(eink, mindest), p["kv_bbg"])
            return basis * (p["kv_satz_erm"] + p["kv_zusatz"]) / 100.0, basis * _pv_satz(e, p) / 100.0
        kv1, pv1 = beitrag(rente_jahr + a)
        kv0, pv0 = beitrag(rente_jahr)
        r.update(kv_pflicht=a > 0, basis_kv=a, kv=kv1 - kv0, pv=pv1 - pv0)
    if (e.get("rv_pflicht") and e.get("rentenart") != "regelalter" and a / 12.0 > p["gfg_monat"]):
        r["rv_pflicht"] = True
        r["rv"] = min(a, p["rv_bbg"]) * p["rv_satz"] / 100.0
    r["summe"] = r["kv"] + r["pv"] + r["rv"]
    return r


def gewerbesteuer(gewinn, e, p):
    if not e.get("gewerbe") or gewinn <= 0:
        return {"ertrag": 0.0, "mess": 0.0, "gewst": 0.0}
    ertrag = max(0.0, math.floor(gewinn / 100.0) * 100.0 - p["gew_freibetrag"])
    mess = ertrag * p["gew_messzahl"] / 100.0
    return {"ertrag": ertrag, "mess": mess, "gewst": mess * max(0.0, e.get("hebesatz", 400.0)) / 100.0}


# ---------------------------------------------------------------------------
# Rente
# ---------------------------------------------------------------------------
def rente_brutto_jahr(e, p):
    m, b = e["rente_modus"], max(0.0, e["rente_betrag"])
    if m == "brutto_jahr":
        return b
    if m == "netto_monat":
        lo, hi = b * 12, b * 12 * 1.6 + 1000
        for _ in range(80):
            mid = (lo + hi) / 2
            k = kvpv_rente(mid, e, p)
            if mid - k["kv"] - k["pv"] < b * 12:
                lo = mid
            else:
                hi = mid
        return round((lo + hi) / 2, 2)
    return b * 12


def rentenfreibetrag(rente_jahr, e):
    if e.get("rentenfreibetrag", 0) > 0:
        return e["rentenfreibetrag"]
    return rente_jahr * (100.0 - besteuerungsanteil(e.get("rentenbeginn", STEUERJAHR))) / 100.0


def rentenkuerzung(arbeitseinkommen, rente_jahr, e, p):
    """Kürzung der Rente durch den Zuverdienst (EM-Rente, Witwenrente) pro Jahr."""
    art = e.get("rentenart", "regelalter")
    a = max(0.0, arbeitseinkommen)
    w = {"art": art, "grenze": None, "anrechnung_monat": 0.0, "kuerzung": 0.0, "einkommen_monat": 0.0}
    if art in ("em_voll", "em_teil"):
        grenze = p["em_voll_grenze"] if art == "em_voll" else max(p["em_teil_min"], e.get("em_grenze_indiv", 0.0))
        w["grenze"] = grenze
        if a > grenze:
            w["anrechnung_monat"] = (a - grenze) / 12.0 * p["em_anrechnung"] / 100.0
    elif art == "witwe":
        eink = a * (1 - p["witwe_abzug_selbst"] / 100.0) / 12.0 + max(0.0, e.get("witwe_sonstiges", 0.0))
        w["einkommen_monat"] = eink
        w["grenze"] = p["witwe_freibetrag"]
        if eink > p["witwe_freibetrag"]:
            w["anrechnung_monat"] = (eink - p["witwe_freibetrag"]) * p["witwe_anrechnung"] / 100.0
    w["kuerzung"] = min(w["anrechnung_monat"] * 12.0, rente_jahr)
    return w


# ---------------------------------------------------------------------------
# Zuverdienst
# ---------------------------------------------------------------------------
def umsatz_aus_eingaben(e):
    m = e["zuv_modus"]
    if m == "stunden":
        return max(0.0, e["stundensatz"] * e["std_woche"] * e["wochen"])
    if m == "umsatz_monat":
        return max(0.0, e["umsatz_monat"] * 12)
    if m == "gewinn_jahr":
        return max(0.0, e["gewinn_jahr"])
    return max(0.0, e["umsatz_jahr"])


def betriebsausgaben(umsatz, e, p):
    if e["zuv_modus"] == "gewinn_jahr":
        return 0.0
    m = e["ba_modus"]
    if m == "betrag_jahr":
        return e["ba_betrag"]
    if m == "betrag_monat":
        return e["ba_betrag"] * 12
    if m == "prozent":
        return umsatz * e["ba_prozent"] / 100.0
    if m == "pausch_neben":
        return min(umsatz * p["ba_neben_satz"] / 100.0, p["ba_neben_max"])
    if m == "pausch_haupt":
        return min(umsatz * p["ba_haupt_satz"] / 100.0, p["ba_haupt_max"])
    return 0.0


def steuerfrei(e, p):
    return min(max(0.0, e.get("steuerfrei_pausch", 0.0)), p["uebungsleiter_max"])


def _steuern(rente_jahr, gewinn_stpfl, vorsorge, gewst_mess, gewst, e, p):
    """ESt, Soli, KiSt für gegebene Rente/Gewinn/Vorsorgeaufwendungen."""
    rfb = rentenfreibetrag(rente_jahr, e) if rente_jahr > 0 else 0.0
    renten_eink = max(0.0, rente_jahr - rfb - min(p["wk_rente"], max(0.0, rente_jahr - rfb)))
    aeb = altersentlastung(max(0.0, gewinn_stpfl), e)
    sde = renten_eink + gewinn_stpfl - aeb
    zve = max(0.0, sde - p["sa_pausch"] - vorsorge)
    est_tarif = tarif_veranlagung(zve, e, p)
    # Gewerbesteuer-Anrechnung § 35 EStG (vereinfacht: höchstens tarifliche ESt)
    anr = min(p["gew_anrechnung"] * gewst_mess, gewst, est_tarif) if gewst_mess else 0.0
    est = est_tarif - anr
    so = soli(est, e, p)
    kist = est_tarif * float(e.get("kirchensteuer", "0") or 0) / 100.0  # KiSt ohne § 35-Minderung
    return {"rentenfreibetrag": rfb, "renten_eink": renten_eink, "aeb": aeb, "zve": zve,
            "est_tarif": est_tarif, "gew_anrechnung": anr, "est": est, "soli": so, "kist": kist,
            "summe": est + so + kist}


def berechne_mit_umsatz(umsatz, e, p, rente_voll=None):
    if rente_voll is None:
        rente_voll = rente_brutto_jahr(e, p)
    ba = betriebsausgaben(umsatz, e, p)
    gewinn = umsatz - ba
    frei = min(steuerfrei(e, p), max(0.0, gewinn))
    gewinn_stpfl = gewinn - frei                 # steuer- und beitragspflichtig
    w = rentenkuerzung(gewinn_stpfl, rente_voll, e, p)
    rente = rente_voll - w["kuerzung"]
    kvr_voll = kvpv_rente(rente_voll, e, p)
    kvr = kvpv_rente(rente, e, p)
    sv = sv_zuverdienst(gewinn_stpfl, rente, e, p)
    gw = gewerbesteuer(gewinn_stpfl, e, p)
    vorsorge = kvr["kv"] + kvr["pv"] + sv["summe"]
    st = _steuern(rente, gewinn_stpfl, vorsorge, gw["mess"], gw["gewst"], e, p)
    st0 = _steuern(rente_voll, 0.0, kvr_voll["kv"] + kvr_voll["pv"], 0.0, 0.0, e, p)
    rente_netto_voll = rente_voll - kvr_voll["kv"] - kvr_voll["pv"]
    rente_netto = rente - kvr["kv"] - kvr["pv"]
    netto_ohne = rente_netto_voll - st0["summe"]
    netto_gesamt = rente_netto + gewinn - sv["summe"] - gw["gewst"] - st["summe"]
    netto_zuv = netto_gesamt - netto_ohne
    return {
        "umsatz": umsatz, "ba": ba, "gewinn": gewinn, "steuerfrei": frei, "gewinn_stpfl": gewinn_stpfl,
        "sv": sv, "gew": gw, "steuer": st, "steuer_ohne": st0,
        "mehrsteuer": st["summe"] - st0["summe"],
        "rente_voll": rente_voll, "rente": rente, "wirkung": w,
        "kvpv_rente": kvr, "kvpv_rente_voll": kvr_voll,
        "rente_netto": rente_netto, "rente_netto_voll": rente_netto_voll,
        "rentenverlust_netto": rente_netto_voll - rente_netto,
        "netto_ohne": netto_ohne, "netto_gesamt": netto_gesamt, "netto_gesamt_monat": netto_gesamt / 12.0,
        "netto_zuv": netto_zuv, "netto_zuv_monat": netto_zuv / 12.0,
        "anteil_umsatz": netto_zuv / umsatz * 100.0 if umsatz > 0 else 0.0,
        "anteil_gewinn": netto_zuv / gewinn * 100.0 if gewinn > 0 else 0.0,
        "grenzsteuersatz": grenzsteuersatz(st["zve"], e, p),
    }


def umsatz_minus_ba(u, e, p):
    return u - betriebsausgaben(u, e, p)


def _umsatz_fuer_gewinn(ziel, e, p):
    lo, hi = 0.0, 1.0
    while umsatz_minus_ba(hi, e, p) <= ziel:
        hi *= 2
        if hi > 1e9:
            return None
    for _ in range(80):
        mid = (lo + hi) / 2
        if umsatz_minus_ba(mid, e, p) <= ziel:
            lo = mid
        else:
            hi = mid
    return hi


def grenzen_sprung(e, p):
    """Gewinne, ab denen Abgaben sprunghaft auf den ganzen Gewinn anfallen."""
    frei = steuerfrei(e, p)
    k = []
    if e.get("kv_art", "kvdr") == "kvdr":
        k.append(("kv", kv_freigrenze_jahr(p) + frei))
    if e.get("rv_pflicht") and e.get("rentenart") != "regelalter":
        k.append(("rv", p["gfg_monat"] * 12 + frei))
    return k


def _bereich_ab(grenze, e, p, rente_voll):
    u_g = _umsatz_fuer_gewinn(grenze, e, p)
    if u_g is None:
        return None
    netto_unter = berechne_mit_umsatz(max(0.0, u_g - 0.01), e, p, rente_voll)["netto_zuv"]
    lo, hi = u_g, u_g + 1.0
    while berechne_mit_umsatz(hi, e, p, rente_voll)["netto_zuv"] < netto_unter:
        hi = lo + (hi - lo) * 2
        if hi > 1e8:
            return None
    for _ in range(80):
        mid = (lo + hi) / 2
        if berechne_mit_umsatz(mid, e, p, rente_voll)["netto_zuv"] < netto_unter:
            lo = mid
        else:
            hi = mid
    if hi - u_g < 0.5:
        return None
    return {"umsatz_grenze": u_g, "umsatz_ende": hi, "gewinn_grenze": grenze,
            "gewinn_ende": umsatz_minus_ba(hi, e, p), "netto_unter": netto_unter}


def unguenstiger_bereich(e, p, rente_voll=None):
    if rente_voll is None:
        rente_voll = rente_brutto_jahr(e, p)
    bereiche = []
    for grund, g in grenzen_sprung(e, p):
        b = _bereich_ab(g, e, p, rente_voll)
        if b:
            b["grund"] = grund
            bereiche.append(b)
    return max(bereiche, key=lambda b: b["umsatz_ende"]) if bereiche else None


def stunden_fuer_umsatz(u, e):
    f = e["stundensatz"] * e["wochen"]
    return u / f if f > 0 else None


def berechne(e, p):
    rv = rente_brutto_jahr(e, p)
    u = umsatz_aus_eingaben(e)
    r = berechne_mit_umsatz(u, e, p, rv)
    r["stunden_jahr"] = e["std_woche"] * e["wochen"] if e["zuv_modus"] == "stunden" else None
    r["netto_pro_stunde"] = r["netto_zuv"] / r["stunden_jahr"] if r["stunden_jahr"] else None
    r["grenz_netto_100"] = berechne_mit_umsatz(u + 100.0, e, p, rv)["netto_zuv"] - r["netto_zuv"]
    r["ungünstig"] = unguenstiger_bereich(e, p, rv)
    r["warnungen"] = warnungen(r, e, p)
    return r


def warnungen(r, e, p):
    w = []
    art = e.get("rentenart", "regelalter")
    wk = r["wirkung"]
    a = r["gewinn_stpfl"]
    ub = r["ungünstig"]
    if ub and ub["umsatz_grenze"] <= r["umsatz"] < ub["umsatz_ende"]:
        warum = {"kv": "Ab dort sind Kranken- und Pflegeversicherungsbeiträge auf das GANZE Arbeitseinkommen "
                       f"fällig (Freigrenze {fmt(kv_freigrenze_jahr(p) / 12)}/Monat)",
                 "rv": "Ab dort ist Rentenversicherung auf das ganze Arbeitseinkommen fällig"}[ub["grund"]]
        txt = (f"UNGÜNSTIGER BEREICH: Der Gewinn liegt knapp über {fmt(ub['gewinn_grenze'])}. {warum}. Netto "
               f"bleibt weniger als knapp darunter ({fmt(ub['netto_unter'])}). Erst ab einem Umsatz von "
               f"{fmt(ub['umsatz_ende'])} lohnt sich der Mehrverdienst.")
        if e["zuv_modus"] == "stunden":
            h1, h2 = stunden_fuer_umsatz(ub["umsatz_grenze"], e), stunden_fuer_umsatz(ub["umsatz_ende"], e)
            if h1 is not None:
                txt += f" Entspricht ca. {zk(h1, 1)} bis {zk(h2, 1)} Std/Woche."
        w.append(("rot", txt))
    elif ub and r["umsatz"] < ub["umsatz_grenze"] and r["gewinn"] > ub["gewinn_grenze"] * 0.8:
        w.append(("orange", f"Hinweis: Der Gewinn ({fmt(r['gewinn'])}) liegt knapp unter {fmt(ub['gewinn_grenze'])}. "
                            "Darüber fallen Beiträge auf den ganzen Gewinn an – sinnvoll erst ab Umsatz "
                            f"{fmt(ub['umsatz_ende'])}."))
    # Rentenart
    if art in ALTERSRENTEN:
        w.append(("info", "Altersrente: Seit 2023 dürfen Sie unbegrenzt hinzuverdienen – die Rente wird nicht gekürzt."))
        w.append(("info", "Aktivrente (seit 2026, bis 2.000 €/Monat steuerfrei) gilt NUR für Arbeitnehmer nach der "
                          "Regelaltersgrenze – nicht für Selbständige und Freiberufler. Hier nicht anwendbar."))
    if art in ("em_voll", "em_teil"):
        if wk["anrechnung_monat"]:
            w.append(("orange", f"RENTENKÜRZUNG: Hinzuverdienst {fmt(a)} über der Grenze von {fmt(wk['grenze'])} – "
                                f"{zk(p['em_anrechnung'], 0)} % des übersteigenden Betrags werden angerechnet: "
                                f"−{fmt(wk['anrechnung_monat'])}/Monat, −{fmt(r['rentenverlust_netto'])} netto im Jahr."))
        elif a > wk["grenze"] * 0.85:
            w.append(("orange", f"Achtung: Hinzuverdienst ({fmt(a)}) nahe der Grenze von {fmt(wk['grenze'])} pro Jahr. "
                                "Darüber werden 40 % des übersteigenden Betrags auf die Rente angerechnet."))
        stunden_max = 15 if art == "em_voll" else 30
        if e["zuv_modus"] == "stunden" and e["std_woche"] > stunden_max:
            w.append(("rot", f"ACHTUNG Leistungsvermögen: Eine Rente wegen {'voller' if art == 'em_voll' else 'teilweiser'} "
                             f"Erwerbsminderung setzt voraus, dass Sie weniger als {3 if art == 'em_voll' else 6} Stunden "
                             f"täglich arbeiten können. {zk(e['std_woche'], 1)} Std/Woche können die Rente selbst "
                             "infrage stellen – vorher mit der Rentenversicherung klären!"))
        if art == "em_teil" and not e.get("em_grenze_indiv"):
            w.append(("info", "Teilweise Erwerbsminderung: Gerechnet mit der Mindestgrenze. Ihre individuelle Grenze "
                              "(bestes Verdienstjahr der letzten 15 Jahre) steht im Rentenbescheid – bitte eintragen."))
        w.append(("info", "EM-Rente: Hinzuverdienst ist der Rentenversicherung zu melden; abgerechnet wird jährlich "
                          "rückwirkend (Überzahlungen werden zurückgefordert)."))
    if art == "witwe":
        if wk["anrechnung_monat"]:
            w.append(("orange", f"EINKOMMENSANRECHNUNG: Anrechenbares Einkommen {fmt(wk['einkommen_monat'])}/Monat "
                                f"(Gewinn − {zk(p['witwe_abzug_selbst'], 1)} % pauschal) über dem Freibetrag von "
                                f"{fmt(p['witwe_freibetrag'])}: {zk(p['witwe_anrechnung'], 0)} % werden angerechnet – "
                                f"−{fmt(wk['anrechnung_monat'])}/Monat."))
        w.append(("info", "Witwen-/Witwerrente: Angerechnet wird das Einkommen des VORJAHRES, jeweils ab 1. Juli. Die "
                          "Kürzung wirkt also zeitversetzt. Eigene Renten zählen ebenfalls (Feld „Sonstiges "
                          "anrechenbares Einkommen“)."))
    # Krankenversicherung
    kv = e.get("kv_art", "kvdr")
    if kv == "kvdr" and ((e["zuv_modus"] == "stunden" and e["std_woche"] > 20) or a > r["rente_voll"]):
        w.append(("orange", "Achtung KVdR: Ist die Selbständigkeit HAUPTberuflich (mehr als ca. 20 Std/Woche oder "
                            "Gewinn höher als die Rente), entfällt die Krankenversicherung der Rentner. Dann gilt "
                            "freiwillige Versicherung mit Beiträgen auf alle Einnahmen (Auswahl „freiwillig“)."))
    if kv == "kvdr" and r["sv"]["kv_pflicht"]:
        w.append(("info", "KVdR: Auf das Arbeitseinkommen zahlen Sie KV (allgemeiner Satz + Zusatzbeitrag) und PV "
                          "allein – ohne Zuschuss der Rentenversicherung."))
    if kv == "privat":
        w.append(("info", "Private Krankenversicherung: Der Zuverdienst ändert Ihren Beitrag nicht."))
    if r["sv"]["rv_pflicht"]:
        w.append(("info", "Rentenversicherungspflicht als Selbständiger (z. B. Lehrer/Dozent, arbeitnehmerähnlich): "
                          "Die Beiträge erhöhen später Ihre Rente."))
    elif e.get("rv_pflicht") and art == "regelalter":
        w.append(("info", "Nach Erreichen der Regelaltersgrenze mit Vollrente sind Sie rentenversicherungsfrei "
                          "(Verzicht auf Versicherungsfreiheit möglich)."))
    # Gewerbe / Umsatzsteuer / Steuer
    if e.get("gewerbe") and r["gew"]["gewst"]:
        w.append(("info", f"Gewerbesteuer {fmt(r['gew']['gewst'])}; davon werden "
                          f"{fmt(r['steuer']['gew_anrechnung'])} auf die Einkommensteuer angerechnet."))
    elif e.get("gewerbe"):
        w.append(("info", f"Gewerbe: Bis {fmt(p['gew_freibetrag'], 0)} Gewinn fällt keine Gewerbesteuer an (Freibetrag)."))
    if r["umsatz"] > p["ku_laufend"]:
        w.append(("rot", f"Umsatz über {fmt(p['ku_laufend'], 0)}: Kleinunternehmerregelung entfällt sofort – "
                         "19 % Umsatzsteuer auf Ihre Rechnungen."))
    elif r["umsatz"] > p["ku_vorjahr"]:
        w.append(("orange", f"Umsatz über {fmt(p['ku_vorjahr'], 0)}: Im FOLGEJAHR sind Sie kein Kleinunternehmer mehr "
                            "und müssen 19 % Umsatzsteuer aufschlagen. Der Stundensatz hier ist Ihr Honorar ohne USt."))
    if e.get("steuerfrei_pausch", 0) > p["uebungsleiter_max"]:
        w.append(("orange", f"Steuerfrei sind höchstens {fmt(p['uebungsleiter_max'], 0)} (Übungsleiter) bzw. "
                            f"{fmt(p['ehrenamt_max'], 0)} (Ehrenamt) – der Rest wurde voll angesetzt."))
    if r["steuer"]["aeb"]:
        w.append(("info", f"Altersentlastungsbetrag (§ 24a EStG): {fmt(r['steuer']['aeb'])} vom Gewinn steuerfrei."))
    if r["gewinn"] > 410:
        w.append(("info", "Steuererklärung: Mit Gewinn aus Selbständigkeit sind Sie zur Abgabe verpflichtet, "
                          "sobald das zu versteuernde Einkommen den Grundfreibetrag übersteigt."))
    if r["gewinn"] < 0:
        w.append(("orange", "Verlust aus dem Zuverdienst – wird mit der Rente verrechnet."))
    return w


def tabelle(e, p, werte, modus_stunden):
    rv = rente_brutto_jahr(e, p)
    ub = unguenstiger_bereich(e, p, rv)
    zeilen = []
    for x in werte:
        u = e["stundensatz"] * x * e["wochen"] if modus_stunden else x
        r = berechne_mit_umsatz(u, e, p, rv)
        if r["wirkung"]["anrechnung_monat"]:
            status = "Rente gekürzt"
        elif ub and ub["umsatz_grenze"] <= u < ub["umsatz_ende"]:
            status = "ungünstig"
        elif r["sv"]["summe"] == 0:
            status = "abgabenfrei"
        else:
            status = "OK"
        r["x"], r["status"] = x, status
        zeilen.append(r)
    return zeilen, ub


def plausibilitaet(p):
    """Formale Prüfung der Parameter. Liefert [(stufe, text)]."""
    m = []
    g = [p[k] for k in TARIF_ECKWERTE]
    if any(a >= b for a, b in zip(g, g[1:])):
        m.append(("rot", "Die Tarifgrenzen der Einkommensteuer sind nicht aufsteigend."))
    for k in ("kv_satz", "kv_satz_erm", "kv_zusatz", "pv_satz", "pv_kinderlos", "rv_satz", "soli_satz",
              "est_s4", "est_s5", "em_anrechnung", "witwe_anrechnung", "witwe_abzug_selbst"):
        if not 0 <= p[k] <= 100:
            m.append(("rot", f"Prozentwert „{k}“ = {p[k]} liegt außerhalb von 0–100 %."))
    if p["kv_zusatz"] > 6:
        m.append(("gelb", "Der KV-Zusatzbeitrag ist ungewöhnlich hoch."))
    if abs(tarif(p["est_g1"] + 1, p) - tarif(p["est_g1"], p)) > 2 or abs(tarif(p["est_g2"] + 1, p) - tarif(p["est_g2"], p)) > 2:
        m.append(("gelb", "Die Tarifformel passt nicht zu den Tarifgrenzen (Sprung an einer Zonengrenze). "
                          "Bei neuen Grenzen bitte auch die Formel-Koeffizienten aktualisieren."))
    if p["em_teil_min"] <= p["em_voll_grenze"]:
        m.append(("gelb", "Die Mindestgrenze bei teilweiser EM ist üblicherweise doppelt so hoch wie die bei voller EM."))
    return m


def fmt(x, nachkomma=2, einheit=" €"):
    if x is None:
        return "–"
    s = f"{x:,.{nachkomma}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s + einheit


def fmt_p(x):
    return fmt(x, 1, " %")


def zk(x, n=2):
    return fmt(x, n, "")
