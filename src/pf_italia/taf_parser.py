"""
Parser per i file TAF (Tabella Attuale Punti Fiduciali).

Il formato TAF e' un file ASCII a larghezza fissa con un record per ogni punto fiduciale.
La struttura del tracciato e' stata derivata dall'analisi del plugin topog4qgis e dalla
documentazione dell'Agenzia delle Entrate.
"""

import re
import logging
from pathlib import Path
from typing import Iterator, Optional

from .models import (
    PuntoFiduciale,
    SistemaCoordinate,
    AttendibilitaPlanimetrica,
    AttendibilitaAltimetrica,
)

logger = logging.getLogger(__name__)


# Tracciato record TAF - posizioni dei campi (0-indexed)
# Derivato dall'analisi di topog4qgis e documentazione AdE
TAF_FIELDS = {
    "cod_comune": (0, 4),           # Codice catastale comune (4 char)
    "sezione": (4, 5),              # Sezione censuaria (1 char, spazio se assente)
    "foglio": (6, 10),              # Foglio catastale (4 char, ultimi 3 significativi)
    "allegato": (11, 12),           # Allegato foglio (1 char, spazio = "0")
    "numero_pf": (15, 17),          # Numero punto fiduciale (2 char)
    "descr_plan": (30, 100),        # Descrizione riferimento planimetrico (70 char)
    "coord_nord": (102, 114),       # Coordinata Nord/X/Y (12 char)
    "coord_est": (116, 125),        # Coordinata Est/Y/X (9 char)
    "quota": (128, 135),            # Quota s.l.m. (7 char)
    "attend_plan": (135, 137),      # Attendibilita planimetrica (2 char)
    "attend_altim": (137, 139),     # Attendibilita altimetrica (2 char)
    "descr_altim": (139, 149),      # Descrizione riferimento altimetrico (10 char)
    "monografia_info": (149, 164),  # Informazioni monografia (15 char)
    "causale": (164, 180),          # Causale aggiornamento (16 char)
    "has_monografia": (237, 238),   # Flag monografia: 0=no, altro=si (1 char)
}


class TafParser:
    """
    Parser per file TAF (Tabella Attuale Punti Fiduciali).

    Esempio di utilizzo:
        parser = TafParser()
        for pf in parser.parse_file("RM.TAF", provincia="RM"):
            print(pf.identificativo, pf.coord_nord, pf.coord_est)
    """

    def __init__(self, encoding: str = "latin-1"):
        """
        Inizializza il parser.

        Args:
            encoding: Encoding del file TAF (default: latin-1 per caratteri italiani)
        """
        self.encoding = encoding
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def parse_file(
        self,
        filepath: str | Path,
        provincia: str = "",
        skip_invalid: bool = True
    ) -> Iterator[PuntoFiduciale]:
        """
        Parsa un file TAF e restituisce un iteratore di PuntoFiduciale.

        Args:
            filepath: Percorso al file TAF
            provincia: Sigla provincia (opzionale, derivata dal nome file se non specificata)
            skip_invalid: Se True, salta i record con errori invece di sollevare eccezione

        Yields:
            PuntoFiduciale per ogni record valido nel file
        """
        filepath = Path(filepath)
        self.errors = []
        self.warnings = []

        if not filepath.exists():
            raise FileNotFoundError(f"File TAF non trovato: {filepath}")

        # Deriva provincia dal nome file se non specificata
        if not provincia:
            provincia = filepath.stem.upper()[:2]

        logger.info(f"Parsing file TAF: {filepath} (provincia: {provincia})")

        line_num = 0
        parsed_count = 0
        error_count = 0

        with open(filepath, "r", encoding=self.encoding, errors="replace") as f:
            for line in f:
                line_num += 1

                # Salta righe vuote o troppo corte
                if len(line.strip()) < 100:
                    continue

                try:
                    pf = self._parse_line(line, provincia, line_num)
                    if pf and pf.has_valid_coordinates:
                        parsed_count += 1
                        yield pf
                    elif pf:
                        self.warnings.append(
                            f"Linea {line_num}: PF {pf.identificativo} senza coordinate valide"
                        )
                except Exception as e:
                    error_count += 1
                    error_msg = f"Linea {line_num}: {str(e)}"
                    self.errors.append(error_msg)
                    if not skip_invalid:
                        raise ValueError(error_msg) from e

        logger.info(
            f"Parsing completato: {parsed_count} PF validi, "
            f"{error_count} errori, {len(self.warnings)} warning"
        )

    def _parse_line(self, line: str, provincia: str, line_num: int) -> Optional[PuntoFiduciale]:
        """
        Parsa una singola linea del file TAF.

        Args:
            line: Linea del file
            provincia: Sigla provincia
            line_num: Numero linea (per messaggi errore)

        Returns:
            PuntoFiduciale o None se la linea non e' valida
        """
        # Estrai campi usando le posizioni definite
        def get_field(name: str) -> str:
            start, end = TAF_FIELDS[name]
            if end > len(line):
                return ""
            return line[start:end].strip()

        # Campi identificativi
        cod_comune = get_field("cod_comune")
        if not cod_comune:
            return None

        sezione = get_field("sezione")
        foglio_raw = get_field("foglio")
        allegato = get_field("allegato") or "0"
        numero_pf = get_field("numero_pf")

        # Gestione foglio con codice speciale (10, 11 -> A, B)
        foglio = self._parse_foglio(foglio_raw)

        # Coordinate - usa regex per trovare i valori numerici grandi
        # Pattern: cerca due numeri decimali consecutivi (Nord ed Est)
        coord_nord = 0.0
        coord_est = 0.0
        quota = 9999.0

        # Cerca coordinate con regex (più robusto delle posizioni fisse)
        # Pattern per coordinate Gauss-Boaga: numeri > 1.000.000
        coord_match = re.search(
            r'(\d{6,7}(?:\.\d+)?)\s+(\d{6,7}(?:\.\d+)?)\s+(\d{1,4}(?:\.\d+)?)',
            line
        )
        if coord_match:
            coord_nord = float(coord_match.group(1))
            coord_est = float(coord_match.group(2))
            quota = float(coord_match.group(3))
        else:
            # Fallback: prova con posizioni fisse
            coord_nord = self._parse_coordinate(get_field("coord_nord"))
            coord_est = self._parse_coordinate(get_field("coord_est"))
            quota = self._parse_quota(get_field("quota"))

        if coord_nord == 0.0 and coord_est == 0.0:
            return None

        # Attendibilita - cerca pattern 4 cifre dopo quota
        attend_plan = AttendibilitaPlanimetrica.NON_DISPONIBILE
        attend_altim = AttendibilitaAltimetrica.NON_DISPONIBILE

        attend_match = re.search(r'\d+\.\d+\s*(\d{2})(\d{2})', line)
        if attend_match:
            attend_plan = self._parse_attendibilita_plan(attend_match.group(1))
            attend_altim = self._parse_attendibilita_altim(attend_match.group(2))

        # Descrizioni
        descr_plan = get_field("descr_plan")
        descr_altim = get_field("descr_altim")

        # Monografia - ultimo carattere della riga
        has_monografia = False
        if len(line.strip()) > 0:
            last_char = line.strip()[-1]
            has_monografia = last_char != "0" and last_char.isdigit()

        # Causale aggiornamento
        causale = get_field("causale") or None

        # Determina sistema di coordinate
        sistema = self._detect_coordinate_system(coord_nord, coord_est, provincia)

        return PuntoFiduciale(
            provincia=provincia,
            codice_comune=cod_comune,
            sezione=sezione,
            foglio=foglio,
            allegato=allegato,
            numero=numero_pf,
            coord_nord=coord_nord,
            coord_est=coord_est,
            quota=quota,
            sistema_coordinate=sistema,
            attendibilita_plan=attend_plan,
            attendibilita_altim=attend_altim,
            descrizione_plan=descr_plan,
            descrizione_altim=descr_altim,
            ha_monografia=has_monografia,
            data_monografia=None,
            causale_aggiornamento=causale,
        )

    def _parse_foglio(self, foglio_raw: str) -> str:
        """
        Parsa il numero foglio, gestendo i codici speciali.

        Nel TAF i fogli con allegato possono avere codici speciali:
        - 10 -> prefisso A
        - 11 -> prefisso B
        """
        if not foglio_raw:
            return "000"

        # Rimuovi eventuali caratteri non numerici iniziali
        foglio_clean = foglio_raw.lstrip("0") or "0"

        # Gestione codici speciali (ultimi 2 caratteri)
        if len(foglio_raw) >= 2:
            prefix_code = foglio_raw[:2]
            if prefix_code == "10":
                return "A" + foglio_raw[2:].zfill(2)
            elif prefix_code == "11":
                return "B" + foglio_raw[2:].zfill(2)

        return foglio_clean.zfill(3)

    def _parse_coordinate(self, value: str) -> float:
        """Parsa un valore coordinata."""
        if not value:
            return 0.0
        try:
            # Rimuovi spazi e converti
            clean = value.replace(" ", "").replace(",", ".")
            return float(clean)
        except ValueError:
            return 0.0

    def _parse_quota(self, value: str) -> float:
        """Parsa la quota, restituendo 9999.0 se non valida."""
        if not value:
            return 9999.0
        try:
            clean = value.replace(" ", "").replace(",", ".")
            q = float(clean)
            # Valori negativi o > 5000 sono sospetti per l'Italia
            if q < -500 or q > 5000:
                return 9999.0
            return q
        except ValueError:
            return 9999.0

    def _parse_attendibilita_plan(self, value: str) -> AttendibilitaPlanimetrica:
        """Parsa il codice attendibilita planimetrica."""
        mapping = {
            "01": AttendibilitaPlanimetrica.OTTIMA,
            "02": AttendibilitaPlanimetrica.BUONA,
            "03": AttendibilitaPlanimetrica.SUFFICIENTE,
            "04": AttendibilitaPlanimetrica.SCARSA,
            "1": AttendibilitaPlanimetrica.OTTIMA,
            "2": AttendibilitaPlanimetrica.BUONA,
            "3": AttendibilitaPlanimetrica.SUFFICIENTE,
            "4": AttendibilitaPlanimetrica.SCARSA,
        }
        return mapping.get(value, AttendibilitaPlanimetrica.NON_DISPONIBILE)

    def _parse_attendibilita_altim(self, value: str) -> AttendibilitaAltimetrica:
        """Parsa il codice attendibilita altimetrica."""
        mapping = {
            "01": AttendibilitaAltimetrica.OTTIMA,
            "02": AttendibilitaAltimetrica.BUONA,
            "03": AttendibilitaAltimetrica.SUFFICIENTE,
            "04": AttendibilitaAltimetrica.SCARSA,
            "1": AttendibilitaAltimetrica.OTTIMA,
            "2": AttendibilitaAltimetrica.BUONA,
            "3": AttendibilitaAltimetrica.SUFFICIENTE,
            "4": AttendibilitaAltimetrica.SCARSA,
        }
        return mapping.get(value, AttendibilitaAltimetrica.NON_DISPONIBILE)

    def _detect_coordinate_system(
        self,
        nord: float,
        est: float,
        provincia: str
    ) -> SistemaCoordinate:
        """
        Rileva automaticamente il sistema di coordinate dai valori.

        Logica:
        - Gauss-Boaga Ovest (EPSG:3003): Est tra 1.400.000 e 1.800.000
        - Gauss-Boaga Est (EPSG:3004): Est tra 2.300.000 e 2.700.000
        - Cassini-Soldner: valori piu' piccoli, tipicamente < 100.000
        - Alcune province usano ancora Cassini-Soldner o Sanson-Flamsteed
        """
        # Province note per Sanson-Flamsteed
        province_sf = {"MO", "RE", "MS", "LU", "SP"}  # Modena, Reggio E., Massa, Lucca, La Spezia

        # Gauss-Boaga in base al valore Est
        if 1_300_000 < est < 1_900_000:
            return SistemaCoordinate.GAUSS_BOAGA_OVEST
        elif 2_200_000 < est < 2_800_000:
            return SistemaCoordinate.GAUSS_BOAGA_EST

        # UTM WGS84 (coordinate piu' recenti)
        if 100_000 < est < 800_000:
            # UTM ha Est tipicamente 200000-800000
            if nord > 4_000_000:  # Conferma Nord > 4M per Italia
                if est < 500_000:
                    return SistemaCoordinate.UTM_WGS84_32N
                else:
                    return SistemaCoordinate.UTM_WGS84_33N

        # Cassini-Soldner o Sanson-Flamsteed (valori locali)
        if provincia in province_sf:
            return SistemaCoordinate.SANSON_FLAMSTEED

        # Default: Cassini-Soldner per valori piccoli
        if abs(nord) < 200_000 and abs(est) < 200_000:
            return SistemaCoordinate.CASSINI_SOLDNER

        return SistemaCoordinate.UNKNOWN


def parse_taf_directory(
    directory: str | Path,
    recursive: bool = False
) -> Iterator[tuple[str, PuntoFiduciale]]:
    """
    Parsa tutti i file TAF in una directory.

    Args:
        directory: Directory contenente i file TAF
        recursive: Se True, cerca anche nelle sottodirectory

    Yields:
        Tuple (nome_file, PuntoFiduciale) per ogni punto valido
    """
    directory = Path(directory)
    parser = TafParser()

    pattern = "**/*.TAF" if recursive else "*.TAF"
    taf_files = list(directory.glob(pattern)) + list(directory.glob(pattern.lower()))

    for taf_file in sorted(set(taf_files)):
        logger.info(f"Elaborazione: {taf_file.name}")
        try:
            for pf in parser.parse_file(taf_file):
                yield (taf_file.name, pf)
        except Exception as e:
            logger.error(f"Errore parsing {taf_file.name}: {e}")
