"""Contrôles de cohérence avant l'envoi de la convocation depuis Even."""

from dataclasses import dataclass

from django.utils import timezone

from .bibliotheque import MODELES_PAR_CODE
from .models import MAJORITE_COURTE, Assemblee, Majorite, Resolution

BLOQUANT = "bloquant"
ATTENTION = "attention"
INFO = "info"


@dataclass
class Alerte:
    niveau: str
    message: str
    resolution: Resolution | None = None


def controler(assemblee: Assemblee, aujourdhui=None):
    aujourdhui = aujourdhui or timezone.localdate()
    alertes = []
    resolutions = list(assemblee.resolutions.prefetch_related("pieces"))
    codes = [r.code_modele for r in resolutions]
    avant_convocation = assemblee.statut not in (
        Assemblee.Statut.CONVOQUEE,
        Assemblee.Statut.TENUE,
    )

    # --- Données de la copropriété --------------------------------------
    if not assemblee.copropriete.lots.exists():
        alertes.append(Alerte(ATTENTION, "Aucun lot importé pour cette copropriété : importer l'export Even."))

    # --- Délais ---------------------------------------------------------
    if avant_convocation:
        limite = assemblee.date_limite_legale_convocation
        if aujourdhui > limite:
            alertes.append(
                Alerte(
                    BLOQUANT,
                    f"Le délai légal de 21 jours est dépassé (limite de présentation : {limite:%d/%m/%Y}). "
                    "L'AG doit être reportée.",
                )
            )
        elif aujourdhui > assemblee.date_envoi_conseillee:
            alertes.append(
                Alerte(
                    ATTENTION,
                    f"La date d'envoi conseillée ({assemblee.date_envoi_conseillee:%d/%m/%Y}) est passée : "
                    f"convoquer sans attendre (limite légale de présentation : {limite:%d/%m/%Y}).",
                )
            )

    # --- Structure de l'ordre du jour ----------------------------------
    if not resolutions:
        alertes.append(Alerte(BLOQUANT, "L'ordre du jour est vide."))
        return alertes

    if "president" not in codes:
        alertes.append(Alerte(ATTENTION, "Aucune résolution d'élection du président de séance."))
    elif codes[0] != "president":
        alertes.append(
            Alerte(ATTENTION, "L'élection du président de séance devrait être la première résolution.")
        )

    if assemblee.type == Assemblee.Type.ORDINAIRE and "comptes" not in codes:
        alertes.append(Alerte(INFO, "Pas de résolution d'approbation des comptes pour cette AG ordinaire."))
    if "comptes" in codes and not (assemblee.exercice_debut and assemblee.exercice_fin):
        alertes.append(Alerte(ATTENTION, "Renseigner les dates de l'exercice comptable à approuver."))

    # --- Résolution par résolution --------------------------------------
    for r in resolutions:
        modele = MODELES_PAR_CODE.get(r.code_modele)
        if modele and r.majorite != modele.majorite:
            alertes.append(
                Alerte(
                    ATTENTION,
                    f"Majorité {r.majorite_courte} retenue alors que {MAJORITE_COURTE[modele.majorite]} "
                    "est habituellement requise pour ce type de décision.",
                    r,
                )
            )
        if r.majorite != Majorite.INFORMATION and not r.texte.strip():
            alertes.append(Alerte(BLOQUANT, "Projet de résolution non rédigé.", r))
        if "…" in r.texte or "..." in r.texte:
            alertes.append(Alerte(ATTENTION, "Le projet de résolution contient des champs à compléter (…).", r))
        if r.origine == Resolution.Origine.COPROPRIETAIRE:
            if not r.demandeur:
                alertes.append(Alerte(ATTENTION, "Préciser le copropriétaire à l'origine de la demande.", r))
            if r.date_demande and r.date_demande > assemblee.date_envoi_conseillee:
                alertes.append(
                    Alerte(
                        ATTENTION,
                        "Demande reçue après la date d'envoi conseillée : si elle ne peut être "
                        "inscrite à temps, elle est reportée à l'assemblée suivante (art. 10 du décret).",
                        r,
                    )
                )
        for piece in r.pieces.all():
            if piece.obligatoire and not piece.prete:
                alertes.append(Alerte(BLOQUANT, f"Pièce à notifier manquante : {piece.libelle}.", r))

    for piece in assemblee.pieces.filter(resolution__isnull=True, obligatoire=True):
        if not piece.prete:
            alertes.append(Alerte(BLOQUANT, f"Pièce à notifier manquante : {piece.libelle}."))

    non_validees = sum(r.statut != Resolution.Statut.VALIDEE for r in resolutions)
    if non_validees:
        alertes.append(Alerte(INFO, f"{non_validees} résolution(s) pas encore validée(s)."))

    # --- Rétroplanning -------------------------------------------------
    en_retard = assemblee.taches.filter(faite=False, echeance__lt=aujourdhui).count()
    if en_retard:
        alertes.append(Alerte(ATTENTION, f"{en_retard} tâche(s) du rétroplanning en retard."))

    ordre = {BLOQUANT: 0, ATTENTION: 1, INFO: 2}
    alertes.sort(key=lambda a: ordre[a.niveau])
    return alertes
