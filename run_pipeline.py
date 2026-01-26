#!/usr/bin/env python3
"""
Script principale per eseguire l'intera pipeline:
1. Download dei file TAF
2. Parsing e conversione coordinate
3. Importazione nel database
4. Esempio di query

Uso:
    python run_pipeline.py [--province RM MI] [--skip-download]
"""

import argparse
import logging
import sys
from pathlib import Path

# Aggiungi src al path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pf_italia import __version__
from pf_italia.downloader import TafDownloader, PROVINCE_ITALIANE
from pf_italia.taf_parser import TafParser
from pf_italia.coordinate_converter import CoordinateConverter
from pf_italia.database import PfDatabase
from pf_italia.query import query_pf, get_pf_geojson

# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_pipeline(
    province: list[str] | None = None,
    skip_download: bool = False,
    data_dir: str = "data",
):
    """
    Esegue l'intera pipeline di elaborazione.

    Args:
        province: Lista province da elaborare (None = tutte)
        skip_download: Se True, salta il download (usa file esistenti)
        data_dir: Directory base per i dati
    """
    data_path = Path(data_dir)
    taf_dir = data_path / "taf"
    db_path = data_path / "pf_italia.db"

    print("=" * 60)
    print(f"PF Italia v{__version__} - Pipeline Completa")
    print("=" * 60)
    print()

    # =========================================================================
    # FASE 1: Download TAF
    # =========================================================================
    if not skip_download:
        print("FASE 1: Download file TAF")
        print("-" * 40)

        downloader = TafDownloader(output_dir=taf_dir)

        if province:
            print(f"Province selezionate: {', '.join(province)}")
        else:
            print(f"Download tutte le {len(PROVINCE_ITALIANE)} province")

        stats = downloader.download_all(province=province)

        print(f"\nRisultati download:")
        print(f"  Scaricati: {stats['downloaded']}")
        print(f"  Saltati:   {stats['skipped']}")
        print(f"  Falliti:   {stats['failed']}")
        print()
    else:
        print("FASE 1: Download SALTATO (usando file esistenti)")
        print()

    # =========================================================================
    # FASE 2: Parsing e conversione
    # =========================================================================
    print("FASE 2: Parsing TAF e conversione coordinate")
    print("-" * 40)

    # Trova file TAF
    taf_files = sorted(taf_dir.glob("*.TAF")) + sorted(taf_dir.glob("*.taf"))

    if province:
        province_upper = [p.upper() for p in province]
        taf_files = [f for f in taf_files if f.stem.upper() in province_upper]

    if not taf_files:
        print("ERRORE: Nessun file TAF trovato!")
        print(f"Directory: {taf_dir}")
        return False

    print(f"File TAF da elaborare: {len(taf_files)}")

    # Inizializza componenti
    parser = TafParser()
    converter = CoordinateConverter()

    print(f"Origini catastali caricate: {len(converter.origini_disponibili)}")
    print()

    # =========================================================================
    # FASE 3: Import nel database
    # =========================================================================
    print("FASE 3: Import nel database")
    print("-" * 40)

    db = PfDatabase(db_path)
    db.init_schema()

    total_parsed = 0
    total_converted = 0
    total_inserted = 0

    for taf_file in taf_files:
        provincia = taf_file.stem.upper()
        logger.info(f"Elaborazione {provincia}...")

        # Parse
        punti = []
        for pf in parser.parse_file(taf_file, provincia=provincia):
            punti.append(pf)

        # Converti coordinate
        converted = 0
        for pf in punti:
            result = converter.convert_to_wgs84(pf)
            if result:
                pf.lat_wgs84, pf.lon_wgs84 = result
                converted += 1

        # Insert
        inserted, errors = db.insert_punti(iter(punti))

        logger.info(
            f"  {provincia}: {len(punti)} parsati, "
            f"{converted} convertiti, {inserted} inseriti"
        )

        total_parsed += len(punti)
        total_converted += converted
        total_inserted += inserted

    print()
    print(f"Totali:")
    print(f"  Punti parsati:    {total_parsed:,}")
    print(f"  Convertiti WGS84: {total_converted:,}")
    print(f"  Inseriti nel DB:  {total_inserted:,}")
    print()

    # =========================================================================
    # FASE 4: Statistiche e test query
    # =========================================================================
    print("FASE 4: Statistiche e query di test")
    print("-" * 40)

    stats = db.get_stats()
    print(f"Database: {db_path}")
    print(f"  Totale PF: {stats['totale_pf']:,}")
    print(f"  Con WGS84: {stats['pf_con_wgs84']:,}")

    if stats.get("per_sistema"):
        print("\n  Per sistema coordinate:")
        for sistema, count in sorted(stats["per_sistema"].items(), key=lambda x: -x[1]):
            pct = count / stats['totale_pf'] * 100 if stats['totale_pf'] > 0 else 0
            print(f"    {sistema}: {count:,} ({pct:.1f}%)")

    db.close()

    # Query di esempio
    print()
    print("Query di esempio (Roma, Colosseo):")
    risultati = query_pf(41.8902, 12.4922, buffer_m=2000, db_path=db_path, limit=5)

    if risultati:
        for pf in risultati:
            print(
                f"  {pf['identificativo']}: "
                f"{pf.get('distanza_m', 0):.0f}m"
            )
    else:
        print("  Nessun punto trovato nell'area")

    print()
    print("=" * 60)
    print("Pipeline completata!")
    print("=" * 60)

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Esegue la pipeline completa per i Punti Fiduciali"
    )
    parser.add_argument(
        "-p", "--province",
        nargs="+",
        help="Province da elaborare (es. RM MI TO). Default: tutte"
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Salta il download (usa file TAF esistenti)"
    )
    parser.add_argument(
        "-d", "--data-dir",
        default="data",
        help="Directory per i dati (default: data)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Output dettagliato"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    success = run_pipeline(
        province=args.province,
        skip_download=args.skip_download,
        data_dir=args.data_dir,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
