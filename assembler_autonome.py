# -*- coding: utf-8 -*-
"""Assemble chronologies.html : la page, son script et ses données en un seul
fichier, qui s'ouvre d'un double-clic sans serveur ni connexion.

    python assembler_autonome.py [donnees.json] [--sortie chronologies.html]
"""
import argparse
import re

ap = argparse.ArgumentParser()
ap.add_argument("donnees", nargs="?", default="donnees.json")
ap.add_argument("--sortie", default="chronologies.html")
args = ap.parse_args()

page = open("index.html", encoding="utf-8").read()
script = open("app.js", encoding="utf-8").read()
donnees = open(args.donnees, encoding="utf-8").read().strip()

# Le chargeur de index.html (fetch de donnees.json puis app.js) est remplacé
# par les données et le script eux-mêmes.
debut = page.index("<script>\n/* Les données sont dans un fichier à part")
fin = page.index("</script>", debut) + len("</script>")
# « </script> » dans une notice fermerait la balise trop tôt.
donnees = donnees.replace("</", "<\\/")
script = script.replace("</script", "<\\/script")
bloc = ("<script>\nwindow.DONNEES = " + donnees + ";\n"
        'document.getElementById("chargement").remove();\n</script>\n'
        "<script>\n" + script + "\n</script>")
page = page[:debut] + bloc + page[fin:]
page = re.sub(r'<link[^>]+rel="?preload"?[^>]*donnees\.json[^>]*>\s*', "", page)
with open(args.sortie, "w", encoding="utf-8") as f:
    f.write(page)
print(f"{args.sortie} : {len(page) / 1e6:.1f} Mo")
