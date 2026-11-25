from django.contrib import admin

from .models import Assemblee, Copropriete, Coproprietaire, Lot, Piece, Resolution, Tache


class LotInline(admin.TabularInline):
    model = Lot
    extra = 0


@admin.register(Copropriete)
class CoproprieteAdmin(admin.ModelAdmin):
    list_display = ["nom", "reference_even", "ville", "date_dernier_import"]
    search_fields = ["nom", "reference_even"]


@admin.register(Coproprietaire)
class CoproprietaireAdmin(admin.ModelAdmin):
    list_display = ["nom", "copropriete", "code_even", "membre_conseil_syndical"]
    list_filter = ["copropriete"]
    search_fields = ["nom", "code_even"]
    inlines = [LotInline]


class ResolutionInline(admin.StackedInline):
    model = Resolution
    extra = 0


@admin.register(Assemblee)
class AssembleeAdmin(admin.ModelAdmin):
    list_display = ["copropriete", "type", "date", "statut"]
    list_filter = ["statut", "type"]
    inlines = [ResolutionInline]


admin.site.register(Piece)
admin.site.register(Tache)
