# Préparation des assemblées générales de copropriété

Application web qui prépare en amont les AG de copropriété, avant la convocation émise depuis **Even**.

## Fonctionnalités

- **Import Even** : copropriétaires, lots et tantièmes, à partir d'un export CSV ou Excel (une ligne par lot).
  Les colonnes sont détectées automatiquement puis peuvent être corrigées à l'écran. Un réimport synchronise la copropriété
  (ajouts, mises à jour, suppressions) et conserve les membres du conseil syndical indiqués dans l'application.
- **Ordre du jour** : bibliothèque de résolutions types (bureau de séance, comptes, budget, fonds de travaux, syndic,
  conseil syndical, travaux, autorisations, art. 26, unanimité…), avec la majorité habituelle et les pièces à notifier.
  Pour chaque résolution, on suit son origine (syndic, conseil syndical, demande d'un copropriétaire au titre de l'art. 10)
  et son statut de validation.
- **Contrôles avant convocation** : délai de 21 jours (art. 9 du décret de 1967), majorité inhabituelle, président de
  séance en première résolution, projets de résolution incomplets (« … »), pièces à notifier manquantes (art. 11),
  demandes art. 10 tardives, tâches en retard.
- **Pièces jointes** : dépôt des fichiers et suivi de ce qui est prêt et de ce qui manque.
- **Rétroplanning** : étapes calculées à partir de la date de l'AG et du contenu de l'ordre du jour, avec une date d'envoi
  conseillée (J-21 plus une marge postale réglable).
- **Export vers Even** : ordre du jour imprimable (ou à enregistrer en PDF), texte brut à copier, tableau CSV des résolutions.

> Les majorités et les références légales sont des repères à vérifier au regard du règlement de copropriété
> et de l'évolution des textes.

## Installation

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver
```

Ouvrir ensuite http://127.0.0.1:8000.

Données de démonstration (copropriété fictive importée depuis `exemples/export_even_exemple.csv`, et une AG à J+60) :

```bash
.venv/bin/python manage.py charger_demo
```

Tests : `.venv/bin/python manage.py test ag`

## Production

Variables d'environnement : `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS`, `AG_MEDIA_ROOT`
(dossier des pièces téléversées). Les pièces ne sont servies qu'aux utilisateurs connectés.

## Organisation du code

| Fichier | Rôle |
|---|---|
| `ag/models.py` | Copropriétés, copropriétaires, lots, AG, résolutions, pièces, tâches |
| `ag/bibliotheque.py` | Résolutions types et étapes du rétroplanning |
| `ag/controles.py` | Contrôles de cohérence avant convocation |
| `ag/import_even.py` | Lecture, détection des colonnes et synchronisation de l'export Even |
| `ag/views.py`, `ag/templates/` | Écrans |
