from pathlib import Path

from django.conf import settings
from django.test import TestCase

from ag import import_even
from ag.models import Copropriete

EXEMPLE = Path(settings.BASE_DIR) / "exemples" / "export_even_exemple.csv"


class DetectionTests(TestCase):
    def test_detection_des_colonnes_de_l_exemple(self):
        entetes, _ = import_even.lire_fichier(EXEMPLE.name, EXEMPLE.read_bytes())
        m = import_even.detecter_colonnes(entetes)
        self.assertEqual(entetes[m["numero_lot"]], "N° lot")
        self.assertEqual(entetes[m["tantiemes"]], "Tantièmes")
        self.assertEqual(entetes[m["nom"]], "Nom")
        self.assertEqual(entetes[m["code"]], "Code copropriétaire")
        self.assertEqual(entetes[m["email"]], "E-mail")

    def test_code_postal_n_est_pas_pris_pour_le_code_coproprietaire(self):
        m = import_even.detecter_colonnes(["Lot", "Propriétaire", "Code postal", "Millièmes"])
        self.assertIsNone(m["code"])
        self.assertEqual(m["tantiemes"], 3)

    def test_ligne_d_entete_apres_un_titre(self):
        contenu = "Liste des lots;;\nLot;Copropriétaire;Tantièmes\n1;DUPONT;100\n".encode()
        entetes, donnees = import_even.lire_fichier("x.csv", contenu)
        self.assertEqual(entetes, ["Lot", "Copropriétaire", "Tantièmes"])
        self.assertEqual(donnees, [["1", "DUPONT", "100"]])

    def test_conversion_des_tantiemes(self):
        self.assertEqual(import_even.convertir_tantiemes("1 234"), 1234)
        self.assertEqual(import_even.convertir_tantiemes("152,00"), 152)
        for invalide in ("", "abc", "12,5", "-3"):
            with self.assertRaises(ValueError):
                import_even.convertir_tantiemes(invalide)


class ImportTests(TestCase):
    def setUp(self):
        self.copro = Copropriete.objects.create(nom="Test")

    def _analyse(self, contenu, nom="x.csv"):
        entetes, donnees = import_even.lire_fichier(nom, contenu)
        return import_even.analyser(donnees, import_even.detecter_colonnes(entetes))

    def test_import_de_l_exemple(self):
        analyse = self._analyse(EXEMPLE.read_bytes())
        self.assertEqual(analyse.erreurs, [])
        stats = import_even.importer(self.copro, analyse)
        self.assertEqual(stats["lots"], 12)
        self.assertEqual(self.copro.coproprietaires.count(), 7)
        self.assertEqual(self.copro.total_tantiemes, 1000)
        martin = self.copro.coproprietaires.get(code_even="C001")
        self.assertEqual(martin.tantiemes, 156)

    def test_erreurs_detectees(self):
        analyse = self._analyse("Lot;Nom;Tantièmes\n1;A;10\n1;B;20\n2;;5\n3;C;x\n".encode())
        self.assertEqual(len(analyse.erreurs), 3)
        with self.assertRaises(import_even.ErreurImport):
            import_even.importer(self.copro, analyse)

    def test_reimport_synchronise_et_conserve_le_conseil_syndical(self):
        import_even.importer(self.copro, self._analyse("Code;Lot;Nom;Tantièmes\nA;1;Alice;60\nB;2;Bob;40\n".encode()))
        alice = self.copro.coproprietaires.get(code_even="A")
        alice.membre_conseil_syndical = True
        alice.save()
        stats = import_even.importer(
            self.copro, self._analyse("Code;Lot;Nom;Tantièmes\nA;1;Alice Martin;60\nC;2;Chloé;40\n".encode())
        )
        self.assertEqual((stats["crees"], stats["maj"], stats["supprimes"]), (1, 1, 1))
        alice.refresh_from_db()
        self.assertTrue(alice.membre_conseil_syndical)
        self.assertEqual(alice.nom, "Alice Martin")
        self.assertFalse(self.copro.coproprietaires.filter(code_even="B").exists())

    def test_colonne_obligatoire_manquante(self):
        with self.assertRaises(import_even.ErreurImport):
            import_even.analyser([["1", "A"]], {"numero_lot": 0, "nom": 1, "tantiemes": None})

    def test_import_excel(self):
        import io

        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.append(["N° de lot", "Copropriétaire", "Millièmes"])
        ws.append([1, "DUPONT", 600])
        ws.append([2, "DURAND", 400.0])
        buf = io.BytesIO()
        wb.save(buf)
        analyse = self._analyse(buf.getvalue(), "export.xlsx")
        self.assertEqual(analyse.erreurs, [])
        self.assertEqual(analyse.total_tantiemes, 1000)
