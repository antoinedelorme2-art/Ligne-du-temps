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
import urllib.error
import urllib.request
from datetime import date

from openpyxl import load_workbook

RE_SHEETS = re.compile(r"docs\.google\.com/spreadsheets/d/([\w-]{20,})")
RE_DRIVE = re.compile(r"drive\.google\.com/file/d/([\w-]{20,})")
RE_ID = re.compile(r"^[\w-]{30,}$")


def echec(*lignes):
    """Message d'erreur visible dans l'interface d'Actions, puis arrêt."""
    print("::error::" + lignes[0])
    for l in lignes[1:]:
        print("   " + l)
    sys.exit(1)


def essayer(url):
    """Télécharge une URL. Renvoie (octets, statut, message) sans lever."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.read(), r.status, r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return b"", e.code, str(e)
    except Exception as e:                                  # réseau, DNS, délai
        return b"", 0, str(e)


def obtenir(source):
    """Renvoie un chemin local, en téléchargeant d'abord si nécessaire."""
    source = (source or "").strip()
    ident = None
    m = RE_SHEETS.search(source)
    if m:
        ident = m.group(1)
    elif RE_DRIVE.search(source):
        ident = RE_DRIVE.search(source).group(1)
    elif RE_ID.match(source):
        ident = source
    if not ident:
        if not os.path.exists(source):
            echec(f"Classeur introuvable : {source!r}",
                  "Attendu : un chemin de fichier, un identifiant Google, ou une URL.")
        return source

    # Deux points d'entrée : un vrai Google Sheets, ou un .xlsx déposé dans
    # Drive sans conversion. Le second ne répond pas à l'export Sheets.
    tentatives = [
        ("classeur Google Sheets",
         f"https://docs.google.com/spreadsheets/d/{ident}/export?format=xlsx"),
        ("fichier .xlsx dans Drive",
         f"https://drive.google.com/uc?export=download&id={ident}"),
    ]
    dernier = ""
    for quoi, url in tentatives:
        print(f"Tentative : {quoi}…")
        donnees, statut, info = essayer(url)
        if donnees[:2] == b"PK":
            tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
            tmp.write(donnees)
            tmp.close()
            print(f"  reçu : {len(donnees) / 1e6:.1f} Mo")
            return tmp.name
        apercu = donnees[:200].decode("utf-8", "replace").replace("\n", " ")
        dernier = f"HTTP {statut}, {info}, début de la réponse : {apercu!r}"
        print(f"  échec — {dernier}")

    echec(
        "Impossible de récupérer le classeur.",
        f"Identifiant utilisé : {ident}",
        f"Dernière réponse : {dernier}",
        "",
        "Trois causes possibles, par ordre de fréquence :",
        "1. Le fichier n'est pas partagé. Ouvrez-le, Partager → Accès général →",
        "   « Tous les utilisateurs disposant du lien », rôle Lecteur.",
        "2. C'est un .xlsx déposé dans Drive, pas un Google Sheets. Ouvrez-le et",
        "   faites Fichier → Enregistrer au format Google Sheets, puis reprenez",
        "   l'identifiant du NOUVEAU document.",
        "3. L'identifiant du secret CLASSEUR est celui d'un dossier Drive et non",
        "   d'un document.",
    )


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

for onglet in ("Lignes du temps", "Objets"):
    if onglet not in wb.sheetnames:
        echec(f"Onglet « {onglet} » absent du classeur.",
              "Onglets trouvés : " + ", ".join(wb.sheetnames))


def verifier(ws, attendues):
    presentes = [c.value for c in next(ws.iter_rows(max_row=1))]
    manquantes = [c for c in attendues if c not in presentes]
    if manquantes:
        echec(f"Colonnes manquantes dans l'onglet « {ws.title} » : "
              + ", ".join(manquantes),
              "En-têtes trouvés : " + ", ".join(str(p) for p in presentes if p))
    return {h: i for i, h in enumerate(presentes)}


# ------------------------------------------------------------ lignes du temps
ws = wb["Lignes du temps"]
verifier(ws, ["ID", "Nom (clé)", "Nom français", "Section", "Section (fr)", "Couleur"])
idx = verifier(ws, ["ID", "Nom (clé)", "Section"])
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
k = verifier(ws, ["Objet", "Version française", "Timeline", "Début (num)",
                  "Fin (num)", "Précision début", "Qualificatif début",
                  "Marge début (± ans)", "Marge fin (± ans)", "Notes", "URL1",
                  "Fiabilité date", "Sous-piste", "Ensembles liés",
                  "Start Month", "Start Date", "Start Hour",
                  "End Month", "End Date", "End Hour"])
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

if not objets:
    echec("Aucun objet exploitable dans le classeur.",
          "Vérifiez que la colonne « Début (num) » contient bien des valeurs "
          "calculées et non des formules vides.")

print(f"{DST} : {len(objets)} objets, {len(lignes)} pistes, "
      f"{len(sections)} sections")
if orphelins:
    print("Pistes citées dans Objets mais absentes du registre :",
          ", ".join(sorted(orphelins)[:10]))
