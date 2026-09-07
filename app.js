"use strict";

/* ------------------------------------------------------------------ données
   DONNEES.lignes : [id, nom, nomFr, section, sectionFr, couleur]
   DONNEES.objets : [nom, nomFr, iLigne, debut, fin, precision, qualD, margeD,
                     margeF, notes, url, fiable, sousPiste]                   */

const L_ID=0, L_NOM=1, L_FR=2, L_SEC=3, L_SECFR=4, L_COUL=5;
const O_NOM=0, O_FR=1, O_LIG=2, O_DEB=3, O_FIN=4, O_PREC=5, O_QUAL=6,
      O_MARGED=7, O_MARGEF=8, O_NOTES=9, O_URL=10, O_FIABLE=11, O_SOUS=12,
      O_ENS=13, O_TD=14, O_TF=15;

/* ------------------------------------------------- positions infra-annuelles
   O_TD / O_TF portent la position dans l'année, en minutes depuis le 1er
   janvier 00 h 00 (0 = inconnue, le 1er janvier vaut 1440). La position d'un
   objet sur l'axe est donc une année fractionnaire, ce qui permet de zoomer
   jusqu'à la minute sans changer de système de coordonnées.                 */
const MS_J = 86400000;
function joursAn(y){ return (y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0)) ? 366 : 365; }
function pos(y, t){ return t > 0 ? y + (t - 1440) / (joursAn(y) * 1440) : y; }
function msDe(y, t){
  const d = new Date(0);
  d.setUTCFullYear(y, 0, 1); d.setUTCHours(0, 0, 0, 0);
  return d.getTime() + (t > 0 ? (t - 1440) * 60000 : 0);
}
function msDePos(p){
  const y = Math.floor(p);
  return msDe(y, 0) + (p - y) * joursAn(y) * MS_J;
}
function posDeMs(ms){
  const y = new Date(ms).getUTCFullYear();
  return y + (ms - msDe(y, 0)) / (joursAn(y) * MS_J);
}
const posD = i => pos(objets[i][O_DEB], objets[i][O_TD]);
const posF = i => objets[i][O_FIN] === null ? null : pos(objets[i][O_FIN], objets[i][O_TF]);

/* ------------------------------------------------------------- bilingue */
const I18N = {
  fr: {
    titre:"Chronologies", objets:"objets", pistes:"pistes",
    allerA:"Aller à l'année", allerPh:"-586 ou 1789", tout:"Tout voir",
    moins:"Reculer (élargir la fenêtre)", plus:"Avancer (resserrer la fenêtre)",
    rech:"Rechercher", rechPh:"Nom d'un objet…", aucun:"Aucun objet ne porte ce nom.",
    aff:"Affichage", verif:"Afficher seulement les dates lues dans le texte source",
    vides:"Masquer les pistes vides à l'écran", sec:"Sections",
    cocher:"Tout cocher", decocher:"Tout décocher",
    aide:"Molette : zoom · Maj+molette ou ascenseur de droite : défilement vertical · Glisser : déplacer · Clic sur un objet : fiche détaillée",
    datation:"Datation", precision:"Précision", ligne:"Ligne du temps",
    sousPiste:"Sous-piste", source:"Source", ensembles:"Ensembles concernés",
    fiable:"date lue dans le texte source",
    pasFiable:"date déduite de la position, ± 2 ans",
    vers:"vers ", ans:"ans", a:" à ", regleAn:"année", reglePas:"par $ ans",
    prec:{ "jour":"jour","mois":"mois","année":"année","décennie":"décennie",
           "siècle":"siècle","millénaire":"millénaire","indéterminée":"indéterminée" },
    fermer:"Fermer",
  },
  en: {
    titre:"Timelines", objets:"objects", pistes:"tracks",
    allerA:"Go to year", allerPh:"-586 or 1789", tout:"Fit all",
    moins:"Zoom out", plus:"Zoom in",
    rech:"Search", rechPh:"Object name…", aucun:"No object by that name.",
    aff:"Display", verif:"Show only dates read from the source text",
    vides:"Hide tracks with nothing on screen", sec:"Sections",
    cocher:"Check all", decocher:"Uncheck all",
    aide:"Wheel: zoom · Shift+wheel or right-hand scrollbar: vertical scroll · Drag: pan · Click an object: details",
    datation:"Dating", precision:"Precision", ligne:"Timeline",
    sousPiste:"Sub-track", source:"Source", ensembles:"Groups involved",
    fiable:"date read from the source text",
    pasFiable:"date inferred from position, ± 2 years",
    vers:"c. ", ans:"years", a:" to ", regleAn:"year", reglePas:"every $ years",
    prec:{ "jour":"day","mois":"month","année":"year","décennie":"decade",
           "siècle":"century","millénaire":"millennium","indéterminée":"undetermined" },
    fermer:"Close",
  },
};
function T(k){ return I18N[vue.lang][k]; }

const lignes = DONNEES.lignes;
const objets = DONNEES.objets;

const sections = DONNEES.sections.map(d => ({
  nomFr: d[0], nomEn: d[1], couleur: d[2], lignes: [], nb: 0, visible: true }));
const parSection = new Map();          // clé de section → objet section
{
  let n = 0;
  for (const l of lignes) if (!parSection.has(l[L_SEC])) parSection.set(l[L_SEC], sections[n++]);
}
lignes.forEach((l, i) => parSection.get(l[L_SEC]).lignes.push(i));
function nomSection(s){ return vue.lang === "fr" ? s.nomFr : s.nomEn; }
// couleurs portées par un objet : les siennes et celles des ensembles liés
function couleursObjet(i, defaut){
  const e = objets[i][O_ENS];
  return e ? e.map(k => sections[k].couleur) : [defaut];
}

// objets groupés par ligne, triés par date de début
const parLigne = lignes.map(() => []);
objets.forEach((o, i) => parLigne[o[O_LIG]].push(i));
parLigne.forEach(a => a.sort((x, y) => posD(x) - posD(y)));
lignes.forEach((l, i) => parSection.get(l[L_SEC]).nb += parLigne[i].length);

const AN_MIN = Math.min(...objets.map(o => o[O_DEB])) - 40;
const AN_MAX = Math.max(...objets.map(o => o[O_FIN] || o[O_DEB])) + 40;

/* ------------------------------------------------------------------- état */
const vue = {
  debut: AN_MIN,
  ppa: 0.2,            // pixels par année
  defil: 0,            // défilement vertical, en pixels
  survol: null,
  choisi: null,
  lang: "fr",
  verifOnly: false,
  masquerVides: false,
  recherche: "",
};

const GOUT = 196;      // gouttière des intitulés de piste
const H_REGLE = 44;
const H_RANG = 21;     // hauteur d'un sous-rang dans une piste
const H_SECTION = 25;
const SEUIL_ETIQ = 0.55;   // px/an à partir duquel on écrit les intitulés

const toile = document.getElementById("toile");
const ctx = toile.getContext("2d");
const apercu = document.getElementById("apercu");
const ctxA = apercu.getContext("2d");
let W = 0, H = 0, dpr = 1;

/* --------------------------------------------------------------- utilitaires */
const ROMAINS = [[1000,"M"],[900,"CM"],[500,"D"],[400,"CD"],[100,"C"],[90,"XC"],
                 [50,"L"],[40,"XL"],[10,"X"],[9,"IX"],[5,"V"],[4,"IV"],[1,"I"]];
function romain(n){
  let s = "";
  for (const [v, l] of ROMAINS) while (n >= v) { s += l; n -= v; }
  return s;
}
function anLong(y){
  if (vue.lang === "fr") {
    if (y < 0) return (-y) + " av. J.-C.";
    return y < 1000 ? y + " apr. J.-C." : String(y);
  }
  if (y < 0) return (-y) + " BC";
  return y < 1000 ? "AD " + y : String(y);
}
function anCourt(y){
  if (y >= 0) return String(y);
  return (-y) + (vue.lang === "fr" ? " av." : " BC");
}

const SUFF_EN = { 1:"st", 2:"nd", 3:"rd" };
function siecleDe(y){
  const n = Math.floor((Math.abs(y) - 1) / 100) + 1;
  if (vue.lang === "fr")
    return romain(n) + (n === 1 ? "er" : "e") + " siècle " + (y < 0 ? "av. J.-C." : "apr. J.-C.");
  const d = n % 100 > 10 && n % 100 < 14 ? "th" : (SUFF_EN[n % 10] || "th");
  return n + d + " century " + (y < 0 ? "BC" : "AD");
}

function nomObjet(i){
  const o = objets[i];
  return (vue.lang === "fr" && o[O_FR]) ? o[O_FR] : o[O_NOM];
}
function nomLigne(i){
  const l = lignes[i];
  return (vue.lang === "fr" && l[L_FR]) ? l[L_FR] : l[L_NOM];
}

// Étendue floue : ce que l'incertitude ajoute de part et d'autre du noyau.
function flou(o){
  let g = 0;
  if (o[O_PREC] === "siècle") g = 50;
  else if (o[O_PREC] === "décennie") g = 5;
  else if (o[O_PREC] === "millénaire") g = 500;
  const d = o[O_MARGED] || (o[O_QUAL] === "circa" ? Math.max(g, 8) : g);
  const f = o[O_MARGEF] || (o[O_QUAL] === "circa" ? Math.max(g, 8) : g);
  return [d, f];
}

const cacheLargeur = new Map();
function largeurTexte(t){
  let w = cacheLargeur.get(t);
  if (w === undefined) { w = ctx.measureText(t).width; cacheLargeur.set(t, w); }
  return w;
}

/* ------------------------------------------------------- disposition des pistes */
let plan = [];        // [{genre, iSection|iLigne, y, h, rangs}]
let hauteurTotale = 0;

function correspond(i){
  const o = objets[i];
  if (vue.verifOnly && !o[O_FIABLE]) return false;
  if (vue.recherche) {
    const t = (o[O_NOM] + " " + (o[O_FR] || "")).toLowerCase();
    if (!t.includes(vue.recherche)) return false;
  }
  return true;
}

// Range les objets visibles d'une piste en sous-rangs sans chevauchement.
function ranger(iLigne, anD, anF, etiquettes){
  const liste = parLigne[iLigne];
  const coulLigne = lignes[iLigne][L_COUL];
  const rangs = [];      // dernier x occupé par sous-rang
  const places = [];
  const MAXR = 16;
  for (const i of liste) {
    const o = objets[i];
    const pd = posD(i);
    if (pd > anF) break;
    const pf = posF(i);
    const fin = pf === null ? pd : pf;
    if (fin < anD) continue;
    if (!correspond(i)) continue;

    const [fd, ff] = flou(o);
    const x0 = (pd - fd - vue.debut) * vue.ppa;
    const xc0 = (pd - vue.debut) * vue.ppa;
    const xc1 = (fin - vue.debut) * vue.ppa;
    const x1 = (fin + ff - vue.debut) * vue.ppa;
    // L'étiquette est toujours ancrée sur l'objet lui-même : à l'intérieur de
    // la barre quand celle-ci est assez large, sinon juste après sa fin. Aucun
    // recalage sur le bord de l'écran, sinon le texte glisse le long de la
    // barre pendant le déplacement.
    const barre = o[O_FIN] !== null && xc1 > xc0 + 2.5;
    let etiq = etiquettes ? nomObjet(i) : null;
    let lw = etiq ? largeurTexte(etiq) : 0;
    let dedans = false, xEtiq = 0;
    if (etiq) {
      dedans = barre && (xc1 - xc0) >= lw + 16;
      xEtiq = dedans ? xc0 + 8 : (barre ? xc1 : xc0 + 5) + 6;
    }
    let occ0 = Math.min(x0, etiq ? xEtiq : x0);
    let occ1 = Math.max(x1, etiq && !dedans ? xEtiq + lw : x1);
    if (occ1 - occ0 < 3) occ1 = occ0 + 3;
    let r = 0;
    while (r < MAXR && rangs[r] !== undefined && rangs[r] > occ0 - 4) r++;
    if (r >= MAXR) { r = MAXR - 1; etiq = null; }
    else rangs[r] = occ1;
    places.push({ i, r, x0, x1, xc0, xc1, etiq, xEtiq, dedans, lw,
                  couls: couleursObjet(i, coulLigne) });
  }
  return { places, nbRangs: Math.max(1, rangs.length) };
}

function construirePlan(){
  const anD = vue.debut - 400 / vue.ppa;
  const anF = vue.debut + (W - GOUT) / vue.ppa + 400 / vue.ppa;
  const etiquettes = vue.ppa >= SEUIL_ETIQ;
  plan = [];
  let y = 0;
  for (const s of sections) {
    if (!s.visible) continue;
    const bloc = [];
    for (const iL of s.lignes) {
      const r = ranger(iL, anD, anF, etiquettes);
      if (vue.masquerVides && r.places.length === 0) continue;
      bloc.push({ genre: "ligne", iLigne: iL, ...r });
    }
    if (!bloc.length) continue;
    plan.push({ genre: "section", section: s, y, h: H_SECTION });
    y += H_SECTION;
    for (const b of bloc) {
      b.y = y;
      b.h = b.nbRangs * H_RANG + 7;
      plan.push(b);
      y += b.h;
    }
    y += 6;
  }
  hauteurTotale = y;
  vue.defil = Math.max(0, Math.min(vue.defil, hauteurTotale - (H - H_REGLE) + 20));
}

/* --------------------------------------------------------------- graduation */
const PAS = [1,2,5,10,20,25,50,100,200,250,500,1000,2000,5000];
function pasGraduation(minPx){
  for (const p of PAS) if (p * vue.ppa >= minPx) return p;
  return PAS[PAS.length - 1];
}

const MOIS_FR = ["janv.","févr.","mars","avr.","mai","juin","juil.","août",
                 "sept.","oct.","nov.","déc."];
const MOIS_EN = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug",
                 "Sep","Oct","Nov","Dec"];
const mois = m => (vue.lang === "fr" ? MOIS_FR : MOIS_EN)[m];
const deuxCh = n => (n < 10 ? "0" : "") + n;

function jourMois(d){
  return vue.lang === "fr" ? d.getUTCDate() + " " + mois(d.getUTCMonth())
                           : mois(d.getUTCMonth()) + " " + d.getUTCDate();
}
function dateEntiere(d){
  return vue.lang === "fr"
    ? d.getUTCDate() + " " + mois(d.getUTCMonth()) + " " + d.getUTCFullYear()
    : mois(d.getUTCMonth()) + " " + d.getUTCDate() + ", " + d.getUTCFullYear();
}

// Paliers de graduation sous l'année, du plus fin au plus large.
const PALIERS = [
  ["min", 1, 60000], ["min", 5, 300000], ["min", 15, 900000], ["min", 30, 1800000],
  ["h", 1, 3600000], ["h", 3, 10800000], ["h", 6, 21600000], ["h", 12, 43200000],
  ["j", 1, MS_J], ["j", 2, 2 * MS_J], ["j", 7, 7 * MS_J],
  ["mois", 1, 30.4 * MS_J], ["mois", 3, 91 * MS_J], ["mois", 6, 182 * MS_J],
];

let GRAD = { grands: [], petits: [], legende: "" };

// Libellé d'une borne de la fenêtre, au niveau de détail du zoom courant.
function bornePhrase(p, span){
  if (span > 3 || p < 1) return anLong(Math.round(p));
  const d = new Date(msDePos(p));
  if (span * 365 > 3) return dateEntiere(d);
  return dateEntiere(d) + (vue.lang === "fr" ? ", " : " ") +
         d.getUTCHours() + ":" + deuxCh(d.getUTCMinutes());
}

function calculerGraduations(){
  const largeur = W - GOUT;
  const anD = vue.debut, anF = vue.debut + largeur / vue.ppa;
  const g = { grands: [], petits: [], legende: "" };

  // Au-delà de trois ans de fenêtre, ou avant l'an 1, on reste en années.
  if (anF - anD > 3 || anD < 1) {
    const grand = pasGraduation(64), petit = pasGraduation(9);
    for (let a = Math.ceil(anD / petit) * petit; a <= anF; a += petit)
      g.petits.push((a - anD) * vue.ppa);
    for (let a = Math.ceil(anD / grand) * grand; a <= anF; a += grand) {
      if (a === 0) continue;
      g.grands.push({ x: (a - anD) * vue.ppa, t: anCourt(a) });
    }
    g.legende = grand === 1 ? T("regleAn") : T("reglePas").replace("$", grand);
    return g;
  }

  const msD = msDePos(anD), msF = msDePos(anF);
  const pxParMs = largeur / (msF - msD);
  let p = PALIERS[PALIERS.length - 1];
  for (const c of PALIERS) if (c[2] * pxParMs >= 62) { p = c; break; }
  const [unite, n, approx] = p;
  const X = ms => (posDeMs(ms) - anD) * vue.ppa;

  if (unite === "mois") {
    const d = new Date(msD);
    const cur = new Date(0);
    cur.setUTCFullYear(d.getUTCFullYear(), Math.floor(d.getUTCMonth() / n) * n, 1);
    cur.setUTCHours(0, 0, 0, 0);
    while (cur.getTime() <= msF) {
      if (cur.getTime() >= msD) {
        const m = cur.getUTCMonth();
        g.grands.push({ x: X(cur.getTime()),
                        t: m === 0 ? mois(m) + " " + cur.getUTCFullYear() : mois(m) });
      }
      cur.setUTCMonth(cur.getUTCMonth() + n);
    }
    g.legende = String(new Date((msD + msF) / 2).getUTCFullYear());
  } else {
    const pas = n * (unite === "min" ? 60000 : unite === "h" ? 3600000 : MS_J);
    for (let m = Math.ceil(msD / pas) * pas; m <= msF; m += pas) {
      const d = new Date(m);
      let t;
      if (unite === "j") {
        t = d.getUTCDate() === 1 ? jourMois(d) : String(d.getUTCDate());
      } else {
        t = (d.getUTCHours() === 0 && d.getUTCMinutes() === 0)
          ? jourMois(d) : d.getUTCHours() + ":" + deuxCh(d.getUTCMinutes());
      }
      g.grands.push({ x: X(m), t });
    }
    const sous = pas / 4;
    for (let m = Math.ceil(msD / sous) * sous; m <= msF; m += sous) g.petits.push(X(m));
    const c = new Date((msD + msF) / 2);
    g.legende = unite === "j" ? mois(c.getUTCMonth()) + " " + c.getUTCFullYear()
                              : dateEntiere(c);
  }
  return g;
}

function dessinerRegle(){
  ctx.fillStyle = "#F7F8F5";
  ctx.fillRect(0, 0, W, H_REGLE);
  ctx.strokeStyle = "#9BA69E";
  ctx.beginPath(); ctx.moveTo(0, H_REGLE - .5); ctx.lineTo(W, H_REGLE - .5); ctx.stroke();

  const anD = vue.debut, anF = vue.debut + (W - GOUT) / vue.ppa;

  ctx.font = "11px " + getComputedStyle(document.body).getPropertyValue("--sans");
  ctx.textBaseline = "alphabetic";

  ctx.strokeStyle = "#C6CCC3";
  ctx.beginPath();
  for (const dx of GRAD.petits) {
    const x = GOUT + dx;
    if (x < GOUT || x > W) continue;
    ctx.moveTo(Math.round(x) + .5, H_REGLE - 7);
    ctx.lineTo(Math.round(x) + .5, H_REGLE - 1);
  }
  ctx.stroke();

  ctx.strokeStyle = "#9BA69E";
  ctx.fillStyle = "#1B2320";
  ctx.textAlign = "center";
  ctx.beginPath();
  for (const t of GRAD.grands) {
    const x = GOUT + t.x;
    if (x < GOUT + 2 || x > W) continue;
    ctx.moveTo(Math.round(x) + .5, H_REGLE - 15);
    ctx.lineTo(Math.round(x) + .5, H_REGLE - 1);
    ctx.fillText(t.t, x, H_REGLE - 20);
  }
  ctx.stroke();

  // repère de l'an 1
  if (anD < 1 && anF > 1) {
    const x = GOUT + (1 - vue.debut) * vue.ppa;
    ctx.strokeStyle = "#8E2317";
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H_REGLE); ctx.stroke();
  }
  ctx.fillStyle = "#F7F8F5";
  ctx.fillRect(0, 0, GOUT, H_REGLE);
  ctx.strokeStyle = "#9BA69E";
  ctx.beginPath();
  ctx.moveTo(GOUT - .5, 0); ctx.lineTo(GOUT - .5, H);
  ctx.moveTo(0, H_REGLE - .5); ctx.lineTo(GOUT, H_REGLE - .5);
  ctx.stroke();
  ctx.textAlign = "left";
  ctx.fillStyle = "#5C6862";
  ctx.fillText(GRAD.legende, 12, H_REGLE - 20);
}

function dessinerFond(){
  ctx.fillStyle = "#E7E9E4";
  ctx.fillRect(GOUT, H_REGLE, W - GOUT, H - H_REGLE);
  const anF = vue.debut + (W - GOUT) / vue.ppa;
  ctx.strokeStyle = "#D5DAD2";
  ctx.beginPath();
  for (const t of GRAD.grands) {
    const x = Math.round(GOUT + t.x) + .5;
    if (x < GOUT || x > W) continue;
    ctx.moveTo(x, H_REGLE); ctx.lineTo(x, H);
  }
  ctx.stroke();
  if (vue.debut < 1 && anF > 1) {
    const x = GOUT + (1 - vue.debut) * vue.ppa;
    ctx.strokeStyle = "rgba(142,35,23,.35)";
    ctx.beginPath(); ctx.moveTo(x, H_REGLE); ctx.lineTo(x, H); ctx.stroke();
  }
}

/* ---------------------------------------------------------------- objets */
function couleurLigne(iL){ return lignes[iL][L_COUL]; }

// Noir ou blanc selon la luminance de la barre, pour rester lisible dedans.
const cacheContraste = new Map();
function luminance(hex){
  const n = parseInt(hex.slice(1), 16);
  return .2126 * ((n >> 16) & 255) + .7152 * ((n >> 8) & 255) + .0722 * (n & 255);
}
function contraste(couls){
  const cle = couls.join("");
  let c = cacheContraste.get(cle);
  if (c === undefined) {
    const L = couls.reduce((a, h) => a + luminance(h), 0) / couls.length;
    c = L > 150 ? "#1B2320" : "#FBFCFA";
    cacheContraste.set(cle, c);
  }
  return c;
}

function dessinerPistes(){
  const sans = getComputedStyle(document.body).getPropertyValue("--sans");
  const serif = getComputedStyle(document.body).getPropertyValue("--serif");
  ctx.textBaseline = "middle";

  for (const b of plan) {
    const yTop = H_REGLE + b.y - vue.defil;
    if (yTop > H || yTop + b.h < H_REGLE) continue;

    if (b.genre === "section") {
      ctx.fillStyle = "#DDE0DA";
      ctx.fillRect(0, yTop, W, b.h);
      ctx.fillStyle = b.section.couleur;
      ctx.fillRect(0, yTop, 4, b.h);
      ctx.font = "600 13px " + serif;
      ctx.fillStyle = "#1B2320";
      ctx.textAlign = "left";
      ctx.fillText(nomSection(b.section), 14, yTop + b.h / 2);
      continue;
    }

    const coul = couleurLigne(b.iLigne);
    // alternance discrète
    ctx.fillStyle = "rgba(255,255,255,.35)";
    ctx.fillRect(GOUT, yTop, W - GOUT, b.h);

    for (const p of b.places) {
      const o = objets[p.i];
      const yc = yTop + 6 + p.r * H_RANG + H_RANG / 2 - 3;
      const sel = vue.choisi === p.i, surv = vue.survol === p.i;

      // halo d'incertitude
      if (p.x1 - p.x0 > (p.xc1 - p.xc0) + 1.5) {
        const g = ctx.createLinearGradient(GOUT + p.x0, 0, GOUT + p.x1, 0);
        g.addColorStop(0, "rgba(0,0,0,0)");
        g.addColorStop(.42, p.couls[0] + "44");
        g.addColorStop(.58, p.couls[0] + "44");
        g.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = g;
        ctx.fillRect(GOUT + p.x0, yc - 6, p.x1 - p.x0, 13);
      }

      const largeur = p.xc1 - p.xc0;
      const couls = p.couls;
      // Un objet partagé entre plusieurs ensembles est rayé de leurs couleurs.
      const bandes = (x, y, w, h) => {
        if (x < -400) { w += x + 400; x = -400; }
        if (w > W + 800) w = W + 800;
        if (w <= 0) return;
        if (sel) { ctx.fillStyle = "#2C4C6B"; ctx.fillRect(x, y, w, h); return; }
        const hb = h / couls.length;
        for (let k = 0; k < couls.length; k++) {
          ctx.fillStyle = couls[k] + "D9";
          ctx.fillRect(x, y + k * hb, w, hb + (k < couls.length - 1 ? .5 : 0));
        }
      };
      if (o[O_FIN] !== null && largeur > 2.5) {
        bandes(GOUT + p.xc0, yc - 7, largeur, 15);
        if (sel || surv) {
          ctx.strokeStyle = "#1B2320";
          ctx.lineWidth = 1;
          ctx.strokeRect(GOUT + p.xc0 - .5, yc - 7.5, largeur + 1, 16);
        }
      } else {
        const x = GOUT + p.xc0;
        const rx = couls.length > 1 ? 6.5 : 4.5, ry = couls.length > 1 ? 7.5 : 5;
        ctx.beginPath();
        ctx.moveTo(x, yc - ry); ctx.lineTo(x + rx, yc);
        ctx.lineTo(x, yc + ry); ctx.lineTo(x - rx, yc);
        ctx.closePath();
        if (couls.length > 1) {
          ctx.save(); ctx.clip(); bandes(x - rx, yc - ry, rx * 2, ry * 2); ctx.restore();
          ctx.strokeStyle = "#1B2320"; ctx.lineWidth = .7; ctx.stroke();
        } else {
          ctx.fillStyle = sel ? "#2C4C6B" : couls[0] + "D9";
          ctx.fill();
        }
        if (sel || surv) { ctx.strokeStyle = "#1B2320"; ctx.lineWidth = 1; ctx.stroke(); }
      }

      if (p.etiq) {
        const xe = GOUT + p.xEtiq;
        if (p.dedans || (xe < W && xe > GOUT - 4)) {
          ctx.font = (sel ? "600 " : "") + "11px " + sans;
          ctx.fillStyle = p.dedans ? (sel ? "#FBFCFA" : contraste(couls))
                                   : (sel ? "#2C4C6B" : "#1B2320");
          ctx.textAlign = "left";
          if (p.dedans) {
            // Centré dans la barre tant qu'elle tient à l'écran ; sinon centré
            // dans la portion visible, sans jamais sortir de la barre. Le texte
            // reste donc toujours lisible, même au milieu d'une longue période.
            const g0 = GOUT + 6, g1 = (vue.choisi !== null ? W - 400 : W - 6);
            const b0 = GOUT + p.xc0, b1 = GOUT + p.xc1;
            const v0 = Math.max(b0, g0), v1 = Math.min(b1, g1);
            let x = (v0 + v1) / 2 - p.lw / 2;
            x = Math.max(b0 + 8, Math.min(x, b1 - 8 - p.lw));
            ctx.fillText(p.etiq, x, yc);
          } else {
            ctx.fillText(p.etiq, xe, yc);
          }
        }
      }
    }

    // gouttière : intitulé de la piste
    ctx.fillStyle = "#F7F8F5";
    ctx.fillRect(0, yTop, GOUT, b.h);
    ctx.fillStyle = coul;
    ctx.fillRect(8, yTop + 5, 3, b.h - 10);
    ctx.font = "11px " + sans;
    ctx.fillStyle = "#1B2320";
    ctx.textAlign = "left";
    let t = nomLigne(b.iLigne).replace(/^[^–]*– /, "");
    while (largeurTexte(t) > GOUT - 26 && t.length > 4) t = t.slice(0, -2) + "…";
    ctx.fillText(t, 17, yTop + b.h / 2);
    ctx.strokeStyle = "#E0E4DD";
    ctx.beginPath();
    ctx.moveTo(0, yTop + b.h - .5); ctx.lineTo(W, yTop + b.h - .5);
    ctx.stroke();
  }
  ctx.strokeStyle = "#9BA69E";
  ctx.beginPath(); ctx.moveTo(GOUT - .5, H_REGLE); ctx.lineTo(GOUT - .5, H); ctx.stroke();
  dessinerAscenseur();
}

const ASC_L = 9;
function metriquesAscenseur(){
  const piste = H - H_REGLE;
  const frac = Math.min(1, piste / hauteurTotale);
  const h = Math.max(34, piste * frac);
  const max = Math.max(1, hauteurTotale - piste);
  const y = H_REGLE + (piste - h) * Math.min(1, vue.defil / max);
  return { piste, h, y, max, visible: frac < 1 };
}
function dessinerAscenseur(){
  const m = metriquesAscenseur();
  if (!m.visible) return;
  ctx.fillStyle = "rgba(155,166,158,.22)";
  ctx.fillRect(W - ASC_L, H_REGLE, ASC_L, m.piste);
  ctx.fillStyle = "#8B968E";
  ctx.fillRect(W - ASC_L + 2, m.y, ASC_L - 4, m.h);
}

/* ------------------------------------------------------------- vue d'ensemble */
let histo = null;
function calculerHisto(n){
  histo = new Array(n).fill(0);
  const pas = (AN_MAX - AN_MIN) / n;
  for (const o of objets) {
    const k = Math.min(n - 1, Math.max(0, Math.floor((o[O_DEB] - AN_MIN) / pas)));
    histo[k]++;
  }
}
function dessinerApercu(){
  const w = apercu.clientWidth, h = apercu.clientHeight;
  apercu.width = w * dpr; apercu.height = h * dpr;
  ctxA.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctxA.clearRect(0, 0, w, h);
  const n = Math.max(60, Math.floor(w / 3));
  if (!histo || histo.length !== n) calculerHisto(n);
  const max = Math.max(...histo);
  ctxA.fillStyle = "#B9C1B7";
  for (let i = 0; i < n; i++) {
    const hh = Math.pow(histo[i] / max, .45) * (h - 15);
    ctxA.fillRect(i * (w / n), h - 11 - hh, w / n - .5, hh);
  }
  // fenêtre courante
  const x0 = (vue.debut - AN_MIN) / (AN_MAX - AN_MIN) * w;
  const x1 = (vue.debut + (W - GOUT) / vue.ppa - AN_MIN) / (AN_MAX - AN_MIN) * w;
  ctxA.fillStyle = "rgba(44,76,107,.16)";
  ctxA.fillRect(x0, 0, Math.max(2, x1 - x0), h - 11);
  ctxA.strokeStyle = "#2C4C6B";
  ctxA.strokeRect(x0 + .5, .5, Math.max(2, x1 - x0), h - 12);
  // échelle
  ctxA.font = "10px " + getComputedStyle(document.body).getPropertyValue("--sans");
  ctxA.fillStyle = "#5C6862";
  ctxA.textBaseline = "bottom";
  for (const a of [-3000, -2000, -1000, 1, 1000, 1500, 2000]) {
    if (a < AN_MIN || a > AN_MAX) continue;
    const x = (a - AN_MIN) / (AN_MAX - AN_MIN) * w;
    ctxA.textAlign = "center";
    ctxA.fillText(anCourt(a), x, h);
    ctxA.fillRect(x, h - 10, .7, 4);
  }
}

/* ------------------------------------------------------------------ rendu */
let enAttente = false;
function rendre(){
  if (enAttente) return;
  enAttente = true;
  requestAnimationFrame(() => {
    enAttente = false;
    ctx.font = "11px " + getComputedStyle(document.body).getPropertyValue("--sans");
    GRAD = calculerGraduations();
    construirePlan();
    ctx.clearRect(0, 0, W, H);
    dessinerFond();
    dessinerPistes();
    dessinerRegle();
    dessinerApercu();
    const anF = vue.debut + (W - GOUT) / vue.ppa;
    document.getElementById("etendue").textContent =
      bornePhrase(vue.debut, anF - vue.debut) + "  →  " + bornePhrase(anF, anF - vue.debut);
  });
}

function redimensionner(){
  const r = document.getElementById("scene").getBoundingClientRect();
  dpr = window.devicePixelRatio || 1;
  W = r.width; H = r.height;
  toile.width = W * dpr; toile.height = H * dpr;
  toile.style.width = W + "px"; toile.style.height = H + "px";
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  rendre();
}

/* ------------------------------------------------------------ interactions */
function zoomer(facteur, ancreX){
  let ax;
  if (ancreX !== undefined) {
    ax = Math.max(ancreX, GOUT + 1);
  } else if (vue.choisi !== null) {
    // Un objet est ouvert : c'est lui qu'on veut garder sous les yeux.
    const px = GOUT + (posD(vue.choisi) - vue.debut) * vue.ppa;
    ax = (px > GOUT && px < W) ? px : (W + GOUT) / 2;
  } else {
    ax = (W + GOUT) / 2;
  }
  const anAncre = vue.debut + (ax - GOUT) / vue.ppa;
  const maxPpa = 6e7, minPpa = (W - GOUT) / (AN_MAX - AN_MIN);
  vue.ppa = Math.max(minPpa, Math.min(maxPpa, vue.ppa * facteur));
  vue.debut = anAncre - (ax - GOUT) / vue.ppa;
  borner();
  rendre();
}
function borner(){
  const span = (W - GOUT) / vue.ppa;
  vue.debut = Math.max(AN_MIN, Math.min(AN_MAX - span, vue.debut));
}

toile.addEventListener("wheel", e => {
  e.preventDefault();
  if (e.shiftKey) {
    vue.defil = Math.max(0, vue.defil + e.deltaY);
    rendre();
  } else {
    zoomer(Math.pow(0.9985, e.deltaY), e.offsetX);
  }
}, { passive: false });

let glisse = null;
let ascenseur = null;
toile.addEventListener("pointerdown", e => {
  if (e.offsetX > W - ASC_L - 4 && e.offsetY > H_REGLE) {
    const m = metriquesAscenseur();
    if (m.visible) {
      ascenseur = { y: e.offsetY, defil: vue.defil, m };
      toile.setPointerCapture(e.pointerId);
      return;
    }
  }
  glisse = { x: e.offsetX, y: e.offsetY, debut: vue.debut, defil: vue.defil, bouge: false };
  toile.setPointerCapture(e.pointerId);
  toile.classList.add("glisse");
});
toile.addEventListener("pointermove", e => {
  if (ascenseur) {
    const m = ascenseur.m;
    const dy = (e.offsetY - ascenseur.y) * (m.max / Math.max(1, m.piste - m.h));
    vue.defil = Math.max(0, Math.min(m.max, ascenseur.defil + dy));
    rendre();
    return;
  }
  if (glisse) {
    const dx = e.offsetX - glisse.x, dy = e.offsetY - glisse.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) glisse.bouge = true;
    vue.debut = glisse.debut - dx / vue.ppa;
    vue.defil = Math.max(0, glisse.defil - dy);
    borner();
    rendre();
  } else {
    const t = objetSous(e.offsetX, e.offsetY);
    if (t !== vue.survol) { vue.survol = t; majBulle(e); rendre(); }
    else if (t !== null) majBulle(e);
  }
});
toile.addEventListener("pointerup", e => {
  if (ascenseur) { ascenseur = null; return; }
  const bouge = glisse && glisse.bouge;
  glisse = null;
  toile.classList.remove("glisse");
  if (!bouge) {
    const t = objetSous(e.offsetX, e.offsetY);
    if (t !== null) ouvrirFiche(t); else fermerFiche();
  }
});
toile.addEventListener("pointerleave", () => {
  vue.survol = null;
  document.getElementById("bulle").style.opacity = 0;
  rendre();
});

function objetSous(px, py){
  if (px < GOUT || py < H_REGLE) return null;
  for (const b of plan) {
    if (b.genre !== "ligne") continue;
    const yTop = H_REGLE + b.y - vue.defil;
    if (py < yTop || py > yTop + b.h) continue;
    const rang = Math.floor((py - yTop - 6) / H_RANG);
    let meilleur = null, dist = 1e9;
    for (const p of b.places) {
      if (p.r !== rang) continue;
      const x0 = GOUT + p.xc0 - 6, x1 = GOUT + Math.max(p.xc1, p.xc0 + 4) + 6;
      if (px >= x0 && px <= x1) return p.i;
      const d = Math.min(Math.abs(px - x0), Math.abs(px - x1));
      if (d < dist) { dist = d; meilleur = p.i; }
    }
    if (dist < 4) return meilleur;
  }
  return null;
}

const bulle = document.getElementById("bulle");
function majBulle(e){
  if (vue.survol === null) { bulle.style.opacity = 0; return; }
  const o = objets[vue.survol];
  bulle.innerHTML = "<b>" + echapper(nomObjet(vue.survol)) + "</b><i>" +
    echapper(datePhrase(o)) + " · " + echapper(nomLigne(o[O_LIG])) + "</i>";
  const r = document.getElementById("scene").getBoundingClientRect();
  let x = e.offsetX + 14, y = e.offsetY + 16;
  if (x + 340 > r.width) x = e.offsetX - 340;
  bulle.style.left = x + "px"; bulle.style.top = y + "px";
  bulle.style.opacity = 1;
}
function echapper(s){
  return String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

/* --------------------------------------------------------------- fiche */
function millenaireDe(y){
  const n = Math.floor((Math.abs(y) - 1) / 1000) + 1;
  if (vue.lang === "fr")
    return romain(n) + (n === 1 ? "er" : "e") + " millénaire " + (y < 0 ? "av. J.-C." : "apr. J.-C.");
  const d = SUFF_EN[n] || "th";
  return n + d + " millennium " + (y < 0 ? "BC" : "AD");
}
// « 14 mai 1948 », « mai 1948 », « 1948 », avec l'heure si elle est connue.
function dateFine(y, t, prec){
  if (!t || y < 1) return anLong(y);
  const d = new Date(msDe(y, t));
  let s = prec === "mois" ? mois(d.getUTCMonth()) + " " + y : dateEntiere(d);
  const h = d.getUTCHours(), mn = d.getUTCMinutes();
  if (h || mn) s += (vue.lang === "fr" ? ", " : " at ") + h + ":" + deuxCh(mn);
  return s;
}
function datePhrase(o){
  let d;
  if (o[O_PREC] === "jour" || o[O_PREC] === "mois") {
    d = (o[O_QUAL] === "circa" ? T("vers") : "") + dateFine(o[O_DEB], o[O_TD], o[O_PREC]);
    if (o[O_FIN] !== null) d += " → " + dateFine(o[O_FIN], o[O_TF], o[O_PREC]);
    return d;
  }
  if (o[O_PREC] === "siècle") d = siecleDe(o[O_DEB]);
  else if (o[O_PREC] === "millénaire") d = millenaireDe(o[O_DEB]);
  else d = (o[O_QUAL] === "circa" ? T("vers") : "") + anLong(o[O_DEB]);
  if (o[O_MARGED]) d += " ± " + o[O_MARGED] + " " + T("ans");
  if (o[O_FIN] !== null && o[O_FIN] !== o[O_DEB]) {
    d += " → " + anLong(o[O_FIN]);
    if (o[O_MARGEF]) d += " ± " + o[O_MARGEF] + " " + T("ans");
  }
  return d;
}

const tiroir = document.getElementById("tiroir");
function ouvrirFiche(i){
  vue.choisi = i;
  const o = objets[i];
  const principal = nomObjet(i), second = (vue.lang === "fr" ? o[O_NOM] : o[O_FR]);
  document.getElementById("tTitre").textContent = principal;
  const fr = document.getElementById("tFr");
  const montrer = second && second !== principal;
  fr.textContent = montrer ? second : "";
  fr.style.display = montrer ? "block" : "none";

  const c = [];
  c.push(champ(T("datation"), echapper(datePhrase(o))));
  c.push(champ(T("precision"), echapper(T("prec")[o[O_PREC]] || o[O_PREC] || "") +
    (o[O_FIABLE]
      ? ' <span class="jeton">' + T("fiable") + "</span>"
      : ' <span class="jeton avert">' + T("pasFiable") + "</span>")));
  c.push(champ(T("ligne"), echapper(nomLigne(o[O_LIG]))));
  if (o[O_SOUS]) c.push(champ(T("sousPiste"), echapper(o[O_SOUS])));
  if (o[O_ENS]) c.push(champ(T("ensembles"), '<span class="rubans">' +
    o[O_ENS].map(k => '<span class="ruban"><i style="background:' + sections[k].couleur +
      '"></i>' + echapper(nomSection(sections[k])) + "</span>").join("") + "</span>"));
  if (o[O_URL]) c.push(champ(T("source"), '<a href="' + echapper(o[O_URL]) +
    '" target="_blank" rel="noopener">' + echapper(o[O_URL].replace(/^https?:\/\//, "")) + "</a>"));
  let html = "<dl>" + c.join("") + "</dl>";
  if (o[O_NOTES]) html += '<div class="notice">' + echapper(o[O_NOTES]) + "</div>";
  document.getElementById("tCorps").innerHTML = html;
  tiroir.classList.add("ouvert");
  tiroir.setAttribute("aria-hidden", "false");
  rendre();
}
function champ(t, v){ return '<div class="champ"><dt>' + t + "</dt><dd>" + v + "</dd></div>"; }
function fermerFiche(){
  vue.choisi = null;
  tiroir.classList.remove("ouvert");
  tiroir.setAttribute("aria-hidden", "true");
  rendre();
}
document.getElementById("tFermer").onclick = fermerFiche;

/* ------------------------------------------------------- aller à / recherche */
document.getElementById("allerA").addEventListener("change", e => {
  const m = e.target.value.trim().match(/^(-?\d+)/);
  if (!m) return;
  let a = parseInt(m[1], 10);
  if (/av/i.test(e.target.value) && a > 0) a = -a;
  if ((W - GOUT) / vue.ppa > 400) vue.ppa = (W - GOUT) / 300;
  const span = (W - GOUT) / vue.ppa;
  vue.debut = a - span / 2;
  borner();
  rendre();
});

function viser(i, zoom){
  if (zoom) vue.ppa = Math.max(vue.ppa, 3);
  const span = (W - GOUT) / vue.ppa;
  vue.debut = posD(i) - span / 3;
  borner();
  // amener la piste à l'écran
  construirePlan();
  const b = plan.find(p => p.genre === "ligne" && p.iLigne === objets[i][O_LIG]);
  if (b) vue.defil = Math.max(0, b.y - (H - H_REGLE) / 3);
  ouvrirFiche(i);
}

const champRecherche = document.getElementById("recherche");
const boiteResultats = document.getElementById("resultats");
let minuteur = null;
champRecherche.addEventListener("input", () => {
  clearTimeout(minuteur);
  minuteur = setTimeout(() => {
    const q = champRecherche.value.trim().toLowerCase();
    vue.recherche = "";
    if (q.length < 2) { boiteResultats.innerHTML = ""; rendre(); return; }
    const trouves = [];
    for (let i = 0; i < objets.length && trouves.length < 60; i++) {
      const o = objets[i];
      if ((o[O_NOM] + " " + (o[O_FR] || "")).toLowerCase().includes(q)) trouves.push(i);
    }
    if (!trouves.length) {
      boiteResultats.innerHTML = '<p class="vide">' + T("aucun") + "</p>";
      return;
    }
    boiteResultats.innerHTML = trouves.map(i =>
      '<div data-i="' + i + '">' + echapper(nomObjet(i)) +
      "<em>" + echapper(anCourt(objets[i][O_DEB])) + " · " +
      echapper(nomLigne(objets[i][O_LIG])) + "</em></div>").join("");
    rendre();
  }, 160);
});
boiteResultats.addEventListener("click", e => {
  const d = e.target.closest("div[data-i]");
  if (d) viser(+d.dataset.i, true);
});

/* ------------------------------------------------------------- commandes */
document.getElementById("plus").onclick = () => zoomer(1.6);
document.getElementById("moins").onclick = () => zoomer(1 / 1.6);
document.getElementById("tout").onclick = () => {
  vue.ppa = (W - GOUT) / (AN_MAX - AN_MIN);
  vue.debut = AN_MIN;
  vue.defil = 0;
  rendre();
};
function appliquerLangue(){
  const d = document.getElementById.bind(document);
  document.documentElement.lang = vue.lang;
  d("langFr").classList.toggle("actif", vue.lang === "fr");
  d("langEn").classList.toggle("actif", vue.lang === "en");
  d("titrePage").textContent = T("titre");
  d("soustitre").textContent = objets.length.toLocaleString(vue.lang === "fr" ? "fr-CA" : "en-CA") +
    " " + T("objets") + " · " + lignes.length + " " + T("pistes");
  d("tAllerA").textContent = T("allerA");
  d("allerA").placeholder = T("allerPh");
  d("moins").title = T("moins"); d("plus").title = T("plus");
  d("tout").textContent = T("tout");
  d("tRech").textContent = T("rech");
  d("recherche").placeholder = T("rechPh");
  d("tAff").textContent = T("aff");
  d("tVerif").textContent = T("verif");
  d("tVides").textContent = T("vides");
  d("tSec").textContent = T("sec");
  d("toutCocher").textContent = T("cocher");
  d("toutDecocher").textContent = T("decocher");
  d("tAide").textContent = T("aide");
  d("tFermer").title = T("fermer");
  liste.querySelectorAll("label").forEach((l, i) => {
    l.innerHTML = echapper(nomSection(sections[i])) +
      ' <span class="compte">' + sections[i].nb + "</span>";
  });
  cacheLargeur.clear();
  if (vue.choisi !== null) ouvrirFiche(vue.choisi);
  champRecherche.dispatchEvent(new Event("input"));
  rendre();
}
document.getElementById("langFr").onclick = () => { vue.lang = "fr"; appliquerLangue(); };
document.getElementById("langEn").onclick = () => { vue.lang = "en"; appliquerLangue(); };
document.getElementById("optVerif").onchange = e => { vue.verifOnly = e.target.checked; rendre(); };
document.getElementById("optVides").onchange = e => { vue.masquerVides = e.target.checked; rendre(); };

apercu.addEventListener("pointerdown", e => {
  const w = apercu.clientWidth;
  const a = AN_MIN + (e.offsetX / w) * (AN_MAX - AN_MIN);
  vue.debut = a - (W - GOUT) / vue.ppa / 2;
  borner(); rendre();
});

window.addEventListener("keydown", e => {
  if (e.target.tagName === "INPUT") return;
  const span = (W - GOUT) / vue.ppa;
  if (e.key === "ArrowRight") { vue.debut += span * .2; borner(); rendre(); }
  else if (e.key === "ArrowLeft") { vue.debut -= span * .2; borner(); rendre(); }
  else if (e.key === "ArrowDown") { vue.defil += 60; rendre(); }
  else if (e.key === "ArrowUp") { vue.defil = Math.max(0, vue.defil - 60); rendre(); }
  else if (e.key === "+" || e.key === "=") zoomer(1.5);
  else if (e.key === "-") zoomer(1 / 1.5);
  else if (e.key === "Escape") fermerFiche();
});

/* -------------------------------------------------------------- sections */
const liste = document.getElementById("listeSections");
liste.innerHTML = sections.map((s, i) =>
  '<li><input type="checkbox" id="s' + i + '" checked data-i="' + i + '">' +
  '<span class="pastille" style="background:' + s.couleur + '"></span>' +
  '<label for="s' + i + '">' + echapper(nomSection(s)) +
  ' <span class="compte">' + s.nb + "</span></label></li>").join("");
liste.addEventListener("change", e => {
  const i = e.target.dataset.i;
  if (i === undefined) return;
  sections[+i].visible = e.target.checked;
  rendre();
});
document.getElementById("toutCocher").onclick = () => basculer(true);
document.getElementById("toutDecocher").onclick = () => basculer(false);
function basculer(v){
  sections.forEach(s => s.visible = v);
  liste.querySelectorAll("input").forEach(c => c.checked = v);
  rendre();
}

/* ------------------------------------------------------------- démarrage */
appliquerLangue();
window.addEventListener("resize", redimensionner);
redimensionner();
vue.ppa = (W - GOUT) / 1000;
vue.debut = -600;
rendre();
