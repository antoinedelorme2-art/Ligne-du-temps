# -*- coding: utf-8 -*-
"""Régénère donnees.json à partir du classeur.

    python generer_donnees.py Base_lignes_du_temps.xlsx
    python generer_donnees.py <id-du-google-sheets> --sortie site/donnees.json
    python generer_donnees.py https://docs.google.com/spreadsheets/d/<id>/edit

Dépendance unique : pip install openpyxl

Le classeur reste la source de vérité. Ce script ne fait que traduire ses
onglets « Lignes du temps » et « Objets » dans le format compact que la page
sait lire. Un classeur Google est téléchargé au format xlsx ; il doit être
partagé en lecture par lien, sans quoi Google renvoie une page de connexion
au lieu du fichier.
"""
import argparse
import json
import os
import re
import sys
import tempfile
import urllib.request
from datetime import date

from openpyxl import load_workbook

RE_SHEETS = re.compile(r"docs\.google\.com/spreadsheets/d/([\w-]{20,})")
RE_ID = re.compile(r"^[\w-]{30,}$")


def obtenir(source):
    """Renvoie un chemin local, en téléchargeant d'abord si nécessaire."""
    ident = None
    m = RE_SHEETS.search(source)
    if m:
        ident = m.group(1)
    elif RE_ID.match(source.strip()):
        ident = source.strip()
    if not ident:
        if not os.path.exists(source):
            sys.exit(f"Introuvable : {source}")
        return source

    url = f"https://docs.google.com/spreadsheets/d/{ident}/export?format=xlsx"
    print("Téléchargement du classeur Google…")
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    with urllib.request.urlopen(url, timeout=120) as r:
        tmp.write(r.read())
    tmp.close()
    with open(tmp.name, "rb") as f:
        if f.read(2) != b"PK":
            sys.exit("Google n'a pas renvoyé un classeur. Vérifiez que le "
                     "document est partagé en lecture par lien.")
    print(f"  {os.path.getsize(tmp.name) / 1e6:.1f} Mo reçus")
    return tmp.name


ap = argparse.ArgumentParser()
ap.add_argument("source", nargs="?", default="Base_lignes_du_temps.xlsx",
                help="chemin du .xlsx, ou identifiant / URL du Google Sheets")
ap.add_argument("--sortie", default="donnees.json")
args = ap.parse_args()

SRC = obtenir(args.source)
DST = args.sortie

PETITS = {"and", "of", "the", "in", "for", "&"}
SIGLES = {"UK", "USA"}


def titre_en(s):
    """« WARS AND BATTLES » → « Wars and Battles », sigles préservés."""
    mots = str(s).replace("\n", " ").split()
    out = []
    for i, w in enumerate(mots):
        if w in SIGLES or not w.isalpha():
            out.append(w if w in SIGLES or not w.isupper() else w.capitalize())
        elif i > 0 and w.lower() in PETITS:
            out.append(w.lower())
        else:
            out.append(w.capitalize() if w.isupper() else w)
    return " ".join(out)


def minutes_dans_annee(an, mois, jour, heure):
    """Position dans l'année, en minutes depuis le 1er janvier 00 h 00.

    0 signifie « inconnue » ; le 1er janvier vaut donc 1440. Seules les dates
    de l'ère chrétienne sont converties, la source n'ayant jamais de mois
    avant l'an 1.
    """
    if an is None or an < 1 or not mois:
        return 0
    try:
        j = date(int(an), int(mois), int(jour) if jour else 1)
    except ValueError:
        return 0
    mn = 0
    if heure not in (None, ""):
        m = re.match(r"^(\d{1,2})[:h.]?(\d{2})?", str(heure).strip())
        if m:
            mn = int(m.group(1)) * 60 + int(m.group(2) or 0)
    return j.timetuple().tm_yday * 1440 + mn


wb = load_workbook(SRC, read_only=True, data_only=True)

# ------------------------------------------------------------ lignes du temps
ws = wb["Lignes du temps"]
idx = {h: i for i, h in enumerate(c.value for c in next(ws.iter_rows(max_row=1)))}
lignes, cle_vers_i = [], {}
sections, sec_index, sec_fr_index = [], {}, {}

for row in ws.iter_rows(min_row=2, values_only=True):
    if not row or not row[idx["Nom (clé)"]]:
        continue
    cle = row[idx["Nom (clé)"]]
    sec = row[idx["Section"]]
    sec_fr = row[idx["Section (fr)"]] or sec
    coul = row[idx["Couleur"]] or "#7F8C8D"
    if sec not in sec_index:
        sec_index[sec] = len(sections)
        sec_fr_index[sec_fr] = len(sections)
        sections.append([sec_fr, titre_en(sec), coul])
    cle_vers_i[cle] = len(lignes)
    lignes.append([row[idx["ID"]], cle, row[idx["Nom français"]] or "",
                   sec, sec_fr, coul])


def ensembles(txt):
    """« Égypte ; Syrie » → indices de sections ; 0 quand il n'y a rien."""
    if not txt:
        return 0
    i = [sec_fr_index[p.strip()] for p in str(txt).split(";")
         if p.strip() in sec_fr_index]
    return i if len(i) > 1 else 0


# -------------------------------------------------------------------- objets
ws = wb["Objets"]
k = {h: i for i, h in enumerate(c.value for c in next(ws.iter_rows(max_row=1)))}
objets, orphelins = [], set()

for row in ws.iter_rows(min_row=2, values_only=True):
    if not row or not row[k["Objet"]]:
        continue
    tl = row[k["Timeline"]]
    if tl not in cle_vers_i:
        orphelins.add(tl)
        continue
    debut = row[k["Début (num)"]]
    if debut in (None, ""):
        continue
    fin = row[k["Fin (num)"]]
    fin = int(fin) if isinstance(fin, (int, float)) else None
    if fin is not None and fin < int(debut):
        fin = None
    notes = (row[k["Notes"]] or "").strip()
    if len(notes) > 900:
        notes = notes[:900].rsplit(" ", 1)[0] + "…"
    objets.append([
        row[k["Objet"]],
        row[k["Version française"]] or "",
        cle_vers_i[tl],
        int(debut),
        fin,
        row[k["Précision début"]] or "année",
        row[k["Qualificatif début"]] or "",
        row[k["Marge début (± ans)"]] or 0,
        row[k["Marge fin (± ans)"]] or 0,
        notes,
        row[k["URL1"]] or "",
        1 if row[k["Fiabilité date"]] in ("texte", "vérifiée", "corrigée") else 0,
        row[k["Sous-piste"]] or "",
        ensembles(row[k["Ensembles liés"]]),
        minutes_dans_annee(debut, row[k["Start Month"]], row[k["Start Date"]],
                           row[k["Start Hour"]]),
        minutes_dans_annee(fin, row[k["End Month"]], row[k["End Date"]],
                           row[k["End Hour"]]),
    ])

dossier = os.path.dirname(DST)
if dossier:
    os.makedirs(dossier, exist_ok=True)
with open(DST, "w", encoding="utf-8") as f:
    json.dump({"lignes": lignes, "sections": sections, "objets": objets},
              f, ensure_ascii=False, separators=(",", ":"))

print(f"{DST} : {len(objets)} objets, {len(lignes)} pistes, "
      f"{len(sections)} sections")
if orphelins:
    print("Pistes citées dans Objets mais absentes du registre :",
          ", ".join(sorted(orphelins)[:10]))
