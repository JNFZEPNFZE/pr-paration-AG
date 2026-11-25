from django.urls import path

from . import views

urlpatterns = [
    path("", views.accueil, name="accueil"),
    # Copropriétés et import Even
    path("coproprietes/", views.copropriete_liste, name="copropriete_liste"),
    path("coproprietes/nouvelle/", views.copropriete_form, name="copropriete_creer"),
    path("coproprietes/<int:pk>/", views.copropriete_detail, name="copropriete_detail"),
    path("coproprietes/<int:pk>/modifier/", views.copropriete_form, name="copropriete_modifier"),
    path("coproprietes/<int:pk>/conseil/<int:cpk>/", views.coproprietaire_conseil, name="coproprietaire_conseil"),
    path("coproprietes/<int:pk>/import/", views.import_even_televersement, name="import_even"),
    path("coproprietes/<int:pk>/import/colonnes/", views.import_even_correspondance, name="import_even_correspondance"),
    path("coproprietes/<int:pk>/ag/nouvelle/", views.assemblee_creer, name="assemblee_creer"),
    # Assemblées
    path("ag/<int:pk>/", views.assemblee_detail, name="assemblee_detail"),
    path("ag/<int:pk>/modifier/", views.assemblee_modifier, name="assemblee_modifier"),
    path("ag/<int:pk>/supprimer/", views.assemblee_supprimer, name="assemblee_supprimer"),
    path("ag/<int:pk>/statut/", views.assemblee_statut, name="assemblee_statut"),
    path("ag/<int:pk>/planning/", views.planning_generer, name="planning_generer"),
    path("ag/<int:pk>/taches/", views.tache_ajouter, name="tache_ajouter"),
    path("ag/<int:pk>/pieces/", views.piece_ajouter, name="piece_ajouter"),
    path("ag/<int:ag_pk>/resolutions/nouvelle/", views.resolution_form, name="resolution_creer"),
    path("ag/<int:pk>/resolutions/modele/", views.resolution_depuis_modele, name="resolution_depuis_modele"),
    path("ag/<int:pk>/export/ordre-du-jour/", views.export_ordre_du_jour, name="export_ordre_du_jour"),
    path("ag/<int:pk>/export/texte/", views.export_texte, name="export_texte"),
    path("ag/<int:pk>/export/csv/", views.export_csv, name="export_csv"),
    # Résolutions, pièces, tâches
    path("resolutions/<int:pk>/", views.resolution_form, name="resolution_modifier"),
    path("resolutions/<int:pk>/supprimer/", views.resolution_supprimer, name="resolution_supprimer"),
    path("resolutions/<int:pk>/deplacer/<str:sens>/", views.resolution_deplacer, name="resolution_deplacer"),
    path("pieces/<int:pk>/fichier/", views.piece_televerser, name="piece_televerser"),
    path("pieces/<int:pk>/telecharger/", views.piece_telecharger, name="piece_telecharger"),
    path("pieces/<int:pk>/basculer/", views.piece_basculer, name="piece_basculer"),
    path("pieces/<int:pk>/supprimer/", views.piece_supprimer, name="piece_supprimer"),
    path("taches/<int:pk>/basculer/", views.tache_basculer, name="tache_basculer"),
    path("taches/<int:pk>/supprimer/", views.tache_supprimer, name="tache_supprimer"),
]
