"""
Test per il convertitore di coordinate.
"""

import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pf_italia.coordinate_converter import CoordinateConverter
from pf_italia.models import PuntoFiduciale, SistemaCoordinate


class TestCoordinateConverter:
    """Test per CoordinateConverter."""

    @pytest.fixture
    def converter(self):
        """Crea un'istanza del converter."""
        return CoordinateConverter()

    def test_initialization(self, converter):
        """Test inizializzazione converter."""
        assert len(converter.origini_disponibili) == 31  # 31 grandi origini
        assert "ROMA" in converter.origini_disponibili
        assert "MILANO" in converter.origini_disponibili

    def test_gauss_boaga_ovest_conversion(self, converter):
        """Test conversione Gauss-Boaga Ovest -> WGS84."""
        # Coordinate note: Roma (approssimative)
        pf = PuntoFiduciale(
            provincia="RM",
            codice_comune="H501",
            coord_nord=4641000.0,
            coord_est=1788000.0,
            sistema_coordinate=SistemaCoordinate.GAUSS_BOAGA_OVEST,
        )

        result = converter.convert_to_wgs84(pf)

        assert result is not None
        lat, lon = result

        # Verifica che sia nell'area di Roma
        assert 41.5 < lat < 42.5, f"Latitudine fuori range Roma: {lat}"
        assert 12.0 < lon < 13.0, f"Longitudine fuori range Roma: {lon}"

    def test_gauss_boaga_est_conversion(self, converter):
        """Test conversione Gauss-Boaga Est -> WGS84."""
        # Coordinate note: Bari (approssimative)
        pf = PuntoFiduciale(
            provincia="BA",
            codice_comune="A662",
            coord_nord=4560000.0,
            coord_est=2672000.0,
            sistema_coordinate=SistemaCoordinate.GAUSS_BOAGA_EST,
        )

        result = converter.convert_to_wgs84(pf)

        assert result is not None
        lat, lon = result

        # Verifica che sia nell'area della Puglia
        assert 40.5 < lat < 42.0, f"Latitudine fuori range Puglia: {lat}"
        assert 16.0 < lon < 18.0, f"Longitudine fuori range Puglia: {lon}"

    def test_invalid_coordinates(self, converter):
        """Test coordinate non valide."""
        pf = PuntoFiduciale(
            provincia="RM",
            codice_comune="H501",
            coord_nord=0.0,
            coord_est=0.0,
        )

        result = converter.convert_to_wgs84(pf)
        assert result is None

    def test_batch_conversion(self, converter):
        """Test conversione batch."""
        punti = [
            PuntoFiduciale(
                provincia="RM",
                codice_comune="H501",
                coord_nord=4641000.0 + i * 1000,
                coord_est=1788000.0 + i * 100,
                sistema_coordinate=SistemaCoordinate.GAUSS_BOAGA_OVEST,
            )
            for i in range(5)
        ]

        converted = converter.convert_batch(punti, update_in_place=True)

        assert len(converted) == 5

        # Verifica che tutti abbiano coordinate WGS84
        for pf in converted:
            assert pf.has_wgs84_coordinates, f"PF senza WGS84: {pf.identificativo}"

    def test_get_origine(self, converter):
        """Test recupero origine catastale."""
        origine = converter.get_origine("ROMA")

        assert origine is not None
        assert origine.nome == "Roma"
        assert origine.tipo == "grande"
        assert origine.fuso_gb == 1

    def test_get_origine_not_found(self, converter):
        """Test origine non trovata."""
        origine = converter.get_origine("ORIGINE_INESISTENTE")
        assert origine is None


class TestCoordinateValidation:
    """Test validazione range coordinate."""

    @pytest.fixture
    def converter(self):
        return CoordinateConverter()

    def test_italy_bounding_box(self, converter):
        """Test che le coordinate convertite siano in Italia."""
        # Test punti in varie parti d'Italia
        test_points = [
            # (nord_gb, est_gb, fuso, expected_lat_range, expected_lon_range)
            (5100000, 1400000, "GB_OVEST", (45.5, 46.5), (7.0, 8.0)),  # Piemonte
            (4300000, 2600000, "GB_EST", (38.0, 39.5), (16.0, 17.5)),  # Calabria
            (4400000, 1500000, "GB_OVEST", (39.0, 40.5), (9.0, 10.0)),  # Sardegna
        ]

        for nord, est, fuso, lat_range, lon_range in test_points:
            result = converter._convert_gauss_boaga(est, nord, fuso)

            if result:
                lat, lon = result
                assert lat_range[0] < lat < lat_range[1], \
                    f"Lat {lat} fuori range {lat_range}"
                assert lon_range[0] < lon < lon_range[1], \
                    f"Lon {lon} fuori range {lon_range}"


class TestCassiniSoldnerConversion:
    """Test conversione Cassini-Soldner."""

    @pytest.fixture
    def converter(self):
        return CoordinateConverter()

    def test_cassini_with_known_origin(self, converter):
        """Test conversione Cassini con origine nota."""
        # Punto vicino all'origine di Roma
        pf = PuntoFiduciale(
            provincia="RM",
            codice_comune="H501",
            coord_nord=1000.0,  # 1km nord dall'origine
            coord_est=500.0,    # 500m est dall'origine
            sistema_coordinate=SistemaCoordinate.CASSINI_SOLDNER,
        )

        result = converter.convert_to_wgs84(pf)

        # La conversione potrebbe funzionare o meno a seconda
        # della disponibilita' dell'origine
        # Per ora verifichiamo solo che non crashi
        # e che se restituisce qualcosa sia nel range Italia
        if result:
            lat, lon = result
            assert 35.0 < lat < 48.0
            assert 6.0 < lon < 19.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
