from datetime import date, datetime, time, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from ag import import_even
from ag.bibliotheque import MODELES, MODELES_PAR_CODE
from ag.models import Assemblee, Copropriete
from ag.views import _creer_resolution, _generer_planning


class Command(BaseCommand):
    help = "Crée une copropriété fictive, importe l'export d'exemple et prépare une AG."

    def handle(self, *args, **options):
        fichier = Path(settings.BASE_DIR) / "exemples" / "export_even_exemple.csv"
        copro, _ = Copropriete.objects.get_or_create(
            nom="Résidence Les Lilas (démo)",
            defaults={"adresse": "12 rue des Lilas", "code_postal": "69003", "ville": "Lyon", "reference_even": "DEMO01"},
        )
        entetes, donnees = import_even.lire_fichier(fichier.name, fichier.read_bytes())
        analyse = import_even.analyser(donnees, import_even.detecter_colonnes(entetes))
        stats = import_even.importer(copro, analyse)
        copro.coproprietaires.filter(code_even__in=["C002", "C004"]).update(membre_conseil_syndical=True)

        jour = timezone.localdate() + timedelta(days=60)
        annee = jour.year - 1
        ag = Assemblee.objects.create(
            copropriete=copro,
            date=timezone.make_aware(datetime.combine(jour, time(18, 30))),
            lieu="Salle polyvalente, 4 place du Marché, Lyon 3e",
            exercice_debut=date(annee, 1, 1),
            exercice_fin=date(annee, 12, 31),
        )
        for ordre, modele in enumerate((m for m in MODELES if m.ago_standard), start=1):
            _creer_resolution(ag, modele, ordre)
        _creer_resolution(ag, MODELES_PAR_CODE["syndic"])
        r = _creer_resolution(ag, MODELES_PAR_CODE["autorisation_travaux_copro"])
        r.origine, r.demandeur = r.Origine.COPROPRIETAIRE, "M. BERNARD Luc"
        r.date_demande = timezone.localdate() - timedelta(days=10)
        r.save()
        _generer_planning(ag)
        self.stdout.write(
            self.style.SUCCESS(f"Démo prête : {stats['lots']} lots importés, AG n° {ag.pk} le {jour:%d/%m/%Y}.")
        )
