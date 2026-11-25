"""Référentiel métier : résolutions types et rétroplanning.

Les textes sont des modèles à adapter. Les majorités indiquées correspondent à la
loi n° 65-557 du 10 juillet 1965 dans sa rédaction issue de l'ordonnance du
30 octobre 2019 ; elles doivent être vérifiées par le gestionnaire au regard du
règlement de copropriété et des évolutions législatives.
"""

from dataclasses import dataclass, field
from datetime import timedelta

from .models import Majorite


@dataclass(frozen=True)
class ModeleResolution:
    code: str
    titre: str
    majorite: str
    texte: str
    pieces: tuple = field(default_factory=tuple)
    ago_standard: bool = False
    note: str = ""


EXERCICE = "{exercice}"

MODELES = [
    ModeleResolution(
        code="president",
        titre="Élection du président de séance",
        majorite=Majorite.ART_24,
        texte="L'assemblée générale élit en qualité de président de séance : …",
        ago_standard=True,
        note="Art. 15 du décret du 17 mars 1967 : première question soumise à l'assemblée.",
    ),
    ModeleResolution(
        code="scrutateurs",
        titre="Élection du ou des scrutateurs",
        majorite=Majorite.ART_24,
        texte="L'assemblée générale élit en qualité de scrutateur(s) : …",
        ago_standard=True,
    ),
    ModeleResolution(
        code="secretaire",
        titre="Élection du secrétaire de séance",
        majorite=Majorite.ART_24,
        texte="L'assemblée générale élit en qualité de secrétaire de séance : …",
        ago_standard=True,
        note="Le syndic assure le secrétariat de séance sauf décision contraire (art. 15 du décret).",
    ),
    ModeleResolution(
        code="comptes",
        titre="Approbation des comptes de l'exercice " + EXERCICE,
        majorite=Majorite.ART_24,
        texte=(
            "L'assemblée générale, après avoir pris connaissance des documents comptables "
            "joints à la convocation et de l'avis du conseil syndical, approuve en leur forme, "
            "teneur, imputation et répartition les comptes de l'exercice " + EXERCICE + "."
        ),
        pieces=(
            "État financier du syndicat après répartition",
            "Compte de gestion générale de l'exercice",
            "Annexes comptables (comparatif budget / réalisé)",
        ),
        ago_standard=True,
    ),
    ModeleResolution(
        code="budget_ajustement",
        titre="Ajustement du budget prévisionnel de l'exercice en cours",
        majorite=Majorite.ART_24,
        texte=(
            "L'assemblée générale fixe le budget prévisionnel de l'exercice en cours à la somme "
            "de … €, appelée par quarts aux dates habituelles."
        ),
        pieces=("Projet de budget prévisionnel avec comparatif du dernier budget voté",),
        ago_standard=True,
    ),
    ModeleResolution(
        code="budget",
        titre="Vote du budget prévisionnel de l'exercice suivant",
        majorite=Majorite.ART_24,
        texte=(
            "L'assemblée générale approuve le budget prévisionnel détaillé de l'exercice "
            "suivant pour un montant de … €. Les provisions seront exigibles le premier jour "
            "de chaque trimestre."
        ),
        pieces=("Projet de budget prévisionnel avec comparatif du dernier budget voté",),
        ago_standard=True,
    ),
    ModeleResolution(
        code="fonds_travaux",
        titre="Fixation de la cotisation annuelle au fonds de travaux",
        majorite=Majorite.ART_25,
        texte=(
            "L'assemblée générale fixe le montant de la cotisation annuelle au fonds de travaux "
            "à … % du budget prévisionnel (minimum légal : 5 %)."
        ),
        ago_standard=True,
        note="Art. 14-2-1 de la loi de 1965.",
    ),
    ModeleResolution(
        code="syndic",
        titre="Désignation du syndic et approbation de son contrat",
        majorite=Majorite.ART_25,
        texte=(
            "L'assemblée générale désigne en qualité de syndic … pour une durée de … mois, "
            "à compter du … jusqu'au …, et approuve le contrat de syndic joint à la convocation. "
            "Elle mandate le président de séance pour signer ce contrat."
        ),
        pieces=(
            "Projet de contrat de syndic (contrat type)",
            "Fiche d'information sur le prix et les prestations",
            "Contrats concurrents issus de la mise en concurrence par le conseil syndical",
        ),
        note="Mise en concurrence par le conseil syndical : art. 21 de la loi de 1965. "
        "Passerelle de l'art. 25-1 possible.",
    ),
    ModeleResolution(
        code="conseil_syndical",
        titre="Désignation des membres du conseil syndical",
        majorite=Majorite.ART_25,
        texte=(
            "L'assemblée générale désigne en qualité de membre du conseil syndical, "
            "pour une durée de … ans : …"
        ),
        note="Prévoir une résolution par candidat.",
    ),
    ModeleResolution(
        code="seuil_consultation_cs",
        titre="Montant des marchés et contrats à partir duquel la consultation du conseil syndical est obligatoire",
        majorite=Majorite.ART_25,
        texte="L'assemblée générale fixe ce montant à … € TTC.",
        note="Art. 21 de la loi de 1965.",
    ),
    ModeleResolution(
        code="seuil_concurrence",
        titre="Montant des marchés et contrats à partir duquel une mise en concurrence est obligatoire",
        majorite=Majorite.ART_25,
        texte="L'assemblée générale fixe ce montant à … € TTC.",
        note="Art. 21 de la loi de 1965.",
    ),
    ModeleResolution(
        code="travaux_entretien",
        titre="Travaux d'entretien ou de conservation des parties communes",
        majorite=Majorite.ART_24,
        texte=(
            "L'assemblée générale, après avoir pris connaissance des devis joints et de l'avis "
            "du conseil syndical, décide de faire réaliser les travaux de … par l'entreprise … "
            "pour un montant de … € TTC. Les honoraires du syndic sont fixés à … % HT du montant "
            "des travaux. Les appels de fonds seront exigibles le …"
        ),
        pieces=(
            "Devis et conditions essentielles des marchés proposés",
            "Avis du conseil syndical",
        ),
    ),
    ModeleResolution(
        code="travaux_amelioration",
        titre="Travaux d'amélioration, de transformation ou d'addition",
        majorite=Majorite.ART_25,
        texte=(
            "L'assemblée générale décide de faire réaliser les travaux de … pour un montant de "
            "… € TTC, selon le devis de l'entreprise … joint à la convocation."
        ),
        pieces=(
            "Devis et conditions essentielles des marchés proposés",
            "Avis du conseil syndical",
        ),
    ),
    ModeleResolution(
        code="autorisation_travaux_copro",
        titre="Autorisation donnée à un copropriétaire de réaliser des travaux affectant les parties communes",
        majorite=Majorite.ART_25,
        texte=(
            "L'assemblée générale autorise M./Mme …, propriétaire du lot n° …, à réaliser à ses "
            "frais exclusifs les travaux suivants : …, conformément au descriptif joint, sous "
            "réserve du respect des règles de l'art et de l'obtention des autorisations "
            "administratives nécessaires."
        ),
        pieces=("Descriptif précisant l'implantation et la consistance des travaux",),
        note="Art. 25 b) de la loi de 1965 ; art. 10 du décret pour la demande d'inscription.",
    ),
    ModeleResolution(
        code="action_justice",
        titre="Autorisation donnée au syndic d'agir en justice",
        majorite=Majorite.ART_24,
        texte=(
            "L'assemblée générale autorise le syndic à engager une action en justice à "
            "l'encontre de … aux fins de …"
        ),
        note="Art. 55 du décret de 1967 (non requise pour le recouvrement des charges).",
    ),
    ModeleResolution(
        code="delegation_cs",
        titre="Délégation de pouvoir au conseil syndical",
        majorite=Majorite.ART_25,
        texte=(
            "L'assemblée générale délègue au conseil syndical le pouvoir de prendre la décision "
            "suivante : … dans la limite d'un montant de … €."
        ),
        note="Art. 21-1 et suivants de la loi de 1965.",
    ),
    ModeleResolution(
        code="alienation_parties_communes",
        titre="Aliénation de parties communes",
        majorite=Majorite.ART_26,
        texte="L'assemblée générale décide de céder à … la partie commune suivante : … pour un prix de … €.",
        pieces=("Projet d'acte modificatif de l'état descriptif de division et du règlement",),
        note="Unanimité si la conservation de la partie commune est nécessaire au respect de la destination de l'immeuble.",
    ),
    ModeleResolution(
        code="modification_reglement",
        titre="Modification du règlement de copropriété (jouissance, usage, administration des parties communes)",
        majorite=Majorite.ART_26,
        texte="L'assemblée générale décide de modifier l'article … du règlement de copropriété comme suit : …",
        pieces=("Projet de modification du règlement de copropriété",),
    ),
    ModeleResolution(
        code="repartition_charges",
        titre="Modification de la répartition des charges",
        majorite=Majorite.UNANIMITE,
        texte="L'assemblée générale décide de modifier la répartition des charges comme suit : …",
        pieces=("Projet de nouvelle répartition des charges",),
        note="Art. 11 de la loi : unanimité, sauf cas particuliers (changement d'usage d'un lot, aliénation…).",
    ),
    ModeleResolution(
        code="information",
        titre="Questions diverses / information",
        majorite=Majorite.INFORMATION,
        texte="Point d'information, ne donnant pas lieu à un vote.",
        note="Aucune décision ne peut être prise sur une question non inscrite à l'ordre du jour.",
    ),
]

MODELES_PAR_CODE = {m.code: m for m in MODELES}


def libelle_exercice(assemblee):
    if assemblee.exercice_debut and assemblee.exercice_fin:
        return f"du {assemblee.exercice_debut:%d/%m/%Y} au {assemblee.exercice_fin:%d/%m/%Y}"
    return "…"


def instancier(modele, assemblee):
    """Renvoie les valeurs d'une résolution construite depuis un modèle."""
    exercice = libelle_exercice(assemblee)
    return {
        "code_modele": modele.code,
        "titre": modele.titre.replace(EXERCICE, exercice),
        "texte": modele.texte.replace(EXERCICE, exercice),
        "majorite": modele.majorite,
    }


# --- Rétroplanning -----------------------------------------------------------
# Chaque étape : (libellé, jours avant l'AG ou "envoi" pour la date d'envoi
# conseillée, référence légale, code de résolution conditionnant l'étape).

ETAPES_PLANNING = [
    ("Recenser les demandes d'inscription de questions des copropriétaires", 90, "Art. 10 du décret", None),
    ("Arrêter les comptes de l'exercice et les transmettre au conseil syndical pour contrôle", 75, "Art. 21 de la loi", "comptes"),
    ("Lancer la mise en concurrence du contrat de syndic par le conseil syndical", 75, "Art. 21 de la loi", "syndic"),
    ("Élaborer le projet de budget prévisionnel avec le conseil syndical", 60, "Art. 14-1 de la loi", "budget"),
    ("Collecter les devis et l'avis du conseil syndical sur les travaux", 50, "Art. 11 du décret", "travaux"),
    ("Transmettre le projet d'ordre du jour au conseil syndical pour relecture", 45, "", None),
    ("Valider l'ordre du jour et les projets de résolutions avec le conseil syndical", 35, "", None),
    ("Réunir toutes les pièces à notifier avec la convocation", 30, "Art. 11 du décret", None),
    ("Saisir l'ordre du jour dans Even et envoyer les convocations (recommandé)", "envoi", "Art. 9 et 64 du décret", None),
    ("Date limite légale : convocation présentée au moins 21 jours avant l'AG", 21, "Art. 9 du décret", None),
    ("Organiser la consultation des pièces justificatives des charges", 10, "Art. 18-1 de la loi", "comptes"),
    ("Date limite de réception des formulaires de vote par correspondance (3 jours francs)", 4, "Art. 9 bis du décret", None),
    ("Préparer la feuille de présence et les documents de séance dans Even", 2, "Art. 14 du décret", None),
]


def etapes_pour(assemblee):
    """Calcule les tâches du rétroplanning pour une assemblée."""
    codes = set(assemblee.resolutions.values_list("code_modele", flat=True))
    a_des_travaux = any(c.startswith("travaux") for c in codes)
    date_ag = assemblee.date.date()
    etapes = []
    for libelle, delai, reference, condition in ETAPES_PLANNING:
        if condition == "travaux":
            if not a_des_travaux:
                continue
        elif condition and condition not in codes:
            continue
        if delai == "envoi":
            echeance = assemblee.date_envoi_conseillee
        else:
            echeance = date_ag - timedelta(days=delai)
        etapes.append({"libelle": libelle, "echeance": echeance, "reference": reference})
    return etapes
