"""
Test per il parser TAF.
"""

import tempfile
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pf_italia.taf_parser import TafParser
from pf_italia.models import SistemaCoordinate


# Esempio di riga TAF (simulata basata sul formato)
SAMPLE_TAF_LINE = (
    "H501 "  # cod_comune (0-4)
    " "       # sezione (4-5)
    "0010"    # foglio (6-10)
    " "       # spazio
    "0"       # allegato (11-12)
    "   "     # spazi
    "01"      # numero_pf (15-17)
    "             "  # spazi
    "SPIGOLO N-O FABBRICATO VIA ROMA 1                                    "  # descr (30-100)
    "  "      # spazi
    "4641234.567"  # coord_nord (102-114)
    "  "      # spazi
    "1789012.34"  # coord_est (116-125)
    "   "     # spazi
    " 123.45"  # quota (128-135)
    "02"      # attend_plan (135-137)
    "03"      # attend_altim (137-139)
    "MARCIAPIEDE"  # descr_altim (139-149)
    "               "  # mono_info (149-164)
    "                "  # causale (164-180)
    " " * 57  # padding
    "1"       # has_monografia (237-238)
)


class TestTafParser:
    """Test per TafParser."""

    def test_parser_initialization(self):
        """Test inizializzazione parser."""
        parser = TafParser()
        assert parser.encoding == "latin-1"
        assert parser.errors == []
        assert parser.warnings == []

    def test_parse_coordinate_gauss_boaga_ovest(self):
        """Test rilevamento Gauss-Boaga Ovest."""
        parser = TafParser()

        sistema = parser._detect_coordinate_system(
            nord=4641234.567,
            est=1789012.34,
            provincia="RM"
        )

        assert sistema == SistemaCoordinate.GAUSS_BOAGA_OVEST

    def test_parse_coordinate_gauss_boaga_est(self):
        """Test rilevamento Gauss-Boaga Est."""
        parser = TafParser()

        sistema = parser._detect_coordinate_system(
            nord=4560000.0,
            est=2672000.0,
            provincia="BA"
        )

        assert sistema == SistemaCoordinate.GAUSS_BOAGA_EST

    def test_parse_coordinate_cassini(self):
        """Test rilevamento Cassini-Soldner."""
        parser = TafParser()

        sistema = parser._detect_coordinate_system(
            nord=12345.67,
            est=5432.10,
            provincia="RM"
        )

        assert sistema == SistemaCoordinate.CASSINI_SOLDNER

    def test_parse_foglio_normal(self):
        """Test parsing foglio normale."""
        parser = TafParser()

        assert parser._parse_foglio("0010") == "10"
        assert parser._parse_foglio("0001") == "1"
        assert parser._parse_foglio("0123") == "123"

    def test_parse_foglio_with_prefix(self):
        """Test parsing foglio con prefisso speciale."""
        parser = TafParser()

        assert parser._parse_foglio("1005") == "A05"
        assert parser._parse_foglio("1112") == "B12"

    def test_parse_coordinate_value(self):
        """Test parsing valore coordinata."""
        parser = TafParser()

        assert parser._parse_coordinate("4641234.567") == 4641234.567
        assert parser._parse_coordinate("  1234.56  ") == 1234.56
        assert parser._parse_coordinate("") == 0.0
        assert parser._parse_coordinate("invalid") == 0.0

    def test_parse_quota(self):
        """Test parsing quota."""
        parser = TafParser()

        assert parser._parse_quota("123.45") == 123.45
        assert parser._parse_quota("9999") == 9999.0  # Valore convenzionale
        assert parser._parse_quota("") == 9999.0
        assert parser._parse_quota("-100.5") == -100.5  # Quote negative possibili

    def test_parse_file_not_found(self):
        """Test file non trovato."""
        parser = TafParser()

        with pytest.raises(FileNotFoundError):
            list(parser.parse_file("/path/inesistente/file.TAF"))

    def test_parse_empty_lines_skipped(self):
        """Test che le righe vuote vengono saltate."""
        parser = TafParser()

        # Crea file temporaneo con righe vuote
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".TAF",
            delete=False,
            encoding="latin-1"
        ) as f:
            f.write("\n")
            f.write("    \n")
            f.write("short line\n")
            temp_path = f.name

        try:
            punti = list(parser.parse_file(temp_path))
            assert len(punti) == 0  # Nessun punto valido
        finally:
            Path(temp_path).unlink()


class TestPuntoFiduciale:
    """Test per il modello PuntoFiduciale."""

    def test_identificativo(self):
        """Test costruzione identificativo."""
        from pf_italia.models import PuntoFiduciale

        pf = PuntoFiduciale(
            provincia="RM",
            codice_comune="H501",
            foglio="010",
            allegato="0",
            numero="01",
        )

        assert pf.identificativo == "PF01/0100/H501"

    def test_identificativo_con_allegato(self):
        """Test identificativo con allegato."""
        from pf_italia.models import PuntoFiduciale

        pf = PuntoFiduciale(
            provincia="RM",
            codice_comune="H501",
            foglio="020",
            allegato="A",
            numero="15",
        )

        assert pf.identificativo == "PF15/020A/H501"

    def test_has_valid_coordinates(self):
        """Test verifica coordinate valide."""
        from pf_italia.models import PuntoFiduciale

        pf1 = PuntoFiduciale(
            provincia="RM",
            codice_comune="H501",
            coord_nord=4641234.0,
            coord_est=1789012.0,
        )
        assert pf1.has_valid_coordinates

        pf2 = PuntoFiduciale(
            provincia="RM",
            codice_comune="H501",
            coord_nord=0.0,
            coord_est=0.0,
        )
        assert not pf2.has_valid_coordinates

    def test_has_wgs84_coordinates(self):
        """Test verifica coordinate WGS84."""
        from pf_italia.models import PuntoFiduciale

        pf = PuntoFiduciale(
            provincia="RM",
            codice_comune="H501",
        )
        assert not pf.has_wgs84_coordinates

        pf.lat_wgs84 = 41.9028
        pf.lon_wgs84 = 12.4964
        assert pf.has_wgs84_coordinates

    def test_to_geojson_feature(self):
        """Test conversione a GeoJSON."""
        from pf_italia.models import PuntoFiduciale

        pf = PuntoFiduciale(
            provincia="RM",
            codice_comune="H501",
            foglio="010",
            numero="01",
            lat_wgs84=41.9028,
            lon_wgs84=12.4964,
        )

        feature = pf.to_geojson_feature()

        assert feature is not None
        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "Point"
        assert feature["geometry"]["coordinates"] == [12.4964, 41.9028]
        assert feature["properties"]["provincia"] == "RM"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
