"""Modèle de données pour la préparation des assemblées générales de copropriété.

Le logiciel couvre la phase *amont* de l'AG : la convocation elle-même est
émise depuis le logiciel métier (Even). Les copropriétaires, lots et tantièmes
sont importés depuis un export Even.
"""

from datetime import timedelta

from django.db import models
from django.urls import reverse


class Majorite(models.TextChoices):
    ART_24 = "24", "Article 24 (majorité simple des voix exprimées)"
    ART_25 = "25", "Article 25 (majorité absolue des voix de tous les copropriétaires)"
    ART_26 = "26", "Article 26 (double majorité)"
    UNANIMITE = "U", "Unanimité"
    INFORMATION = "I", "Sans vote (information)"


MAJORITE_COURTE = {
    Majorite.ART_24: "Art. 24",
    Majorite.ART_25: "Art. 25",
    Majorite.ART_26: "Art. 26",
    Majorite.UNANIMITE: "Unanimité",
    Majorite.INFORMATION: "Sans vote",
}


class Copropriete(models.Model):
    nom = models.CharField(max_length=200)
    reference_even = models.CharField(
        "référence Even", max_length=50, blank=True, help_text="Code de l'immeuble dans Even."
    )
    adresse = models.CharField(max_length=255, blank=True)
    code_postal = models.CharField(max_length=10, blank=True)
    ville = models.CharField(max_length=100, blank=True)
    date_dernier_import = models.DateTimeField("dernier import Even", null=True, blank=True)

    class Meta:
        ordering = ["nom"]
        verbose_name = "copropriété"

    def __str__(self):
        return self.nom

    def get_absolute_url(self):
        return reverse("copropriete_detail", args=[self.pk])

    @property
    def total_tantiemes(self):
        return self.lots.aggregate(t=models.Sum("tantiemes"))["t"] or 0


class Coproprietaire(models.Model):
    copropriete = models.ForeignKey(
        Copropriete, on_delete=models.CASCADE, related_name="coproprietaires"
    )
    code_even = models.CharField("code Even", max_length=50, blank=True)
    nom = models.CharField(max_length=200)
    adresse = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    telephone = models.CharField("téléphone", max_length=50, blank=True)
    membre_conseil_syndical = models.BooleanField("membre du conseil syndical", default=False)

    class Meta:
        ordering = ["nom"]
        verbose_name = "copropriétaire"

    def __str__(self):
        return self.nom

    @property
    def tantiemes(self):
        return sum(lot.tantiemes for lot in self.lots.all())


class Lot(models.Model):
    copropriete = models.ForeignKey(Copropriete, on_delete=models.CASCADE, related_name="lots")
    proprietaire = models.ForeignKey(
        Coproprietaire, on_delete=models.CASCADE, related_name="lots"
    )
    numero = models.CharField("n° de lot", max_length=30)
    nature = models.CharField(max_length=100, blank=True, help_text="Appartement, cave, parking…")
    batiment = models.CharField("bâtiment", max_length=50, blank=True)
    tantiemes = models.PositiveIntegerField("tantièmes généraux")

    class Meta:
        ordering = ["numero"]
        constraints = [
            models.UniqueConstraint(fields=["copropriete", "numero"], name="lot_unique_par_copro")
        ]

    def __str__(self):
        return f"Lot {self.numero}"


class Assemblee(models.Model):
    class Type(models.TextChoices):
        ORDINAIRE = "AGO", "Assemblée générale ordinaire"
        EXTRAORDINAIRE = "AGE", "Assemblée générale extraordinaire"

    class Statut(models.TextChoices):
        PREPARATION = "prep", "En préparation"
        VALIDATION_CS = "cs", "En relecture par le conseil syndical"
        PRETE = "prete", "Prête à convoquer"
        CONVOQUEE = "convoquee", "Convoquée dans Even"
        TENUE = "tenue", "Tenue"

    copropriete = models.ForeignKey(
        Copropriete, on_delete=models.CASCADE, related_name="assemblees"
    )
    type = models.CharField(max_length=3, choices=Type.choices, default=Type.ORDINAIRE)
    date = models.DateTimeField("date et heure")
    lieu = models.CharField(max_length=255, blank=True)
    exercice_debut = models.DateField("début de l'exercice à approuver", null=True, blank=True)
    exercice_fin = models.DateField("fin de l'exercice à approuver", null=True, blank=True)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.PREPARATION)
    marge_postale = models.PositiveSmallIntegerField(
        "marge postale (jours)",
        default=5,
        help_text="Jours ajoutés au délai légal de 21 jours pour couvrir l'acheminement du recommandé.",
    )
    notes = models.TextField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]
        verbose_name = "assemblée générale"
        verbose_name_plural = "assemblées générales"

    def __str__(self):
        return f"{self.get_type_display()} du {self.date:%d/%m/%Y} – {self.copropriete}"

    def get_absolute_url(self):
        return reverse("assemblee_detail", args=[self.pk])

    @property
    def date_limite_legale_convocation(self):
        """Dernier jour où la convocation doit avoir été *présentée* au destinataire.

        Art. 9 du décret du 17 mars 1967 : 21 jours au moins avant la réunion, le délai
        courant à compter du lendemain de la première présentation du recommandé.
        """
        return self.date.date() - timedelta(days=21)

    @property
    def date_envoi_conseillee(self):
        return self.date_limite_legale_convocation - timedelta(days=self.marge_postale)


class Resolution(models.Model):
    class Origine(models.TextChoices):
        SYNDIC = "syndic", "Syndic"
        CONSEIL = "cs", "Conseil syndical"
        COPROPRIETAIRE = "copro", "Demande d'un copropriétaire (art. 10)"

    class Statut(models.TextChoices):
        BROUILLON = "brouillon", "Brouillon"
        A_VALIDER = "a_valider", "À valider par le conseil syndical"
        VALIDEE = "validee", "Validée"

    assemblee = models.ForeignKey(Assemblee, on_delete=models.CASCADE, related_name="resolutions")
    ordre = models.PositiveSmallIntegerField(default=0)
    code_modele = models.CharField(
        max_length=50, blank=True, help_text="Résolution type de la bibliothèque dont elle est issue."
    )
    titre = models.CharField(max_length=255)
    texte = models.TextField("projet de résolution", blank=True)
    majorite = models.CharField(max_length=2, choices=Majorite.choices, default=Majorite.ART_24)
    origine = models.CharField(max_length=10, choices=Origine.choices, default=Origine.SYNDIC)
    demandeur = models.CharField(
        max_length=200, blank=True, help_text="Copropriétaire à l'origine de la demande (art. 10)."
    )
    date_demande = models.DateField(
        "date de réception de la demande", null=True, blank=True
    )
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.BROUILLON)
    commentaire_interne = models.TextField(
        blank=True, help_text="Non repris dans l'ordre du jour exporté."
    )

    class Meta:
        ordering = ["ordre", "pk"]
        verbose_name = "résolution"

    def __str__(self):
        return f"{self.ordre}. {self.titre}"

    @property
    def majorite_courte(self):
        return MAJORITE_COURTE.get(self.majorite, self.majorite)


def chemin_piece(instance, filename):
    return f"assemblees/{instance.assemblee_id}/{filename}"


class Piece(models.Model):
    """Document à notifier avec la convocation ou à préparer pour l'AG."""

    assemblee = models.ForeignKey(Assemblee, on_delete=models.CASCADE, related_name="pieces")
    resolution = models.ForeignKey(
        Resolution, on_delete=models.CASCADE, related_name="pieces", null=True, blank=True
    )
    libelle = models.CharField("libellé", max_length=255)
    obligatoire = models.BooleanField(
        default=False, help_text="Pièce à notifier avec la convocation (art. 11 du décret de 1967)."
    )
    fichier = models.FileField(upload_to=chemin_piece, blank=True)
    recue = models.BooleanField("reçue / prête", default=False)

    class Meta:
        ordering = ["resolution__ordre", "libelle"]
        verbose_name = "pièce"

    def __str__(self):
        return self.libelle

    @property
    def prete(self):
        return self.recue or bool(self.fichier)


class Tache(models.Model):
    """Étape du rétroplanning de préparation."""

    assemblee = models.ForeignKey(Assemblee, on_delete=models.CASCADE, related_name="taches")
    libelle = models.CharField("libellé", max_length=255)
    echeance = models.DateField("échéance")
    faite = models.BooleanField(default=False)
    reference = models.CharField("référence légale", max_length=100, blank=True)

    class Meta:
        ordering = ["echeance", "pk"]
        verbose_name = "tâche"

    def __str__(self):
        return self.libelle
