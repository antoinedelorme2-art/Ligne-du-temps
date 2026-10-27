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


# ------------------------------------------------------------------ banques
# La banque « Climat et catastrophes » ne donne pas d'objets : ses lignes
# deviennent les repères du bandeau fixe en haut de la page.
BANQUE_CLIMAT = "Climat et catastrophes"
banques = []
if "Listes" in wb.sheetnames:
    ws = wb["Listes"]
    entetes = [c.value for c in next(ws.iter_rows(max_row=1))]
    if "Banque" in entetes:
        col = entetes.index("Banque")
        for row in ws.iter_rows(min_row=2, values_only=True):
            b = row[col] if col < len(row) else None
            if b and b != BANQUE_CLIMAT and b not in banques:
                banques.append(b)


def indice_banque(b):
    b = b or "—"
    if b not in banques:
        banques.append(b)
    return banques.index(b)


# Noms anglais et couleurs de repli des catégories du bandeau climatique.
CATS_EN = {
    "Épisodes climatiques": ("Climatic episodes", "#2C6E8B"),
    "Séismes et tsunamis": ("Earthquakes and tsunamis", "#6E4B1F"),
    "Sécheresses et famines": ("Droughts and famines", "#B5871D"),
    "Éruptions volcaniques": ("Volcanic eruptions", "#8E2317"),
    "Épidémies": ("Epidemics", "#5B3A6B"),
    "Impacts et événements cosmiques": ("Cosmic events", "#3F4A52"),
}
categories, cat_index = [], {}


def indice_categorie(tl):
    """« Climat – Épidémies » → indice de la catégorie « Épidémies »."""
    nom = re.sub(r"^Climat\s*[–-]\s*", "", str(tl or "")).strip() or "Autre"
    if nom not in cat_index:
        en, coul = CATS_EN.get(nom, (nom, "#3F4A52"))
        if tl in cle_vers_i:
            coul = lignes[cle_vers_i[tl]][5] or coul
        cat_index[nom] = len(categories)
        categories.append([nom, en, coul])
    return cat_index[nom]


# Rapprochements entre banques (même événement vu par deux sources). Lus
# dans une colonne « Groupe » si le classeur en a une ; sinon repris du
# donnees.json précédent, où ils ont été établis.
groupes_precedents = {}
climat_precedent = None          # (categories, reperes) du donnees.json versé
for chemin in ("donnees.json", DST):
    try:
        with open(chemin, encoding="utf-8") as f:
            ancien = json.load(f)
        if climat_precedent is None and ancien.get("reperes"):
            climat_precedent = (ancien.get("categories", []), ancien["reperes"])
        for o in ancien.get("objets", []):
            if len(o) > 17 and o[17]:
                cle_l = ancien["lignes"][o[2]][1]
                groupes_precedents[(o[0], cle_l, ancien["banques"][o[16]], o[3])] = o[17]
        if groupes_precedents:
            break
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        continue


# -------------------------------------------------------------------- objets
ws = wb["Objets"]
k = verifier(ws, ["Objet", "Version française", "Timeline", "Début (num)",
                  "Fin (num)", "Précision début", "Qualificatif début",
                  "Marge début (± ans)", "Marge fin (± ans)", "Notes", "URL1",
                  "Fiabilité date", "Sous-piste", "Ensembles liés",
                  "Start Month", "Start Date", "Start Hour",
                  "End Month", "End Date", "End Hour", "Banque"])
k_ampleur = k.get("Ampleur")
k_groupe = k.get("Groupe")
objets, reperes, orphelins = [], [], set()

for row in ws.iter_rows(min_row=2, values_only=True):
    if not row or not row[k["Objet"]]:
        continue
    tl = row[k["Timeline"]]
    banque = row[k["Banque"]]
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
    if banque == BANQUE_CLIMAT:
        ampleur = row[k_ampleur] if k_ampleur is not None else None
        reperes.append([
            row[k["Objet"]],
            row[k["Version française"]] or "",
            indice_categorie(tl),
            int(ampleur) if isinstance(ampleur, (int, float)) else 1,
            int(debut),
            fin,
            notes,
            row[k["URL1"]] or "",
        ])
        continue
    if tl not in cle_vers_i:
        orphelins.add(tl)
        continue
    groupe = row[k_groupe] if k_groupe is not None else None
    if not isinstance(groupe, (int, float)) or not groupe:
        groupe = groupes_precedents.get(
            (row[k["Objet"]], tl, banque or "—", int(debut)), 0)
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
        indice_banque(banque),
        int(groupe),
    ])

# Un classeur sans lignes « Climat et catastrophes » viderait le bandeau :
# on garde alors les repères du donnees.json versé dans le dépôt.
if not reperes and climat_precedent:
    categories, reperes = climat_precedent
    print(f"Aucun repère climatique dans le classeur : {len(reperes)} repris "
          "du donnees.json du dépôt.")

if not objets:
    echec("Aucun objet exploitable dans le classeur.",
          "Vérifiez que la colonne « Début (num) » contient bien des valeurs "
          "calculées et non des formules vides.")

dossier = os.path.dirname(DST)
if dossier:
    os.makedirs(dossier, exist_ok=True)
with open(DST, "w", encoding="utf-8") as f:
    json.dump({"lignes": lignes, "sections": sections, "banques": banques,
               "objets": objets, "categories": categories,
               "reperes": reperes},
              f, ensure_ascii=False, separators=(",", ":"))

print(f"{DST} : {len(objets)} objets, {len(lignes)} pistes, "
      f"{len(sections)} sections, {len(reperes)} repères climatiques")
print("Banques : " + ", ".join(
    f"{b} ({sum(1 for o in objets if o[16] == i)})"
    for i, b in enumerate(banques)))
if orphelins:
    print("Pistes citées dans Objets mais absentes du registre :",
          ", ".join(sorted(orphelins)[:10]))
