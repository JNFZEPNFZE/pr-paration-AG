from datetime import date, datetime, time, timedelta

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from ag.bibliotheque import MODELES_PAR_CODE
from ag.controles import ATTENTION, BLOQUANT, controler
from ag.models import Assemblee, Copropriete, Majorite, Piece, Resolution
from ag.views import _creer_resolution, _generer_planning


def creer_ag(jours=60, **kwargs):
    copro = Copropriete.objects.create(nom="Les Lilas")
    jour = timezone.localdate() + timedelta(days=jours)
    return Assemblee.objects.create(
        copropriete=copro,
        date=timezone.make_aware(datetime.combine(jour, time(18, 0))),
        **kwargs,
    )


class DelaisTests(TestCase):
    def test_dates_de_convocation(self):
        ag = creer_ag(marge_postale=5)
        self.assertEqual(ag.date_limite_legale_convocation, ag.date.date() - timedelta(days=21))
        self.assertEqual(ag.date_envoi_conseillee, ag.date.date() - timedelta(days=26))

    def test_planning_depend_de_l_ordre_du_jour(self):
        ag = creer_ag()
        _creer_resolution(ag, MODELES_PAR_CODE["president"])
        _generer_planning(ag)
        libelles = list(ag.taches.values_list("libelle", flat=True))
        self.assertFalse(any("contrat de syndic" in t for t in libelles))
        _creer_resolution(ag, MODELES_PAR_CODE["syndic"])
        _creer_resolution(ag, MODELES_PAR_CODE["travaux_entretien"])
        _generer_planning(ag)
        libelles = list(ag.taches.values_list("libelle", flat=True))
        self.assertTrue(any("contrat de syndic" in t for t in libelles))
        self.assertTrue(any("devis" in t for t in libelles))

    def test_regeneration_conserve_les_taches_faites_et_ajoutees(self):
        ag = creer_ag()
        _generer_planning(ag)
        t = ag.taches.first()
        t.faite = True
        t.save()
        ag.taches.create(libelle="Réserver la salle", echeance=date.today())
        _generer_planning(ag)
        self.assertTrue(ag.taches.get(libelle=t.libelle).faite)
        self.assertTrue(ag.taches.filter(libelle="Réserver la salle").exists())


class ControlesTests(TestCase):
    def niveaux(self, ag, **kw):
        return [(a.niveau, a.message) for a in controler(ag, **kw)]

    def test_ordre_du_jour_vide_bloquant(self):
        ag = creer_ag()
        self.assertIn((BLOQUANT, "L'ordre du jour est vide."), self.niveaux(ag))

    def test_delai_legal_depasse(self):
        ag = creer_ag(jours=10)
        _creer_resolution(ag, MODELES_PAR_CODE["president"])
        self.assertTrue(any(n == BLOQUANT and "21 jours" in m for n, m in self.niveaux(ag)))
        ag.statut = Assemblee.Statut.CONVOQUEE
        ag.save()
        self.assertFalse(any("21 jours" in m for _, m in self.niveaux(ag)))

    def test_majorite_inhabituelle_et_president_pas_en_premier(self):
        ag = creer_ag()
        r = _creer_resolution(ag, MODELES_PAR_CODE["syndic"])
        r.majorite = Majorite.ART_24
        r.save()
        _creer_resolution(ag, MODELES_PAR_CODE["president"])
        messages = self.niveaux(ag)
        self.assertTrue(any(n == ATTENTION and "Art. 25" in m for n, m in messages))
        self.assertTrue(any("première résolution" in m for _, m in messages))

    def test_pieces_obligatoires(self):
        ag = creer_ag()
        r = _creer_resolution(ag, MODELES_PAR_CODE["comptes"])
        self.assertEqual(r.pieces.filter(obligatoire=True).count(), 3)
        self.assertEqual(sum("Pièce à notifier manquante" in m for _, m in self.niveaux(ag)), 3)
        r.pieces.update(recue=True)
        self.assertEqual(sum("Pièce à notifier manquante" in m for _, m in self.niveaux(ag)), 0)

    def test_demande_art_10_tardive(self):
        ag = creer_ag()
        r = Resolution.objects.create(
            assemblee=ag,
            titre="Pose d'une climatisation",
            texte="Autoriser M. X",
            origine=Resolution.Origine.COPROPRIETAIRE,
            demandeur="M. X",
            date_demande=ag.date_envoi_conseillee + timedelta(days=1),
        )
        self.assertTrue(any(a.resolution == r and "art. 10" in a.message for a in controler(ag)))

    def test_exercice_remplace_dans_le_titre(self):
        ag = creer_ag(exercice_debut=date(2025, 1, 1), exercice_fin=date(2025, 12, 31))
        r = _creer_resolution(ag, MODELES_PAR_CODE["comptes"])
        self.assertIn("du 01/01/2025 au 31/12/2025", r.titre)


@override_settings(MEDIA_ROOT="/tmp/ag-tests-media")
class VuesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("gestionnaire", password="motdepasse")
        self.client.force_login(self.user)

    def test_connexion_obligatoire(self):
        self.client.logout()
        r = self.client.get(reverse("accueil"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("login"), r["Location"])

    def test_parcours_complet(self):
        r = self.client.post(reverse("copropriete_creer"), {"nom": "Les Lilas", "ville": "Lyon"})
        copro = Copropriete.objects.get()
        self.assertRedirects(r, copro.get_absolute_url())

        # Import Even en deux étapes
        csv = "Lot;Propriétaire;Tantièmes\n1;DUPONT;600\n2;DURAND;400\n".encode("cp1252")
        r = self.client.post(reverse("import_even", args=[copro.pk]), {"fichier": SimpleUploadedFile("e.csv", csv)})
        self.assertRedirects(r, reverse("import_even_correspondance", args=[copro.pk]))
        r = self.client.get(reverse("import_even_correspondance", args=[copro.pk]))
        self.assertContains(r, "1000")
        r = self.client.post(
            reverse("import_even_correspondance", args=[copro.pk]),
            {"numero_lot": "0", "nom": "1", "tantiemes": "2", "action": "importer"},
        )
        self.assertRedirects(r, copro.get_absolute_url())
        self.assertEqual(copro.total_tantiemes, 1000)

        # Création de l'AG avec ordre du jour type
        jour = timezone.localdate() + timedelta(days=50)
        r = self.client.post(
            reverse("assemblee_creer", args=[copro.pk]),
            {"type": "AGO", "date": f"{jour:%Y-%m-%d}T18:30", "marge_postale": 5, "ordre_du_jour_type": "on"},
        )
        ag = Assemblee.objects.get()
        self.assertRedirects(r, ag.get_absolute_url())
        self.assertEqual(ag.resolutions.first().code_modele, "president")
        self.assertTrue(ag.taches.exists())

        # Ajout depuis la bibliothèque puis déplacement
        r = self.client.post(reverse("resolution_depuis_modele", args=[ag.pk]), {"modele": "syndic"})
        syndic = ag.resolutions.get(code_modele="syndic")
        self.assertRedirects(r, reverse("resolution_modifier", args=[syndic.pk]))
        ordre = syndic.ordre
        self.client.post(reverse("resolution_deplacer", args=[syndic.pk, "haut"]))
        syndic.refresh_from_db()
        self.assertEqual(syndic.ordre, ordre - 1)

        # Résolution libre à la demande d'un copropriétaire
        r = self.client.post(
            reverse("resolution_creer", args=[ag.pk]),
            {"titre": "Ravalement", "texte": "Décide…", "majorite": "24", "origine": "copro", "statut": "brouillon"},
        )
        self.assertEqual(r.status_code, 200)  # demandeur manquant
        self.client.post(
            reverse("resolution_creer", args=[ag.pk]),
            {"titre": "Ravalement", "texte": "Décide", "majorite": "24", "origine": "copro", "demandeur": "M. X", "statut": "brouillon"},
        )
        self.assertEqual(ag.resolutions.last().titre, "Ravalement")

        # Pièce : téléversement puis téléchargement
        piece = Piece.objects.filter(assemblee=ag).first()
        self.client.post(reverse("piece_televerser", args=[piece.pk]), {"fichier": SimpleUploadedFile("devis.pdf", b"%PDF")})
        piece.refresh_from_db()
        self.assertTrue(piece.prete)
        r = self.client.get(reverse("piece_telecharger", args=[piece.pk]))
        self.assertEqual(b"".join(r.streaming_content), b"%PDF")

        # Pages et exports
        for nom in ("accueil", "copropriete_liste"):
            self.assertEqual(self.client.get(reverse(nom)).status_code, 200)
        self.assertContains(self.client.get(ag.get_absolute_url()), "Rétroplanning")
        self.assertContains(self.client.get(reverse("export_ordre_du_jour", args=[ag.pk])), "Ravalement")
        r = self.client.get(reverse("export_csv", args=[ag.pk]))
        self.assertIn("Ravalement", r.content.decode("utf-8-sig"))
        self.assertIn("ORDRE DU JOUR", self.client.get(reverse("export_texte", args=[ag.pk])).content.decode())

    def test_redirection_externe_refusee(self):
        ag = creer_ag()
        _generer_planning(ag)
        t = ag.taches.first()
        r = self.client.post(reverse("tache_basculer", args=[t.pk]), {"suivant": "https://exemple.invalid/"})
        self.assertTrue(r["Location"].startswith(ag.get_absolute_url()))
