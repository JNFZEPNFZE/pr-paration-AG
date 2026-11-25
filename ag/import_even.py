"""Import des copropriétaires, lots et tantièmes depuis un export Even (CSV ou Excel).

Le format exact de l'export pouvant varier selon le paramétrage d'Even, les
colonnes sont détectées automatiquement à partir de leur intitulé puis peuvent
être corrigées par l'utilisateur. Le fichier attendu contient une ligne par lot.
"""

import csv
import io
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from .models import Coproprietaire, Lot

# Champ cible -> (libellé, obligatoire, intitulés reconnus)
CHAMPS = {
    "numero_lot": ("N° de lot", True, ["n lot", "no lot", "num lot", "numero lot", "lot", "numero de lot", "n de lot"]),
    "tantiemes": ("Tantièmes", True, ["tantiemes", "tantieme", "milliemes", "millieme", "quote part", "quote-part", "tantiemes generaux", "charges generales"]),
    "nom": ("Nom du copropriétaire", True, ["nom", "coproprietaire", "proprietaire", "nom coproprietaire", "nom du coproprietaire", "raison sociale", "titulaire"]),
    "code": ("Code copropriétaire", False, ["code", "code coproprietaire", "code copro", "compte", "n compte", "reference", "ref coproprietaire", "code proprietaire"]),
    "adresse": ("Adresse", False, ["adresse", "adresse postale", "adresse coproprietaire", "adresse 1"]),
    "email": ("E-mail", False, ["email", "e mail", "mail", "courriel", "adresse email"]),
    "telephone": ("Téléphone", False, ["telephone", "tel", "portable", "mobile"]),
    "nature": ("Nature du lot", False, ["nature", "type", "type de lot", "nature du lot", "designation"]),
    "batiment": ("Bâtiment", False, ["batiment", "bat", "escalier", "immeuble"]),
}


class ErreurImport(Exception):
    pass


def normaliser(texte):
    texte = unicodedata.normalize("NFKD", str(texte or "")).encode("ascii", "ignore").decode()
    texte = re.sub(r"[^a-z0-9]+", " ", texte.lower())
    return texte.strip()


def lire_fichier(nom, contenu: bytes):
    """Renvoie (entêtes, lignes) à partir d'un fichier CSV ou XLSX."""
    if nom.lower().endswith((".xlsx", ".xlsm")):
        return _lire_xlsx(contenu)
    return _lire_csv(contenu)


def _lire_xlsx(contenu):
    from openpyxl import load_workbook

    try:
        classeur = load_workbook(io.BytesIO(contenu), read_only=True, data_only=True)
    except Exception as exc:  # fichier corrompu ou non Excel
        raise ErreurImport(f"Fichier Excel illisible : {exc}") from exc
    feuille = classeur.worksheets[0]
    lignes = [
        ["" if v is None else str(v).strip() for v in ligne]
        for ligne in feuille.iter_rows(values_only=True)
    ]
    return _separer_entetes(lignes)


def _lire_csv(contenu):
    for encodage in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            texte = contenu.decode(encodage)
            break
        except UnicodeDecodeError:
            continue
    try:
        dialecte = csv.Sniffer().sniff(texte[:5000], delimiters=";,\t|")
        delimiteur = dialecte.delimiter
    except csv.Error:
        delimiteur = ";"
    lignes = [[c.strip() for c in ligne] for ligne in csv.reader(io.StringIO(texte), delimiter=delimiteur)]
    return _separer_entetes(lignes)


def _separer_entetes(lignes):
    lignes = [ligne for ligne in lignes if any(c for c in ligne)]
    if not lignes:
        raise ErreurImport("Le fichier est vide.")
    # La ligne d'entête est la première, parmi les 10 premières, qui reconnaît le plus de champs.
    meilleure, score_max = 0, -1
    for i, ligne in enumerate(lignes[:10]):
        score = sum(1 for v in detecter_colonnes(ligne).values() if v is not None)
        if score > score_max:
            meilleure, score_max = i, score
    entetes = lignes[meilleure]
    largeur = len(entetes)
    donnees = [(ligne + [""] * largeur)[:largeur] for ligne in lignes[meilleure + 1 :]]
    return entetes, donnees


def detecter_colonnes(entetes):
    """Associe chaque champ cible à l'index de colonne le plus probable."""
    normalises = [normaliser(e) for e in entetes]
    resultat, pris = {}, set()
    # Passe 1 : correspondance exacte ; passe 2 : l'intitulé contient l'alias.
    for exact in (True, False):
        for champ, (_, _, alias) in CHAMPS.items():
            if resultat.get(champ) is not None:
                continue
            resultat.setdefault(champ, None)
            for i, entete in enumerate(normalises):
                if i in pris or not entete or (not exact and "postal" in entete):
                    continue
                if any((entete == a) if exact else (a in entete.split() or entete.startswith(a)) for a in alias):
                    resultat[champ] = i
                    pris.add(i)
                    break
    return resultat


def convertir_tantiemes(valeur):
    texte = str(valeur).replace(" ", "").replace(" ", "").replace(",", ".")
    if not texte:
        raise ValueError("vide")
    try:
        nombre = Decimal(texte)
    except InvalidOperation as exc:
        raise ValueError(texte) from exc
    if nombre < 0 or nombre != nombre.to_integral_value():
        raise ValueError(texte)
    return int(nombre)


@dataclass
class Analyse:
    lots: list = field(default_factory=list)
    erreurs: list = field(default_factory=list)

    @property
    def nb_coproprietaires(self):
        return len({lot["cle"] for lot in self.lots})

    @property
    def total_tantiemes(self):
        return sum(lot["tantiemes"] for lot in self.lots)


def analyser(donnees, correspondance):
    """Valide les lignes selon la correspondance champ -> index de colonne."""
    for champ, (libelle, obligatoire, _) in CHAMPS.items():
        if obligatoire and correspondance.get(champ) is None:
            raise ErreurImport(f"La colonne « {libelle} » doit être indiquée.")

    def val(ligne, champ):
        idx = correspondance.get(champ)
        return ligne[idx].strip() if idx is not None and idx < len(ligne) else ""

    analyse, numeros = Analyse(), set()
    for n, ligne in enumerate(donnees, start=2):
        numero = val(ligne, "numero_lot")
        nom = val(ligne, "nom")
        brut = val(ligne, "tantiemes")
        if not numero and not nom and not brut:
            continue
        if not numero or not nom:
            analyse.erreurs.append(f"Ligne {n} : n° de lot ou nom manquant.")
            continue
        try:
            tantiemes = convertir_tantiemes(brut)
        except ValueError:
            analyse.erreurs.append(f"Ligne {n} : tantièmes invalides « {brut} ».")
            continue
        if numero in numeros:
            analyse.erreurs.append(f"Ligne {n} : le lot {numero} apparaît plusieurs fois.")
            continue
        numeros.add(numero)
        code = val(ligne, "code")
        analyse.lots.append(
            {
                "numero": numero,
                "tantiemes": tantiemes,
                "nature": val(ligne, "nature"),
                "batiment": val(ligne, "batiment"),
                "cle": code or normaliser(nom),
                "code": code,
                "nom": nom,
                "adresse": val(ligne, "adresse"),
                "email": val(ligne, "email"),
                "telephone": val(ligne, "telephone"),
            }
        )
    if not analyse.lots and not analyse.erreurs:
        analyse.erreurs.append("Aucun lot trouvé dans le fichier.")
    return analyse


@transaction.atomic
def importer(copropriete, analyse):
    """Synchronise la copropriété avec l'export : ajoute, met à jour et supprime.

    Les informations saisies uniquement dans ce logiciel (membre du conseil
    syndical) sont conservées pour les copropriétaires retrouvés.
    """
    if analyse.erreurs:
        raise ErreurImport("Le fichier contient des erreurs : import annulé.")

    existants = {}
    for c in copropriete.coproprietaires.all():
        existants[c.code_even or normaliser(c.nom)] = c

    stats = {"crees": 0, "maj": 0, "supprimes": 0, "lots": 0}
    retenus = {}
    for lot in analyse.lots:
        cle = lot["cle"]
        if cle in retenus:
            continue
        copro = existants.get(cle)
        valeurs = {
            "code_even": lot["code"],
            "nom": lot["nom"],
            "adresse": lot["adresse"],
            "email": lot["email"],
            "telephone": lot["telephone"],
        }
        if copro:
            for k, v in valeurs.items():
                setattr(copro, k, v)
            copro.save()
            stats["maj"] += 1
        else:
            copro = Coproprietaire.objects.create(copropriete=copropriete, **valeurs)
            stats["crees"] += 1
        retenus[cle] = copro

    copropriete.lots.all().delete()
    Lot.objects.bulk_create(
        Lot(
            copropriete=copropriete,
            proprietaire=retenus[lot["cle"]],
            numero=lot["numero"],
            nature=lot["nature"],
            batiment=lot["batiment"],
            tantiemes=lot["tantiemes"],
        )
        for lot in analyse.lots
    )
    stats["lots"] = len(analyse.lots)

    ids_retenus = {c.pk for c in retenus.values()}
    obsoletes = copropriete.coproprietaires.exclude(pk__in=ids_retenus)
    stats["supprimes"] = obsoletes.count()
    obsoletes.delete()

    copropriete.date_dernier_import = timezone.now()
    copropriete.save(update_fields=["date_dernier_import"])
    return stats
