# -*- coding: utf-8 -*-
"""Récolte trois banques ouvertes et les range dans sources/.

    python recolter_sources.py                  # les trois banques
    python recolter_sources.py wikidata periodo # certaines seulement

Aucune dépendance hors de la bibliothèque standard.

  sources/wikidata.json    batailles, guerres, traités, révolutions, États,
                           catastrophes… ayant un article dans beaucoup de
                           Wikipédias (seuil de notoriété par type)
  sources/wikipedia.json   lignes des pages « Chronologie de… » (fr) et
                           « Timeline of … history » (en)
  sources/wikidata_regnes.json  règnes des monarques et mandats des chefs
                           d'État et de gouvernement, avec naissance et mort
  sources/periodo.json     périodes nommées de PeriodO (perio.do)

Chaque objet porte déjà sa piste (clé « Nom (clé) » du registre) ; c'est
generer_donnees.py qui les fusionne avec le classeur et repère les doublons.
Une banque dont la récolte échoue ou paraît tronquée garde son fichier
précédent : on ne remplace jamais des données par moins de données.
"""
import gzip
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import date

from rattachement import (GUERRES, AUTRES, PISTE_PERIODE, cle_titre,
                          piste_pour)

UA = ("LigneDuTemps/1.0 (https://github.com/antoinedelorme2-art/Ligne-du-temps; "
      "frise chronologique non commerciale)")
DOSSIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources")
SPARQL = "https://query.wikidata.org/sparql"


# ------------------------------------------------------------------ réseau
def telecharger(url, donnees=None, accept=None, essais=5):
    """GET (ou POST si donnees) avec reprises espacées. Renvoie des octets."""
    attente = 4
    for n in range(essais):
        req = urllib.request.Request(url, data=donnees, headers={
            "User-Agent": UA, "Accept-Encoding": "gzip",
            **({"Accept": accept} if accept else {}),
            **({"Content-Type": "application/x-www-form-urlencoded"} if donnees else {}),
        })
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                brut = r.read()
                codage = r.headers.get("Content-Encoding", "")
                if codage == "gzip":
                    brut = gzip.decompress(brut)
                elif codage == "zstd":          # PeriodO répond toujours ainsi
                    brut = dezstd(brut)
                return brut
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raison = f"HTTP {e.code}"
            if e.code == 429 and e.headers.get("Retry-After", "").isdigit():
                attente = max(attente, int(e.headers["Retry-After"]))
        except Exception as e:                                  # délai, réseau
            raison = str(e)
        if n == essais - 1:
            raise RuntimeError(f"{url[:90]} : {raison}")
        print(f"   … {raison}, nouvel essai dans {attente} s")
        time.sleep(attente)
        attente *= 2


def dezstd(brut):
    try:
        from compression import zstd                    # Python 3.14 et plus
        return zstd.decompress(brut)
    except ImportError:
        import zstandard                                # pip install zstandard
        return zstandard.ZstdDecompressor().decompressobj().decompress(brut)


def sparql(requete):
    corps = urllib.parse.urlencode({"query": requete}).encode()
    brut = telecharger(SPARQL, corps, "application/sparql-results+json")
    time.sleep(1)                       # politesse envers le service public
    lignes = []
    for b in json.loads(brut)["results"]["bindings"]:
        lignes.append({k: v["value"] for k, v in b.items()})
    return lignes


def qid(uri):
    return uri.rsplit("/", 1)[-1]


def par_paquets(liste, n):
    for i in range(0, len(liste), n):
        yield liste[i:i + n]


# ---------------------------------------------------------------- écriture
def ecrire(nom, banque, licence, objets, minimum):
    """Écrit sources/<nom>.json sauf si la récolte paraît tronquée."""
    chemin = os.path.join(DOSSIER, nom + ".json")
    avant = 0
    try:
        with open(chemin, encoding="utf-8") as f:
            avant = len(json.load(f)["objets"])
    except (OSError, ValueError, KeyError):
        pass
    if len(objets) < minimum or len(objets) < avant * 0.7:
        print(f"::warning::{banque} : {len(objets)} objets seulement "
              f"(précédent : {avant}) — fichier conservé tel quel.")
        return False
    objets.sort(key=lambda o: (o["piste"], o["debut"], o["nom"]))
    os.makedirs(DOSSIER, exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        f.write('{"banque":' + json.dumps(banque, ensure_ascii=False) +
                ',"licence":' + json.dumps(licence, ensure_ascii=False) +
                ',"recolte":"' + date.today().isoformat() + '","objets":[\n')
        f.write(",\n".join(json.dumps(o, ensure_ascii=False, separators=(",", ":"))
                           for o in objets))
        f.write("\n]}\n")
    pistes = Counter(o["piste"] for o in objets)
    print(f"{chemin} : {len(objets)} objets sur {len(pistes)} pistes "
          f"(précédent : {avant})")
    return True


PRECISION_WD = {11: "jour", 10: "mois", 9: "année", 8: "décennie",
                7: "siècle", 6: "millénaire"}


def gregorien_vers_julien(a, m, j):
    """Date grégorienne proleptique → date julienne (années astronomiques)."""
    # numéro de jour julien du calendrier grégorien…
    x = (14 - m) // 12
    y, mm = a + 4800 - x, m + 12 * x - 3
    jj = j + (153 * mm + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
    # …puis retour par le calendrier julien
    c = jj + 32082
    d = (4 * c + 3) // 1461
    e = c - 1461 * d // 4
    n = (5 * e + 2) // 153
    return d - 4800 + n // 10, n + 3 - 12 * (n // 10), e - (153 * n + 2) // 5 + 1


def date_wd(valeur, precision, julien=False):
    """« -0489-09-12T00:00:00Z » → (année historique, mois, jour, précision).

    Le service SPARQL numérote les années à la manière astronomique (0 = 1 av.
    J.-C.) ; la page compte sans an zéro, comme les historiens. Il convertit
    aussi en grégorien les dates saisies dans le calendrier julien : on les
    y ramène, puisque c'est sous cette forme que les historiens les citent
    (Hastings le 14 octobre 1066, non le 20).
    """
    m = re.match(r"^(-?)(\d+)-(\d\d)-(\d\d)", valeur)
    if not m:
        return None
    an = int(m.group(2)) * (-1 if m.group(1) else 1)
    p = int(precision or 9)
    if p < 6:
        return None                       # au-delà du millénaire : hors sujet
    mois, jour = int(m.group(3)), int(m.group(4))
    if julien and p >= 11:
        an, mois, jour = gregorien_vers_julien(an, mois, jour)
    if an <= 0:
        an -= 1
    mois = mois if p >= 10 else 0
    jour = jour if p >= 11 else 0
    return an, mois, jour, PRECISION_WD.get(p, "année"), bool(julien and p >= 11)


# =================================================================== WIKIDATA
# (classe, type affiché, seuil de notoriété = nombre minimal de Wikipédias,
#  piste par défaut quand aucun pays n'est identifiable)
CLASSES = [
    ("Q178561", "Bataille", 18, GUERRES),
    ("Q188055", "Siège", 15, GUERRES),
    ("Q198", "Guerre", 18, GUERRES),
    ("Q124734", "Rébellion", 15, AUTRES),
    ("Q10931", "Révolution", 12, AUTRES),
    ("Q45382", "Coup d'État", 15, AUTRES),
    ("Q131569", "Traité", 18, AUTRES),
    ("Q3882219", "Assassinat", 20, AUTRES),
    ("Q3199915", "Massacre", 25, AUTRES),
    ("Q3024240", "État historique", 22, AUTRES),
    ("Q8065", "Catastrophe naturelle", 20, AUTRES),
    ("Q3839081", "Catastrophe", 30, AUTRES),
    ("Q12184", "Pandémie", 12, AUTRES),
    ("Q44512", "Épidémie", 20, AUTRES),
]
TYPES_GUERRE = {"Bataille", "Siège", "Guerre"}


def majuscule(t):
    return t[:1].upper() + t[1:] if t else t


def choisir_piste(pistes, defaut):
    """Un ou deux pays : le premier. Davantage : la piste générique du type,
    les régions concernées restant visibles par les rubans de couleur."""
    if not pistes:
        return defaut
    return pistes[0] if len(pistes) <= 2 else defaut


def recolter_wikidata():
    entites = {}
    for classe, genre, seuil, defaut in CLASSES:
        print(f"Wikidata : {genre} (≥ {seuil} Wikipédias)…")
        try:
            rangs = sparql(f"""
SELECT ?e ?sl ?en ?fr ?enD ?frD ?frA ?enA WHERE {{
  ?e wdt:P31/wdt:P279* wd:{classe} ; wikibase:sitelinks ?sl .
  FILTER(?sl >= {seuil})
  OPTIONAL {{ ?e rdfs:label ?en FILTER(lang(?en) = "en") }}
  OPTIONAL {{ ?e rdfs:label ?fr FILTER(lang(?fr) = "fr") }}
  OPTIONAL {{ ?e schema:description ?enD FILTER(lang(?enD) = "en") }}
  OPTIONAL {{ ?e schema:description ?frD FILTER(lang(?frD) = "fr") }}
  OPTIONAL {{ ?frA schema:about ?e ; schema:isPartOf <https://fr.wikipedia.org/> }}
  OPTIONAL {{ ?enA schema:about ?e ; schema:isPartOf <https://en.wikipedia.org/> }}
}}""")
        except RuntimeError as err:
            print(f"::warning::Wikidata, {genre} : {err}")
            continue
        for r in rangs:
            q = qid(r["e"])
            if q in entites:
                continue                  # déjà vu sous une classe plus parlante
            entites[q] = {"genre": genre, "defaut": defaut, "sl": int(r["sl"]),
                          "en": r.get("en", ""), "fr": r.get("fr", ""),
                          "enD": r.get("enD", ""), "frD": r.get("frD", ""),
                          "frA": r.get("frA", ""), "enA": r.get("enA", "")}
        print(f"   {len(rangs)} lignes, {len(entites)} entités au total")

    # Dates et pays, par paquets : une seule grosse requête dépasserait le
    # délai de 60 s du service.
    dates = defaultdict(dict)
    pays = defaultdict(list)
    ids = sorted(entites)
    for paquet in par_paquets(ids, 200):
        valeurs = " ".join("wd:" + q for q in paquet)
        for prop in ("P585", "P580", "P582", "P571", "P576"):
            for r in sparql(f"""
SELECT ?e ?t ?p ?cal WHERE {{
  VALUES ?e {{ {valeurs} }}
  ?e p:{prop} ?st . ?st psv:{prop} ?v .
  ?v wikibase:timeValue ?t ; wikibase:timePrecision ?p ; wikibase:timeCalendarModel ?cal .
  FILTER NOT EXISTS {{ ?st wikibase:rank wikibase:DeprecatedRank }}
}}"""):
                d = date_wd(r["t"], r["p"], r.get("cal", "").endswith("Q1985786"))
                if not d:
                    continue
                q = qid(r["e"])
                ancien = dates[q].get(prop)
                # plusieurs valeurs : la plus ancienne pour un début, la plus
                # tardive pour une fin
                if ancien is None or (d[0] < ancien[0] if prop in ("P585", "P580", "P571")
                                      else d[0] > ancien[0]):
                    dates[q][prop] = d
        # pays : chaque chemin à part, sans libellés (sinon délai dépassé)
        for ordre, chemin in ((1, "wdt:P17"), (2, "wdt:P276/wdt:P17"),
                              (3, "wdt:P36/wdt:P17"), (4, "wdt:P30")):
            for r in sparql(f"SELECT ?e ?p WHERE {{ VALUES ?e {{ {valeurs} }} ?e {chemin} ?p }}"):
                pays[qid(r["e"])].append((ordre, qid(r["p"])))
        print(f"   dates et pays : {min(len(ids), ids.index(paquet[-1]) + 1)}/{len(ids)}")

    # noms anglais des pays rencontrés
    noms_pays = {}
    tous = sorted({p for l in pays.values() for _, p in l})
    for paquet in par_paquets(tous, 300):
        valeurs = " ".join("wd:" + q for q in paquet)
        for r in sparql(f"""SELECT ?p ?l WHERE {{ VALUES ?p {{ {valeurs} }}
  ?p rdfs:label ?l FILTER(lang(?l) = "en") }}"""):
            noms_pays[qid(r["p"])] = r["l"]
    for q in pays:
        pays[q] = [(o, noms_pays.get(p, "")) for o, p in pays[q]]

    objets = []
    for q, e in entites.items():
        d = dates.get(q, {})
        debut = d.get("P585") or d.get("P580") or d.get("P571")
        fin = d.get("P582") or d.get("P576")
        if not debut or not (e["en"] or e["fr"]):
            continue
        if fin and (fin[0] < debut[0] or fin == debut):
            fin = None
        # piste : premier pays rattachable, par ordre de fiabilité de la source
        cands = sorted(set(pays.get(q, [])))
        pistes = []
        for _, nom in cands:
            p = piste_pour(nom, debut[0])
            if p and p not in pistes:
                pistes.append(p)
        piste = choisir_piste(pistes, e["defaut"])
        liens = [u for u in (e["frA"], e["enA"]) if u]
        notes = e["frD"] or e["enD"]
        if e["frD"] and e["enD"]:
            notes = e["frD"][0].upper() + e["frD"][1:] + "\n" + e["enD"]
        en, fr = majuscule(e["en"]), majuscule(e["fr"])
        objets.append({
            "nom": en or fr, "fr": fr if fr != en else "",
            "piste": piste, "ensembles": pistes[:6] if len(pistes) > 1 else [],
            "debut": debut[0], "mois": debut[1], "jour": debut[2],
            "fin": fin[0] if fin else None,
            "moisF": fin[1] if fin else 0, "jourF": fin[2] if fin else 0,
            "precision": debut[3], "type": e["genre"],
            "julien": debut[4] or bool(fin and fin[4]),
            "notes": notes, "url": "https://www.wikidata.org/wiki/" + q,
            "liens": liens, "qid": q, "notoriete": e["sl"],
        })
    print(f"Wikidata : {len(objets)} objets datés sur {len(entites)} entités")
    return ecrire("wikidata", "Wikidata", "Wikidata (CC0)", objets, 1000)


# ========================================================= RÈGNES ET OFFICES
# Fonctions occupées (P39) avec début et fin : règnes des monarques, mandats
# des chefs d'État et de gouvernement. Chaque objet est le règne ou le mandat,
# la notice donne la naissance et la mort de la personne.
MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
           "août", "septembre", "octobre", "novembre", "décembre"]


def siecle_fr(an):
    """1701 av. J.-C. → « XVIIIe siècle av. J.-C. »."""
    n = (abs(an) - 1) // 100 + 1
    rom = ""
    for v, l in ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
                 (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= v:
            rom += l
            n -= v
    return rom + ("er" if rom == "I" else "e") + " siècle" + (" av. J.-C." if an < 0 else "")


def date_fr(d):
    """(an, mois, jour, précision, julien) → « 1er janvier 1515 (julien) »."""
    an, mois, jour, prec, julien = d
    a = f"{-an} av. J.-C." if an < 0 else str(an)
    if prec in ("siècle", "millénaire"):
        return siecle_fr(an)
    if prec == "décennie":
        return f"vers {a}"
    t = a
    if mois:
        t = f"{MOIS_FR[mois - 1]} {a}"
        if jour:
            t = f"{'1er' if jour == 1 else jour} {t}"
    return t + (" (julien)" if julien else "")


GROUPES_FONCTIONS = [
    # (racine de la classe de fonctions, nature, seuil de notoriété)
    ("Q116", "r", 25),          # monarque
    ("Q48352", "o", 40),        # chef d'État
    ("Q14212", "o", 40),        # Premier ministre
]


def recolter_regnes():
    fonctions = {}                       # QID de fonction → nature
    for racine, nature, _ in GROUPES_FONCTIONS:
        for r in sparql(f"SELECT DISTINCT ?f WHERE {{ ?f wdt:P279* wd:{racine} }}"):
            fonctions.setdefault(qid(r["f"]), nature)    # monarque prioritaire
    print(f"Règnes et offices : {len(fonctions)} fonctions")

    mandats = {}                         # (personne, fonction, début) → mandat
    for racine, nature, seuil in GROUPES_FONCTIONS:
        liste = sorted(f for f, n in fonctions.items() if n == nature)
        for paquet in par_paquets(liste, 300):
            valeurs = " ".join("wd:" + q for q in paquet)
            for r in sparql(f"""
SELECT ?p ?f ?d ?dp ?dc ?e ?ep ?ec WHERE {{
  VALUES ?f {{ {valeurs} }}
  ?p p:P39 ?st . ?st ps:P39 ?f .
  ?st pqv:P580 ?vd . ?vd wikibase:timeValue ?d ; wikibase:timePrecision ?dp ;
                         wikibase:timeCalendarModel ?dc .
  OPTIONAL {{ ?st pqv:P582 ?ve . ?ve wikibase:timeValue ?e ; wikibase:timePrecision ?ep ;
                                   wikibase:timeCalendarModel ?ec . }}
  ?p wikibase:sitelinks ?sl FILTER(?sl >= {seuil})
}}"""):
                d = date_wd(r["d"], r["dp"], r["dc"].endswith("Q1985786"))
                if not d:
                    continue
                e = date_wd(r["e"], r["ep"], r["ec"].endswith("Q1985786")) if r.get("e") else None
                cle = (qid(r["p"]), qid(r["f"]), d[0])
                if cle not in mandats or (e and not mandats[cle]["fin"]):
                    mandats[cle] = {"debut": d, "fin": e, "nature": fonctions[qid(r["f"])]}
        print(f"   {racine} : {len(mandats)} mandats au total")

    personnes = sorted({k[0] for k in mandats})
    postes = sorted({k[1] for k in mandats})
    infos = defaultdict(dict)
    for paquet in par_paquets(personnes, 200):
        valeurs = " ".join("wd:" + q for q in paquet)
        for r in sparql(f"""
SELECT ?x ?en ?fr ?frA ?enA WHERE {{ VALUES ?x {{ {valeurs} }}
  OPTIONAL {{ ?x rdfs:label ?en FILTER(lang(?en) = "en") }}
  OPTIONAL {{ ?x rdfs:label ?fr FILTER(lang(?fr) = "fr") }}
  OPTIONAL {{ ?frA schema:about ?x ; schema:isPartOf <https://fr.wikipedia.org/> }}
  OPTIONAL {{ ?enA schema:about ?x ; schema:isPartOf <https://en.wikipedia.org/> }}
}}"""):
            infos[qid(r["x"])].update({k: r[k] for k in ("en", "fr", "frA", "enA") if k in r})
        for prop, cle in (("P569", "naissance"), ("P570", "mort")):
            for r in sparql(f"""
SELECT ?x ?t ?pr ?cal WHERE {{ VALUES ?x {{ {valeurs} }}
  ?x p:{prop}/psv:{prop} ?v . ?v wikibase:timeValue ?t ; wikibase:timePrecision ?pr ;
                                 wikibase:timeCalendarModel ?cal . }}"""):
                d = date_wd(r["t"], r["pr"], r["cal"].endswith("Q1985786"))
                if d and cle not in infos[qid(r["x"])]:
                    infos[qid(r["x"])][cle] = d
        print(f"   personnes : {min(len(personnes), personnes.index(paquet[-1]) + 1)}/{len(personnes)}")
    # fonctions : libellés et territoire (P1001), pour choisir la piste
    territoire = defaultdict(list)
    for paquet in par_paquets(postes, 300):
        valeurs = " ".join("wd:" + q for q in paquet)
        for r in sparql(f"""
SELECT ?x ?en ?fr WHERE {{ VALUES ?x {{ {valeurs} }}
  OPTIONAL {{ ?x rdfs:label ?en FILTER(lang(?en) = "en") }}
  OPTIONAL {{ ?x rdfs:label ?fr FILTER(lang(?fr) = "fr") }} }}"""):
            infos[qid(r["x"])].update({k: r[k] for k in ("en", "fr") if k in r})
        for r in sparql(f"""
SELECT ?x ?l WHERE {{ VALUES ?x {{ {valeurs} }}
  {{ ?x wdt:P1001 ?t }} UNION {{ ?x wdt:P17 ?t }}
  ?t rdfs:label ?l FILTER(lang(?l) = "en") }}"""):
            territoire[qid(r["x"])].append(r["l"])

    objets, sans_piste = [], 0
    for (p, f, _), m in mandats.items():
        per, fct = infos.get(p, {}), infos.get(f, {})
        nom_en, nom_fr = majuscule(per.get("en", "")), majuscule(per.get("fr", ""))
        if not (nom_en or nom_fr):
            continue
        d, e = m["debut"], m["fin"]
        if e and e[0] < d[0]:
            e = None
        piste = None
        for t in territoire.get(f, []) + [fct.get("en", "")]:
            piste = piste_pour(t, d[0])
            if piste:
                break
        if not piste:
            sans_piste += 1
            continue
        vie = []
        if per.get("naissance"):
            vie.append("Naissance : " + date_fr(per["naissance"]))
        if per.get("mort"):
            vie.append("Mort : " + date_fr(per["mort"]))
        fonction = majuscule(fct.get("fr") or fct.get("en") or "")
        objets.append({
            "nom": nom_en or nom_fr, "fr": nom_fr if nom_fr != nom_en else "",
            "piste": piste, "debut": d[0], "mois": d[1], "jour": d[2],
            "fin": e[0] if e else None, "moisF": e[1] if e else 0,
            "jourF": e[2] if e else 0, "precision": d[3],
            "type": "Règne" if m["nature"] == "r" else "Office",
            "nature": m["nature"], "julien": d[4] or bool(e and e[4]),
            "vie": " · ".join(vie),
            "notes": "\n".join(x for x in (fonction, " · ".join(vie)) if x),
            "url": "https://www.wikidata.org/wiki/" + p,
            "liens": [u for u in (per.get("frA"), per.get("enA")) if u],
        })
    print(f"Règnes et offices : {len(objets)} objets ({sans_piste} sans piste connue)")
    return ecrire("wikidata_regnes", "Wikidata", "Wikidata (CC0)", objets, 500)


# ================================================================== WIKIPÉDIA
# (langue, titre de la page, piste). Les titres absents ou devenus des
# redirections vers autre chose qu'une chronologie sont simplement ignorés.
PAGES = [
    ("fr", "Chronologie de la France", "France"),
    ("fr", "Chronologie de la Russie", "Eastern Europe – Russia"),
    ("fr", "Chronologie de l'Égypte", "Egypt"),
    ("fr", "Chronologie du Brésil", "South America"),
    ("fr", "Chronologie de la Tunisie", "Africa – Tunisia"),
    ("fr", "Chronologie du Liban", "Mesopotamia & Levant – Lebanon"),
    ("fr", "Chronologie de l'Afrique du Sud", "Africa – South Africa"),
    ("fr", "Chronologie de l'Arménie", "West Asia – Armenia"),
    ("fr", "Chronologie de l'Islande", "Northern Europe – Iceland"),
    ("fr", "Chronologie de la Pologne", "Eastern Europe – Poland"),
    ("fr", "Chronologie du Portugal", "Southern Europe – Portugal"),
    ("fr", "Chronologie du Pérou", "South America"),
    ("fr", "Chronologie des États-Unis", "Uk & Ireland – UNITED STATES OF AMERICA"),
    ("fr", "Chronologie du Québec", "Canada"),
    ("fr", "Chronologie de l'Acadie", "Canada"),
    ("fr", "Chronologie de la République romaine", "Rome And Persia – Roman Era"),
    ("fr", "Chronologie de l'Empire romain", "Rome And Persia – Roman Era"),
    ("fr", "Chronologie de la Slovénie", "Southern Europe – former Yugoslavia"),
    ("fr", "Chronologie de la Grèce antique", "Greece"),
    ("fr", "Chronologie de l'Espagne", "Southern Europe – Spain"),
    ("fr", "Chronologie de l'Allemagne", "Germany"),
    ("fr", "Chronologie de l'Italie", "European Monarchies – RENAISSANCE ITALY"),
    ("fr", "Chronologie du Japon", "East Asia – Japan"),
    ("fr", "Chronologie de la Chine", "China"),
    ("fr", "Chronologie de l'Inde", "India – India, Pakistan & Bangladesh"),
    ("fr", "Chronologie de l'Iran", "Rome And Persia – PERSIA (Iran)"),
    ("fr", "Chronologie de l'Algérie", "Africa – Algeria"),
    ("fr", "Chronologie du Maroc", "Africa – Morocco"),
    ("fr", "Chronologie du Mexique", "Mesoamerica"),
    ("fr", "Chronologie du Canada", "Canada"),
    ("fr", "Chronologie de la Belgique", "Western Europe – Belgium"),
    ("fr", "Chronologie de la Suisse", "Western Europe – Switzerland"),
    ("fr", "Chronologie de l'Irlande", "Uk & Ireland – IRELAND"),
    ("fr", "Chronologie du Royaume-Uni", "Uk & Ireland"),
    ("fr", "Chronologie de la Turquie", "Anatolia & Turkey – Anatolia (modern Turkey)"),
    ("fr", "Chronologie de l'Empire ottoman", "Anatolia & Turkey – Anatolia (modern Turkey)"),
    ("fr", "Chronologie du Viêt Nam", "Southeast Asia – Vietnam"),
    ("fr", "Chronologie de la Corée", "East Asia – Korea"),
    ("fr", "Chronologie de Haïti", "Caribbean – Caribbean Region"),
    ("fr", "Chronologie du Sénégal", "Africa – Senegal"),
    ("fr", "Chronologie de Madagascar", "Africa – Madagascar"),
]
_EN = {
    "French": "France", "German": "Germany", "British": "Uk & Ireland",
    "English": "Uk & Ireland", "Scottish": "Uk & Ireland", "Welsh": "Uk & Ireland",
    "Irish": "Uk & Ireland – IRELAND",
    "United States": "Uk & Ireland – UNITED STATES OF AMERICA",
    "Canadian": "Canada", "Russian": "Eastern Europe – Russia",
    "Ukrainian": "Eastern Europe – Ukraine", "Polish": "Eastern Europe – Poland",
    "Hungarian": "Eastern Europe – Hungary", "Romanian": "Eastern Europe – Romania",
    "Bulgarian": "Eastern Europe – Bulgaria", "Belarusian": "Eastern Europe – Belarus",
    "Moldovan": "Eastern Europe – Moldova", "Czech": "Eastern Europe – Czechoslovakia",
    "Slovak": "Eastern Europe – Czechoslovakia",
    "Serbian": "Southern Europe – former Yugoslavia",
    "Croatian": "Southern Europe – former Yugoslavia",
    "Bosnian": "Southern Europe – former Yugoslavia",
    "Slovenian": "Southern Europe – former Yugoslavia",
    "Albanian": "Southern Europe – Albania", "Maltese": "Southern Europe – Malta",
    "Portuguese": "Southern Europe – Portugal", "Spanish": "Southern Europe – Spain",
    "Italian": "European Monarchies – RENAISSANCE ITALY",
    "Greek": "Greece", "Ancient Greek": "Greece",
    "Dutch": "Western Europe – The Netherlands", "Belgian": "Western Europe – Belgium",
    "Luxembourg": "Western Europe – Luxembourg", "Austrian": "Western Europe – Austria",
    "Swiss": "Western Europe – Switzerland", "Monaco": "Western Europe – Monaco",
    "Danish": "Northern Europe – Denmark", "Norwegian": "Northern Europe – Norway",
    "Swedish": "Northern Europe – Sweden", "Finnish": "Northern Europe – Finland",
    "Icelandic": "Northern Europe – Iceland", "Estonian": "Northern Europe – Estonia",
    "Latvian": "Northern Europe – Latvia", "Lithuanian": "Northern Europe – Lithuania",
    "Turkish": "Anatolia & Turkey – Anatolia (modern Turkey)",
    "Ottoman": "Anatolia & Turkey – Anatolia (modern Turkey)",
    "Armenian": "West Asia – Armenia", "Azerbaijani": "West Asia – Azerbaijan",
    "Georgian": "West Asia – Georgia", "Iranian": "Rome And Persia – PERSIA (Iran)",
    "Iraqi": "Mesopotamia & Levant – Iraq", "Syrian": "Mesopotamia & Levant – Syria",
    "Jordanian": "Mesopotamia & Levant – Jordan",
    "Lebanese": "Mesopotamia & Levant – Lebanon",
    "Israeli": "Mesopotamia & Levant – Israel",
    "Palestinian": "Mesopotamia & Levant – Palestine",
    "Cypriot": "Mesopotamia & Levant – Cyprus",
    "Saudi Arabian": "Arabian Peninsula – Central", "Yemeni": "Arabian Peninsula – South",
    "Omani": "Arabian Peninsula – East", "Kuwaiti": "Arabian Peninsula – North",
    "Bahraini": "Arabian Peninsula – East", "Qatari": "Arabian Peninsula – East",
    "Afghan": "South Asia – Afghanistan", "Nepalese": "South Asia – Nepal",
    "Sri Lankan": "South Asia – Sri Lanka", "Bhutanese": "South Asia – Bhutan",
    "Indian": "India – India, Pakistan & Bangladesh",
    "Pakistani": "India – India, Pakistan & Bangladesh",
    "Bangladeshi": "India – India, Pakistan & Bangladesh",
    "Kazakh": "Central Asia – Kazakhstan", "Kyrgyz": "Central Asia – Kyrgyzstan",
    "Tajik": "Central Asia – Tajikistan", "Turkmen": "Central Asia – Turkmenistan",
    "Uzbek": "Central Asia – Uzbekistan", "Mongolian": "East Asia – Mongolia",
    "Chinese": "China", "Taiwanese": "China", "Hong Kong": "China",
    "Japanese": "East Asia – Japan", "Korean": "East Asia – Korea",
    "South Korean": "East Asia – Korea", "North Korean": "East Asia – Korea",
    "Vietnamese": "Southeast Asia – Vietnam", "Cambodian": "Southeast Asia – Cambodia",
    "Laotian": "Southeast Asia – Laos", "Thai": "Southeast Asia – Thailand",
    "Burmese": "Southeast Asia – Myanmar", "Malaysian": "Southeast Asia – Malaysia",
    "Singaporean": "Southeast Asia – Singapore",
    "Indonesian": "Southeast Asia – Indonesia",
    "Philippine": "Southeast Asia – The Philippines",
    "Bruneian": "Southeast Asia – Brunei", "East Timorese": "Southeast Asia – East Timor",
    "Egyptian": "Egypt", "Libyan": "Africa – Libya", "Tunisian": "Africa – Tunisia",
    "Algerian": "Africa – Algeria", "Moroccan": "Africa – Morocco",
    "Sudanese": "Africa – Sudan", "South Sudanese": "Africa – Sudan",
    "Ethiopian": "Africa – Ethiopia", "Eritrean": "Africa – Eritrea",
    "Somali": "Africa – Somalia", "Djiboutian": "Africa – Djibouti",
    "Kenyan": "Africa – Kenya", "Ugandan": "Africa – Uganda",
    "Tanzanian": "Africa – Tanzania", "Rwandan": "Africa – Rwanda",
    "Burundian": "Africa – Burundi", "Malagasy": "Africa – Madagascar",
    "Mozambican": "Africa – Mozambique", "Malawian": "Africa – Malawi",
    "Zambian": "Africa – Zambia", "Zimbabwean": "Africa – Zimbabwe",
    "Mauritian": "Africa – Mauritius", "Seychellois": "Africa – Seychelles",
    "Nigerian": "Africa – Nigeria", "Ghanaian": "Africa – Ghana",
    "Senegalese": "Africa – Senegal", "Malian": "Africa – Mali",
    "Nigerien": "Africa – Niger", "Burkinabé": "Africa – Burkina Faso",
    "Ivorian": "Africa – Côte D'Ivoire", "Guinean": "Africa – Guinea",
    "Liberian": "Africa – Liberia", "Sierra Leonean": "Africa – Sierra Leone",
    "Togolese": "Africa – Togo", "Beninese": "Africa – Benin",
    "Gambian": "Africa – Gambia", "Mauritanian": "Africa – Mauritania",
    "Cape Verdean": "Africa – Cape Verde", "Cameroonian": "Africa – Cameroon",
    "Chadian": "Africa – Chad", "Gabonese": "Africa – Gabon",
    "Angolan": "Africa – Angola", "Namibian": "Africa – Namibia",
    "Botswana": "Africa – Botswana", "South African": "Africa – South Africa",
    "Lesotho": "Africa – Lesotho",
    "Mexican": "Mesoamerica", "Guatemalan": "Mesoamerica",
    "Honduran": "Mesoamerica", "Salvadoran": "Mesoamerica",
    "Nicaraguan": "Mesoamerica", "Costa Rican": "Mesoamerica",
    "Panamanian": "Mesoamerica", "Belizean": "Mesoamerica",
    "Cuban": "Caribbean – Caribbean Region", "Haitian": "Caribbean – Caribbean Region",
    "Dominican Republic": "Caribbean – Caribbean Region",
    "Jamaican": "Caribbean – Caribbean Region",
    "Puerto Rican": "Caribbean – Caribbean Region",
    "Brazilian": "South America", "Argentine": "South America",
    "Chilean": "South America", "Peruvian": "South America",
    "Colombian": "South America", "Venezuelan": "South America",
    "Ecuadorian": "South America", "Bolivian": "South America",
    "Paraguayan": "South America", "Uruguayan": "South America",
    "Australian": "Australia – Australia, New Zealand and Oceania",
    "New Zealand": "Australia – Australia, New Zealand and Oceania",
    "Fijian": "Australia – Australia, New Zealand and Oceania",
}
PAGES += [("en", f"Timeline of {adj} history", piste) for adj, piste in _EN.items()]
PAGES += [
    ("en", "Timeline of ancient Rome", "Rome And Persia – Roman Era"),
    ("en", "Timeline of the Roman Empire", "Rome And Persia – Roman Era"),
    ("en", "Timeline of the Byzantine Empire", "Rome And Persia – Roman Era"),
    ("en", "Timeline of ancient Egypt", "Egypt"),
    ("en", "Timeline of ancient Greece", "Greece"),
    ("en", "Timeline of the Ottoman Empire", "Anatolia & Turkey – Anatolia (modern Turkey)"),
    ("en", "Timeline of the Mughal Empire", "India – India, Pakistan & Bangladesh"),
    ("en", "Timeline of the Holy Roman Empire", "Germany"),
]

MOIS = {m: i + 1 for i, m in enumerate(
    "january february march april may june july august september october november december".split())}
MOIS.update({m: i + 1 for i, m in enumerate(
    "janvier février mars avril mai juin juillet août septembre octobre novembre décembre".split())})
MOIS.update({"fevrier": 2, "aout": 8, "decembre": 12, "1er": None})

RE_AV = r"(?:av\.?\s*J\.?-?C\.?|avant\s+(?:J\.?-?C\.?|notre\s+ère|l['’]ère\s+chrétienne)|BCE?|B\.C\.E?\.?)"
RE_AN = re.compile(
    r"^\s*(?:(?P<circa>c\.|ca\.|circa|vers|env\.|\{\{circa\}\}|~)\s*)?"
    r"(?P<moins>[-−–])?(?P<an>\d{1,5})(?:\s*(?:[-–—/]|à|to)\s*(?P<fin>\d{1,5}))?"
    r"(?:\s*(?P<av>" + RE_AV + r"))?(?:\s*(?:AD|CE|apr\.?\s*J\.?-?C\.?))?", re.I)


def lire_annee(txt, av_par_defaut=False):
    """« 1250-1382 », « 3000 BC », « vers -500 » → (début, fin, circa) ou None."""
    m = RE_AN.match(txt or "")
    if not m:
        return None
    an = int(m.group("an"))
    fin = int(m.group("fin")) if m.group("fin") else None
    av = bool(m.group("av")) or bool(m.group("moins")) or av_par_defaut
    if an == 0 or an > 2100:
        return None
    if av:
        an = -an
        if fin is not None:
            fin = -fin
    if fin is not None and fin < an:
        fin = None if not av else fin
    if fin is not None and fin < an:
        fin = None
    return an, fin, bool(m.group("circa"))


def lire_jour(txt):
    """« 27 November », « 6 juillet », « Mai », « May 5 » → (mois, jour)."""
    t = sans_balises(txt or "").lower().replace("1er", "1")
    mois = jour = 0
    for mot in re.findall(r"[a-zéûô]+", t):
        if MOIS.get(mot):
            mois = MOIS[mot]
            break
    if mois:
        n = re.search(r"\b(\d{1,2})\b", t)
        if n and 1 <= int(n.group(1)) <= 31:
            jour = int(n.group(1))
    return mois, jour


GABARITS_TEXTE = {"souverain2", "souverain", "souverain-", "noble", "nobr", "nowrap",
                  "lang", "langue", "page h'", "page h", "lien", "japonais",
                  "unité", "nombre", "sp", "small", "abbr", "w", "nihongo",
                  "transl", "lang-fr", "date", "date-", "ill", "sic", "lnobr"}


def _gabarit(contenu):
    """Contenu d'un {{…}} → texte à garder (souvent vide)."""
    morceaux = [m.strip() for m in contenu.split("|")]
    nom = morceaux[0].lower()
    params = [m for m in morceaux[1:] if "=" not in m]
    if nom in ("s-", "s", "-s-", "siècle", "s2-"):
        return (params[0] + "e siècle") if params else ""
    if nom in ("er", "e", "ier", "re", "ii", "iii"):
        return ""
    if nom.startswith("lang") or nom in ("langue", "transl"):
        return params[-1] if params else ""
    if nom in ("unité", "nombre", "date", "date-"):
        return " ".join(params)
    if nom in GABARITS_TEXTE:
        return params[0] if params else ""
    if nom in ("circa", "c.", "c"):
        return "vers "
    if re.fullmatch(r"[ivxlcdm]+(e|er)?", nom):        # {{XVe}}, {{Ier}}
        return morceaux[0] + (" " + params[0] if params else "")
    return ""


def sans_balises(t):
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    t = re.sub(r"<ref[^>/]*/>", "", t)
    t = re.sub(r"<ref[^>]*>.*?</ref>", "", t, flags=re.S)
    for _ in range(4):                                  # gabarits imbriqués
        t2 = re.sub(r"\{\{([^{}]*)\}\}", lambda m: _gabarit(m.group(1)), t)
        if t2 == t:
            break
        t = t2
    t = re.sub(r"\[\[(?:Fichier|File|Image|Catégorie|Category):[^\]]*\]\]", "", t, flags=re.I)
    t = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"\[\[([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"\[https?://\S+\s+([^\]]*)\]", r"\1", t)
    t = re.sub(r"\[https?://\S+\]", "", t)
    t = re.sub(r"'{2,}", "", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t).replace(" ", " ")
    return re.sub(r"\s+", " ", t).strip(" :;,–-")


RE_LIEN_EVT = re.compile(r"^\s*(?:''+)?\[\[([^\]|#]+)(?:\|([^\]]+))?\]\](?:''+)?\s*[:：]")


def entree(texte_brut, piste, an, fin, circa, mois, jour, url, langue):
    """Une ligne de chronologie → objet, ou None si inexploitable."""
    lien = RE_LIEN_EVT.match(texte_brut)
    texte = sans_balises(texte_brut)
    if len(texte) < 8:
        return None
    article = ""
    if lien:
        # « ''[[Bataille de Vouillé]]'' : … » — l'événement a son article
        nom = sans_balises(lien.group(2) or lien.group(1))
        article = lien.group(1).strip()
        reste = sans_balises(texte_brut[lien.end():])
        notes = reste
    else:
        phrase = re.split(r"(?<=[a-zé\)])\.\s", texte, maxsplit=1)[0]
        nom = phrase if len(phrase) <= 110 else phrase[:105].rsplit(" ", 1)[0] + "…"
        notes = texte if texte != nom else ""
    if len(notes) > 350:
        notes = notes[:350].rsplit(" ", 1)[0] + "…"
    o = {"_poids": (3 if lien else 0) + min(texte_brut.count("[["), 5),
         "nom": nom if langue == "en" else "", "fr": nom if langue == "fr" else "",
         "piste": piste, "debut": an, "fin": fin, "mois": mois, "jour": jour,
         "precision": "jour" if jour else ("mois" if mois else "année"),
         "qual": "circa" if circa else "", "notes": notes, "url": url}
    for k in ("nom", "fr"):
        if o[k]:
            o[k] = o[k][0].upper() + o[k][1:]
    if not o["nom"]:
        o["nom"] = o["fr"]
    # articles cités dans la ligne : servent à reconnaître l'événement
    cites = []
    for cible in re.findall(r"\[\[([^\]|#]+)", texte_brut):
        cible = cible.strip()
        if ":" in cible or not cible:
            continue
        u = f"https://{langue}.wikipedia.org/wiki/" + urllib.parse.quote(
            (cible[:1].upper() + cible[1:]).replace(" ", "_"))
        if u not in cites:
            cites.append(u)
    o["cites"] = cites[:6]
    if article:
        o["article"] = f"https://{langue}.wikipedia.org/wiki/" + \
            urllib.parse.quote(article.replace(" ", "_")[:1].upper() + article.replace(" ", "_")[1:])
    return o


def analyser_page(wikitexte, piste, url, langue):
    """Tableaux « Année | Date | Événement » et listes à puces datées."""
    sortie = []
    av_section = False           # dans une section « avant J.-C. »
    an_courant = None
    lignes = wikitexte.split("\n")
    i = 0
    while i < len(lignes):
        l = lignes[i]
        titre = re.match(r"^=+\s*(.*?)\s*=+\s*$", l)
        if titre:
            av_section = bool(re.search(RE_AV + r"|avant notre|before", titre.group(1), re.I))
            an_courant = None
            i += 1
            continue
        if l.startswith("{|"):                       # ---------------- tableau
            fin_t = i + 1
            while fin_t < len(lignes) and not lignes[fin_t].startswith("|}"):
                fin_t += 1
            sortie += analyser_tableau(lignes[i:fin_t], piste, url, langue, av_section)
            i = fin_t + 1
            continue
        puce = re.match(r"^(\*+)\s*(.*)$", l)
        if puce:
            niveau, txt = len(puce.group(1)), puce.group(2)
            nu = sans_balises(txt)
            a = lire_annee(nu, av_section)
            if niveau == 1 and a:
                an_courant = a
                reste = re.sub(r"^[^:–—-]*?\d{1,5}[^:–—]*?(?:[:–—]|\s-\s)", "", txt, count=1) \
                    if re.search(r"[:–—]|\s-\s", txt) else ""
                if sans_balises(reste):
                    o = entree(reste, piste, a[0], a[1], a[2], 0, 0, url, langue)
                    if o:
                        sortie.append(o)
            elif niveau >= 2 and an_courant:
                m = re.match(r"^([^:]{2,25}?)\s*:\s*(.*)$", txt)
                mois = jour = 0
                corps = txt
                if m:
                    mois, jour = lire_jour(m.group(1))
                    if mois:
                        corps = m.group(2)
                o = entree(corps, piste, an_courant[0], an_courant[1], an_courant[2],
                           mois, jour, url, langue)
                if o:
                    sortie.append(o)
        i += 1
    return sortie


def cellules(rangee):
    """Lignes d'une rangée de tableau → [(texte, rowspan)]."""
    cel = []
    for l in rangee:
        if not l.startswith(("|", "!")) or l.startswith(("|-", "|+")):
            if cel and not l.startswith(("|-", "|+")):
                cel[-1] = (cel[-1][0] + " " + l, cel[-1][1])
            continue
        for c in re.split(r"\|\||!!", l[1:]):
            # « rowspan="2" valign="top" | 524 » : attributs avant la barre
            span = 1
            m = re.match(r'^\s*([a-z]+\s*=\s*"?[^|]*?"?\s*)+\|(?!\|)(.*)$', c, re.I)
            if m and "[[" not in c.split("|")[0]:
                attrs = c.split("|")[0]
                rs = re.search(r'rowspan\s*=\s*"?(\d+)', attrs, re.I)
                span = int(rs.group(1)) if rs else 1
                c = c[len(attrs) + 1:]
            cel.append((c.strip(), span))
    return cel


def analyser_tableau(bloc, piste, url, langue, av_section):
    rangees, courante = [], []
    for l in bloc[1:]:
        if l.startswith("|-"):
            if courante:
                rangees.append(courante)
            courante = []
        else:
            courante.append(l)
    if courante:
        rangees.append(courante)
    if not rangees:
        return []
    entete = [sans_balises(c).lower() for c, _ in cellules(
        [r for r in rangees[0] if r.startswith("!")])] if any(
        r.startswith("!") for r in rangees[0]) else []
    i_an = next((k for k, h in enumerate(entete) if h in ("year", "année", "an", "date")), None)
    i_date = next((k for k, h in enumerate(entete) if h in ("date", "jour") and k != i_an), None)
    i_evt = next((k for k, h in enumerate(entete) if "event" in h or "événement" in h
                  or "évènement" in h), None)
    if i_an is None or i_evt is None:
        return []
    ncol = len(entete)
    sortie = []
    reste_an = 0              # rangées encore couvertes par le rowspan de l'année
    an = None
    for r in rangees[1:] if entete else rangees:
        cel = cellules(r)
        if not cel:
            continue
        premiere = sans_balises(cel[0][0])
        if reste_an > 0 and len(cel) < ncol:
            cel = [("", 1)] + cel                      # l'année vient d'au-dessus
            reste_an -= 1
        elif len(cel) < ncol and lire_jour(premiere)[0] and not re.match(r"^\s*\d{3,4}\b", premiere):
            cel = [("", 1)] + cel                      # « 14 February » sans année
        else:
            texte_an, span = cel[0] if i_an == 0 else (cel[i_an][0] if i_an < len(cel) else "", 1)
            a = lire_annee(sans_balises(texte_an), av_section)
            if a and not lire_jour(sans_balises(texte_an))[0]:
                an = a
            reste_an = span - 1
        if an is None or len(cel) < 2:
            continue
        # L'événement est la dernière colonne de ces tableaux ; la date, s'il
        # y en a une, celle qui la précède.
        evt = cel[-1][0] if i_evt == ncol - 1 else (cel[i_evt][0] if i_evt < len(cel) else "")
        mois = jour = 0
        if i_date is not None and len(cel) >= 3:
            mois, jour = lire_jour(cel[-2][0] if i_evt == ncol - 1 else cel[i_date][0])
        if not evt or (lire_jour(evt)[0] and len(sans_balises(evt)) < 20):
            continue                                   # cellule de date égarée
        o = entree(evt, piste, an[0], an[1], an[2], mois, jour, url, langue)
        if o:
            sortie.append(o)
    return sortie


PAR_PAGE = 80


def recolter_wikipedia():
    objets, vues = [], set()
    pages_lues = 0
    for langue, titre, piste in PAGES:
        url = f"https://{langue}.wikipedia.org/wiki/" + urllib.parse.quote(titre.replace(" ", "_"))
        brut = None
        for _ in range(3):                                 # redirections
            try:
                brut = telecharger(f"https://{langue}.wikipedia.org/w/index.php?"
                                   + urllib.parse.urlencode({"title": titre, "action": "raw"}))
            except RuntimeError as err:
                print(f"::warning::{titre} : {err}")
                brut = None
            if brut is None:
                break
            texte = brut.decode("utf-8", "replace")
            m = re.match(r"\s*#(?:REDIRECT|REDIRECTION)\s*\[\[([^\]#|]+)", texte, re.I)
            if not m:
                break
            titre = m.group(1).strip()
            url = f"https://{langue}.wikipedia.org/wiki/" + urllib.parse.quote(titre.replace(" ", "_"))
            brut = None
        time.sleep(0.5)
        if brut is None or url in vues:
            continue
        if not re.search(r"chronolog|timeline", titre, re.I):
            continue                    # redirigée vers un article ordinaire
        vues.add(url)
        trouves = analyser_page(brut.decode("utf-8", "replace"), piste, url, langue)
        # Plafond par page, pour que le site reste léger : d'abord les lignes
        # qui nomment un événement ayant son article, puis les plus liées.
        if len(trouves) > PAR_PAGE:
            garder = set(map(id, sorted(trouves, key=lambda o: -o["_poids"])[:PAR_PAGE]))
            trouves = [o for o in trouves if id(o) in garder]
        for o in trouves:
            o.pop("_poids", None)
        if trouves:
            pages_lues += 1
            print(f"Wikipédia : {titre} → {len(trouves)} entrées")
        objets += trouves

    # Identifiant Wikidata des articles d'événements cités, pour reconnaître
    # le même événement dans les autres banques.
    articles = sorted({o["article"] for o in objets if o.get("article")} |
                      {u for o in objets for u in o.get("cites", [])})
    vers_qid = {}
    for paquet in par_paquets(articles, 150):
        valeurs = " ".join("<" + a + ">" for a in paquet)
        try:
            for r in sparql(f"SELECT ?a ?e WHERE {{ VALUES ?a {{ {valeurs} }} ?a schema:about ?e }}"):
                vers_qid[r["a"]] = qid(r["e"])
        except RuntimeError as err:
            print(f"::warning::Identifiants Wikidata : {err}")
    for o in objets:
        a = o.pop("article", None)
        cites = o.pop("cites", [])
        if a:
            o["liens"] = [a]
            if a in vers_qid:
                o["qid"] = vers_qid[a]
        mentions = [vers_qid[u] for u in cites if u in vers_qid and vers_qid[u] != o.get("qid")]
        if mentions:
            o["mentions"] = mentions
    # Une même ligne reprise d'une page à l'autre (France / Empire…) : une fois.
    uniques, deja = [], set()
    for o in objets:
        k = (o["piste"], o["debut"], cle_titre(o["nom"]))
        if k in deja:
            continue
        deja.add(k)
        uniques.append(o)
    print(f"Wikipédia : {pages_lues} pages lues, {len(uniques)} entrées, "
          f"{sum(1 for o in uniques if o.get('qid'))} reliées à Wikidata")
    return ecrire("wikipedia", "Wikipédia — chronologies",
                  "Wikipédia (CC BY-SA 4.0)", uniques, 1000)


# ==================================================================== PERIODO
def an_periodo(borne):
    """Borne PeriodO → année historique (les années ISO comptent un an zéro)."""
    if not borne:
        return None
    v = borne.get("in", {})
    an = v.get("year") or v.get("earliestYear") or v.get("latestYear")
    try:
        an = int(an)
    except (TypeError, ValueError):
        return None
    return an - 1 if an <= 0 else an


def recolter_periodo():
    print("PeriodO : téléchargement du jeu complet…")
    donnees = json.loads(telecharger("https://data.perio.do/d.json"))
    groupes = defaultdict(list)          # (piste, intitulé normalisé) → périodes
    for auteur in donnees["authorities"].values():
        src = auteur.get("source", {})
        titre_src = src.get("title") or src.get("partOf", {}).get("title") or ""
        annee_src = src.get("yearPublished") or src.get("partOf", {}).get("yearPublished") or ""
        for p in auteur.get("periods", {}).values():
            etiquettes = p.get("localizedLabels", {})
            en = (etiquettes.get("en") or [""])[0] or (p.get("label") if p.get("languageTag") == "en" else "")
            fr = (etiquettes.get("fr") or [""])[0] or (p.get("label") if p.get("languageTag") == "fr" else "")
            if not (en or fr):
                continue
            debut, fin = an_periodo(p.get("start")), an_periodo(p.get("stop"))
            if debut is None or fin is None or fin < debut or debut < -12000:
                continue
            couverture = [s.get("label", "") for s in p.get("spatialCoverage", [])]
            pistes = []
            for c in couverture:
                k = piste_pour(c, debut)
                if k and k not in pistes:
                    pistes.append(k)
            # Une période valable pour un continent entier n'apprend rien à
            # une piste nationale : on ne garde que les couvertures précises.
            if not pistes or len(pistes) > 4:
                continue
            piste = PISTE_PERIODE.get(pistes[0], pistes[0])
            groupes[(piste, cle_titre(en or fr))].append({
                "en": en, "fr": fr, "debut": debut, "fin": fin, "pistes": pistes,
                "source": (titre_src + (f" ({annee_src})" if annee_src else "")).strip(),
                "id": p.get("id"),
            })

    objets = []
    for (piste, _), versions in groupes.items():
        # Plusieurs autorités pour une même période : la datation médiane
        # sert de référence, les autres sont citées dans la notice.
        versions.sort(key=lambda v: (v["debut"], v["fin"]))
        ref = versions[len(versions) // 2]
        autres = [v for v in versions if v is not ref][:6]
        notes = "Selon " + (ref["source"] or "PeriodO")
        if autres:
            notes += ".\nAutres datations : " + " ; ".join(
                f"{v['debut']} → {v['fin']} ({v['source'] or 'PeriodO'})" for v in autres)
        en = ref["en"] or next((v["en"] for v in versions if v["en"]), "")
        fr = ref["fr"] or next((v["fr"] for v in versions if v["fr"]), "")
        objets.append({
            "nom": en or fr, "fr": fr if fr != en else "", "piste": piste,
            "ensembles": ref["pistes"] if len(ref["pistes"]) > 1 else [],
            "debut": ref["debut"], "fin": ref["fin"], "precision": "année",
            "qual": "circa" if ref["debut"] < 0 else "", "type": "Période",
            "notes": notes,
            "url": "http://n2t.net/ark:/99152/" + ref["id"] if ref["id"] else "https://perio.do/",
            "versions": len(versions),
        })
    print(f"PeriodO : {len(objets)} périodes après regroupement des autorités")
    return ecrire("periodo", "PeriodO", "PeriodO (CC0)", objets, 500)


if __name__ == "__main__":
    voulues = sys.argv[1:] or ["wikidata", "regnes", "wikipedia", "periodo"]
    echecs = []
    for nom in voulues:
        fonction = {"wikidata": recolter_wikidata, "regnes": recolter_regnes,
                    "wikipedia": recolter_wikipedia,
                    "periodo": recolter_periodo}[nom]
        try:
            fonction()
        except Exception as err:                      # une banque n'arrête pas les autres
            print(f"::warning::{nom} : récolte interrompue — {err}")
            echecs.append(nom)
    if len(echecs) == len(voulues):
        sys.exit(1)
