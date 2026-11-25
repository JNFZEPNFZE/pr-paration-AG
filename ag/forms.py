from django import forms

from .bibliotheque import MODELES
from .import_even import CHAMPS
from .models import Assemblee, Copropriete, Piece, Resolution, Tache


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%d", **kwargs)


class DateTimeInput(forms.DateTimeInput):
    input_type = "datetime-local"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%dT%H:%M", **kwargs)


class CoproprieteForm(forms.ModelForm):
    class Meta:
        model = Copropriete
        fields = ["nom", "reference_even", "adresse", "code_postal", "ville"]


class AssembleeForm(forms.ModelForm):
    ordre_du_jour_type = forms.BooleanField(
        label="Pré-remplir l'ordre du jour type d'une AG ordinaire",
        required=False,
        initial=True,
    )

    class Meta:
        model = Assemblee
        fields = ["type", "date", "lieu", "exercice_debut", "exercice_fin", "marge_postale", "statut", "notes"]
        widgets = {
            "date": DateTimeInput(),
            "exercice_debut": DateInput(),
            "exercice_fin": DateInput(),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            del self.fields["ordre_du_jour_type"]
        else:
            del self.fields["statut"]

    def clean(self):
        donnees = super().clean()
        debut, fin = donnees.get("exercice_debut"), donnees.get("exercice_fin")
        if debut and fin and fin <= debut:
            self.add_error("exercice_fin", "La fin de l'exercice doit suivre son début.")
        return donnees


class ResolutionForm(forms.ModelForm):
    class Meta:
        model = Resolution
        fields = [
            "titre",
            "texte",
            "majorite",
            "origine",
            "demandeur",
            "date_demande",
            "statut",
            "commentaire_interne",
        ]
        widgets = {
            "texte": forms.Textarea(attrs={"rows": 8}),
            "commentaire_interne": forms.Textarea(attrs={"rows": 2}),
            "date_demande": DateInput(),
        }

    def clean(self):
        donnees = super().clean()
        if donnees.get("origine") == Resolution.Origine.COPROPRIETAIRE and not donnees.get("demandeur"):
            self.add_error("demandeur", "Indiquer le copropriétaire à l'origine de la demande.")
        return donnees


class AjoutModeleForm(forms.Form):
    modele = forms.ChoiceField(
        label="Résolution type",
        choices=[(m.code, f"{m.titre} — art. {m.majorite}" if m.majorite.isdigit() else m.titre) for m in MODELES],
    )


class PieceForm(forms.ModelForm):
    class Meta:
        model = Piece
        fields = ["libelle", "resolution", "obligatoire", "fichier", "recue"]

    def __init__(self, *args, assemblee=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["resolution"].queryset = assemblee.resolutions.all() if assemblee else Resolution.objects.none()
        self.fields["resolution"].required = False


class TacheForm(forms.ModelForm):
    class Meta:
        model = Tache
        fields = ["libelle", "echeance", "reference"]
        widgets = {"echeance": DateInput()}


class ImportForm(forms.Form):
    fichier = forms.FileField(
        label="Export Even (CSV ou Excel)",
        help_text="Une ligne par lot : n° de lot, copropriétaire, tantièmes…",
    )

    def clean_fichier(self):
        f = self.cleaned_data["fichier"]
        if not f.name.lower().endswith((".csv", ".txt", ".xlsx", ".xlsm")):
            raise forms.ValidationError("Formats acceptés : .csv, .txt, .xlsx.")
        if f.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Fichier trop volumineux (5 Mo maximum).")
        return f


class CorrespondanceForm(forms.Form):
    """Choix, pour chaque champ, de la colonne correspondante du fichier."""

    def __init__(self, *args, entetes=(), initial_map=None, **kwargs):
        super().__init__(*args, **kwargs)
        choix = [("", "— non importé —")] + [(str(i), e or f"Colonne {i + 1}") for i, e in enumerate(entetes)]
        for champ, (libelle, obligatoire, _) in CHAMPS.items():
            idx = (initial_map or {}).get(champ)
            self.fields[champ] = forms.ChoiceField(
                label=libelle + (" *" if obligatoire else ""),
                choices=choix,
                required=obligatoire,
                initial="" if idx is None else str(idx),
            )

    def correspondance(self):
        return {c: (int(v) if v != "" else None) for c, v in self.cleaned_data.items()}
