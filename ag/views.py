import csv
import uuid
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Max, Sum
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import import_even
from .bibliotheque import ETAPES_PLANNING, MODELES, MODELES_PAR_CODE, etapes_pour, instancier
from .controles import ATTENTION, BLOQUANT, controler
from .forms import (
    AjoutModeleForm,
    AssembleeForm,
    CoproprieteForm,
    CorrespondanceForm,
    ImportForm,
    PieceForm,
    ResolutionForm,
    TacheForm,
)
from .models import Assemblee, Copropriete, Majorite, Piece, Resolution, Tache

# --- Accueil -----------------------------------------------------------------


@login_required
def accueil(request):
    aujourdhui = timezone.localdate()
    a_venir = (
        Assemblee.objects.filter(date__date__gte=aujourdhui)
        .select_related("copropriete")
        .order_by("date")
    )
    lignes = []
    for ag in a_venir:
        alertes = controler(ag, aujourdhui)
        lignes.append(
            {
                "ag": ag,
                "bloquants": sum(a.niveau == BLOQUANT for a in alertes),
                "attentions": sum(a.niveau == ATTENTION for a in alertes),
            }
        )
    taches = (
        Tache.objects.filter(faite=False, echeance__lte=aujourdhui + timedelta(days=14))
        .filter(assemblee__date__date__gte=aujourdhui)
        .select_related("assemblee__copropriete")
    )
    return render(
        request,
        "ag/accueil.html",
        {"lignes": lignes, "taches": taches, "aujourdhui": aujourdhui},
    )


# --- Copropriétés ------------------------------------------------------------


@login_required
def copropriete_liste(request):
    copros = Copropriete.objects.annotate(
        nb_lots=Count("lots", distinct=True),
        nb_copros=Count("coproprietaires", distinct=True),
    )
    return render(request, "ag/copropriete_liste.html", {"coproprietes": copros})


@login_required
def copropriete_form(request, pk=None):
    copro = get_object_or_404(Copropriete, pk=pk) if pk else None
    form = CoproprieteForm(request.POST or None, instance=copro)
    if request.method == "POST" and form.is_valid():
        copro = form.save()
        messages.success(request, "Copropriété enregistrée.")
        return redirect(copro)
    return render(request, "ag/form.html", {"form": form, "titre": "Copropriété", "retour": copro})


@login_required
def copropriete_detail(request, pk):
    copro = get_object_or_404(Copropriete, pk=pk)
    coproprietaires = copro.coproprietaires.annotate(
        voix=Sum("lots__tantiemes"), nb_lots=Count("lots")
    ).prefetch_related("lots")
    return render(
        request,
        "ag/copropriete_detail.html",
        {
            "copro": copro,
            "coproprietaires": coproprietaires,
            "total": copro.total_tantiemes,
            "assemblees": copro.assemblees.all(),
        },
    )


@login_required
@require_POST
def coproprietaire_conseil(request, pk, cpk):
    copro = get_object_or_404(Copropriete, pk=pk)
    c = get_object_or_404(copro.coproprietaires, pk=cpk)
    c.membre_conseil_syndical = not c.membre_conseil_syndical
    c.save(update_fields=["membre_conseil_syndical"])
    return redirect(copro)


# --- Import Even ---------------------------------------------------------------


def _dossier_import():
    dossier = Path(settings.MEDIA_ROOT) / "imports_temporaires"
    dossier.mkdir(parents=True, exist_ok=True)
    return dossier


@login_required
def import_even_televersement(request, pk):
    copro = get_object_or_404(Copropriete, pk=pk)
    form = ImportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        fichier = form.cleaned_data["fichier"]
        contenu = fichier.read()
        try:
            import_even.lire_fichier(fichier.name, contenu)
        except import_even.ErreurImport as exc:
            form.add_error("fichier", str(exc))
        else:
            jeton = uuid.uuid4().hex
            (_dossier_import() / jeton).write_bytes(contenu)
            request.session[f"import_{copro.pk}"] = {"jeton": jeton, "nom": fichier.name}
            return redirect("import_even_correspondance", pk=copro.pk)
    return render(request, "ag/import_televersement.html", {"copro": copro, "form": form})


@login_required
def import_even_correspondance(request, pk):
    copro = get_object_or_404(Copropriete, pk=pk)
    info = request.session.get(f"import_{copro.pk}")
    chemin = _dossier_import() / info["jeton"] if info else None
    if not chemin or not chemin.exists():
        messages.error(request, "Aucun fichier en cours d'import : téléverser l'export Even.")
        return redirect("import_even", pk=copro.pk)

    entetes, donnees = import_even.lire_fichier(info["nom"], chemin.read_bytes())
    form = CorrespondanceForm(
        request.POST or None, entetes=entetes, initial_map=import_even.detecter_colonnes(entetes)
    )
    analyse, erreur = None, None
    if form.is_valid() or request.method == "GET":
        correspondance = form.correspondance() if request.method == "POST" else import_even.detecter_colonnes(entetes)
        try:
            analyse = import_even.analyser(donnees, correspondance)
        except import_even.ErreurImport as exc:
            erreur = str(exc)
        if analyse and request.POST.get("action") == "importer" and not analyse.erreurs:
            stats = import_even.importer(copro, analyse)
            chemin.unlink(missing_ok=True)
            del request.session[f"import_{copro.pk}"]
            messages.success(
                request,
                f"Import terminé : {stats['lots']} lots, {stats['crees']} copropriétaire(s) créé(s), "
                f"{stats['maj']} mis à jour, {stats['supprimes']} supprimé(s).",
            )
            return redirect(copro)
    return render(
        request,
        "ag/import_correspondance.html",
        {
            "copro": copro,
            "form": form,
            "nom_fichier": info["nom"],
            "entetes": entetes,
            "apercu": donnees[:8],
            "nb_lignes": len(donnees),
            "analyse": analyse,
            "erreur": erreur,
            "total_actuel": copro.total_tantiemes,
        },
    )


# --- Assemblées ----------------------------------------------------------------


@login_required
def assemblee_creer(request, pk):
    copro = get_object_or_404(Copropriete, pk=pk)
    form = AssembleeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            ag = form.save(commit=False)
            ag.copropriete = copro
            ag.save()
            if form.cleaned_data.get("ordre_du_jour_type"):
                for ordre, modele in enumerate((m for m in MODELES if m.ago_standard), start=1):
                    _creer_resolution(ag, modele, ordre)
            _generer_planning(ag)
        messages.success(request, "Assemblée créée avec son rétroplanning.")
        return redirect(ag)
    return render(request, "ag/form.html", {"form": form, "titre": f"Nouvelle AG – {copro}", "retour": copro})


@login_required
def assemblee_modifier(request, pk):
    ag = get_object_or_404(Assemblee, pk=pk)
    ancienne_date = ag.date
    form = AssembleeForm(request.POST or None, instance=ag)
    if request.method == "POST" and form.is_valid():
        ag = form.save()
        if ag.date != ancienne_date:
            messages.info(request, "La date a changé : pensez à régénérer le rétroplanning.")
        messages.success(request, "Assemblée enregistrée.")
        return redirect(ag)
    return render(request, "ag/form.html", {"form": form, "titre": str(ag), "retour": ag})


@login_required
def assemblee_supprimer(request, pk):
    ag = get_object_or_404(Assemblee, pk=pk)
    if request.method == "POST":
        copro = ag.copropriete
        ag.delete()
        messages.success(request, "Assemblée supprimée.")
        return redirect(copro)
    return render(request, "ag/confirmer_suppression.html", {"objet": ag, "retour": ag})


@login_required
def assemblee_detail(request, pk):
    ag = get_object_or_404(Assemblee.objects.select_related("copropriete"), pk=pk)
    resolutions = ag.resolutions.prefetch_related("pieces")
    alertes = controler(ag)
    alertes_par_resolution = {}
    for a in alertes:
        if a.resolution:
            alertes_par_resolution.setdefault(a.resolution.pk, []).append(a)
    for r in resolutions:
        r.alertes = alertes_par_resolution.get(r.pk, [])
        r.modele = MODELES_PAR_CODE.get(r.code_modele)
    return render(
        request,
        "ag/assemblee_detail.html",
        {
            "ag": ag,
            "resolutions": resolutions,
            "alertes_generales": [a for a in alertes if not a.resolution],
            "nb_bloquants": sum(a.niveau == BLOQUANT for a in alertes),
            "taches": ag.taches.all(),
            "pieces": ag.pieces.select_related("resolution"),
            "form_modele": AjoutModeleForm(),
            "form_piece": PieceForm(assemblee=ag),
            "form_tache": TacheForm(),
            "aujourdhui": timezone.localdate(),
            "statuts": Assemblee.Statut.choices,
        },
    )


@login_required
@require_POST
def assemblee_statut(request, pk):
    ag = get_object_or_404(Assemblee, pk=pk)
    statut = request.POST.get("statut")
    if statut in Assemblee.Statut.values:
        ag.statut = statut
        ag.save(update_fields=["statut"])
        messages.success(request, f"Statut : {ag.get_statut_display()}.")
    return redirect(ag)


# --- Résolutions -------------------------------------------------------------


def _creer_resolution(ag, modele, ordre=None):
    if ordre is None:
        ordre = (ag.resolutions.aggregate(m=Max("ordre"))["m"] or 0) + 1
    r = Resolution.objects.create(assemblee=ag, ordre=ordre, **instancier(modele, ag))
    for libelle in modele.pieces:
        Piece.objects.create(assemblee=ag, resolution=r, libelle=libelle, obligatoire=True)
    return r


def _renumeroter(ag):
    for i, r in enumerate(ag.resolutions.order_by("ordre", "pk"), start=1):
        if r.ordre != i:
            r.ordre = i
            r.save(update_fields=["ordre"])


@login_required
@require_POST
def resolution_depuis_modele(request, pk):
    ag = get_object_or_404(Assemblee, pk=pk)
    form = AjoutModeleForm(request.POST)
    if form.is_valid():
        r = _creer_resolution(ag, MODELES_PAR_CODE[form.cleaned_data["modele"]])
        messages.success(request, f"Résolution « {r.titre} » ajoutée.")
        return redirect("resolution_modifier", pk=r.pk)
    return redirect(ag)


@login_required
def resolution_form(request, pk=None, ag_pk=None):
    if pk:
        r = get_object_or_404(Resolution, pk=pk)
        ag = r.assemblee
    else:
        ag = get_object_or_404(Assemblee, pk=ag_pk)
        r = Resolution(assemblee=ag)
    form = ResolutionForm(request.POST or None, instance=r)
    if request.method == "POST" and form.is_valid():
        r = form.save(commit=False)
        if not r.pk:
            r.ordre = (ag.resolutions.aggregate(m=Max("ordre"))["m"] or 0) + 1
        r.save()
        messages.success(request, "Résolution enregistrée.")
        return redirect(f"{ag.get_absolute_url()}#resolution-{r.pk}")
    modele = MODELES_PAR_CODE.get(r.code_modele)
    return render(
        request,
        "ag/resolution_form.html",
        {
            "form": form,
            "ag": ag,
            "resolution": r,
            "modele": modele,
            "majorite_modele": Majorite(modele.majorite).label if modele else "",
        },
    )


@login_required
@require_POST
def resolution_supprimer(request, pk):
    r = get_object_or_404(Resolution, pk=pk)
    ag = r.assemblee
    r.delete()
    _renumeroter(ag)
    messages.success(request, "Résolution supprimée.")
    return redirect(ag)


@login_required
@require_POST
def resolution_deplacer(request, pk, sens):
    r = get_object_or_404(Resolution, pk=pk)
    ag = r.assemblee
    _renumeroter(ag)
    r.refresh_from_db()
    voisin = ag.resolutions.filter(ordre=r.ordre + (1 if sens == "bas" else -1)).first()
    if voisin:
        voisin.ordre, r.ordre = r.ordre, voisin.ordre
        voisin.save(update_fields=["ordre"])
        r.save(update_fields=["ordre"])
    return redirect(f"{ag.get_absolute_url()}#resolution-{r.pk}")


# --- Pièces -------------------------------------------------------------------


@login_required
@require_POST
def piece_ajouter(request, pk):
    ag = get_object_or_404(Assemblee, pk=pk)
    form = PieceForm(request.POST, request.FILES, assemblee=ag)
    if form.is_valid():
        piece = form.save(commit=False)
        piece.assemblee = ag
        piece.save()
        messages.success(request, "Pièce ajoutée.")
    else:
        messages.error(request, "Pièce non ajoutée : " + "; ".join(e for errs in form.errors.values() for e in errs))
    return redirect(f"{ag.get_absolute_url()}#pieces")


@login_required
@require_POST
def piece_televerser(request, pk):
    piece = get_object_or_404(Piece, pk=pk)
    fichier = request.FILES.get("fichier")
    if fichier:
        piece.fichier = fichier
        piece.recue = True
        piece.save()
        messages.success(request, f"Fichier joint à « {piece.libelle} ».")
    return redirect(f"{piece.assemblee.get_absolute_url()}#pieces")


@login_required
@require_POST
def piece_basculer(request, pk):
    piece = get_object_or_404(Piece, pk=pk)
    piece.recue = not piece.recue
    piece.save(update_fields=["recue"])
    return redirect(f"{piece.assemblee.get_absolute_url()}#pieces")


@login_required
@require_POST
def piece_supprimer(request, pk):
    piece = get_object_or_404(Piece, pk=pk)
    ag = piece.assemblee
    if piece.fichier:
        piece.fichier.delete(save=False)
    piece.delete()
    return redirect(f"{ag.get_absolute_url()}#pieces")


@login_required
def piece_telecharger(request, pk):
    piece = get_object_or_404(Piece, pk=pk)
    if not piece.fichier:
        raise Http404
    return FileResponse(piece.fichier.open("rb"), as_attachment=True, filename=Path(piece.fichier.name).name)


# --- Rétroplanning ------------------------------------------------------------


def _generer_planning(ag):
    """(Re)génère les tâches standard en conservant celles déjà faites et les tâches ajoutées."""
    faites = set(ag.taches.filter(faite=True).values_list("libelle", flat=True))
    ag.taches.filter(libelle__in=[e[0] for e in ETAPES_PLANNING]).delete()
    for etape in etapes_pour(ag):
        Tache.objects.create(assemblee=ag, faite=etape["libelle"] in faites, **etape)


@login_required
@require_POST
def planning_generer(request, pk):
    ag = get_object_or_404(Assemblee, pk=pk)
    _generer_planning(ag)
    messages.success(request, "Rétroplanning recalculé à partir de la date et de l'ordre du jour.")
    return redirect(f"{ag.get_absolute_url()}#planning")


@login_required
@require_POST
def tache_ajouter(request, pk):
    ag = get_object_or_404(Assemblee, pk=pk)
    form = TacheForm(request.POST)
    if form.is_valid():
        tache = form.save(commit=False)
        tache.assemblee = ag
        tache.save()
    return redirect(f"{ag.get_absolute_url()}#planning")


@login_required
@require_POST
def tache_basculer(request, pk):
    tache = get_object_or_404(Tache, pk=pk)
    tache.faite = not tache.faite
    tache.save(update_fields=["faite"])
    suivant = request.POST.get("suivant", "")
    if not url_has_allowed_host_and_scheme(suivant, allowed_hosts={request.get_host()}):
        suivant = f"{tache.assemblee.get_absolute_url()}#planning"
    return redirect(suivant)


@login_required
@require_POST
def tache_supprimer(request, pk):
    tache = get_object_or_404(Tache, pk=pk)
    ag = tache.assemblee
    tache.delete()
    return redirect(f"{ag.get_absolute_url()}#planning")


# --- Exports vers Even --------------------------------------------------------


def _resolutions_export(ag):
    return ag.resolutions.prefetch_related("pieces")


@login_required
def export_ordre_du_jour(request, pk):
    ag = get_object_or_404(Assemblee.objects.select_related("copropriete"), pk=pk)
    return render(request, "ag/export_ordre_du_jour.html", {"ag": ag, "resolutions": _resolutions_export(ag)})


@login_required
def export_texte(request, pk):
    ag = get_object_or_404(Assemblee.objects.select_related("copropriete"), pk=pk)
    lignes = [str(ag).upper(), ""]
    if ag.lieu:
        lignes += [f"Lieu : {ag.lieu}", ""]
    lignes += ["ORDRE DU JOUR", ""]
    for r in _resolutions_export(ag):
        lignes.append(f"{r.ordre}. {r.titre} ({r.majorite_courte})")
        if r.texte:
            lignes.append("Projet de résolution : " + r.texte)
        pieces = [p.libelle for p in r.pieces.all() if p.obligatoire]
        if pieces:
            lignes.append("Documents joints : " + " ; ".join(pieces))
        lignes.append("")
    reponse = HttpResponse("\r\n".join(lignes), content_type="text/plain; charset=utf-8")
    reponse["Content-Disposition"] = f'attachment; filename="ordre_du_jour_ag_{ag.pk}.txt"'
    return reponse


@login_required
def export_csv(request, pk):
    ag = get_object_or_404(Assemblee, pk=pk)
    reponse = HttpResponse(content_type="text/csv; charset=utf-8")
    reponse["Content-Disposition"] = f'attachment; filename="resolutions_ag_{ag.pk}.csv"'
    reponse.write("﻿")  # BOM pour l'ouverture directe dans Excel
    w = csv.writer(reponse, delimiter=";")
    w.writerow(["N°", "Titre", "Projet de résolution", "Majorité", "Origine", "Demandeur", "Pièces jointes"])
    for r in _resolutions_export(ag):
        w.writerow(
            [
                r.ordre,
                r.titre,
                r.texte,
                r.majorite_courte,
                r.get_origine_display(),
                r.demandeur,
                " ; ".join(p.libelle for p in r.pieces.all() if p.obligatoire),
            ]
        )
    return reponse
