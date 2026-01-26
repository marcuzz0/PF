"""
CLI (Command Line Interface) per PF Italia.

Comandi disponibili:
- pf-download: Scarica i file TAF
- pf-import: Importa TAF nel database con conversione WGS84
- pf-query: Cerca punti fiduciali per coordinata
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from . import __version__


def setup_logging(verbose: bool = False):
    """Configura il logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def download_all():
    """Comando: scarica tutti i file TAF."""
    parser = argparse.ArgumentParser(
        description="Scarica i file TAF (Tabella Attuale Punti Fiduciali) dall'Agenzia delle Entrate"
    )
    parser.add_argument(
        "-o", "--output",
        default="data/taf",
        help="Directory output per i file TAF (default: data/taf)"
    )
    parser.add_argument(
        "-p", "--province",
        nargs="+",
        help="Scarica solo le province specificate (es. RM MI TO)"
    )
    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Riscarica anche file esistenti"
    )
    parser.add_argument(
        "--no-altervista",
        action="store_true",
        help="Non usare fiduciali.altervista.org come fonte"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Output dettagliato"
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    from .downloader import TafDownloader

    print(f"PF Italia v{__version__} - Download TAF")
    print(f"Output: {args.output}")
    print()

    downloader = TafDownloader(
        output_dir=args.output,
        use_altervista=not args.no_altervista,
    )

    stats = downloader.download_all(
        province=args.province,
        force=args.force,
    )

    print()
    print(f"Download completato:")
    print(f"  Scaricati: {stats['downloaded']}")
    print(f"  Saltati:   {stats['skipped']}")
    print(f"  Falliti:   {stats['failed']}")

    # Mostra province mancanti
    missing = downloader.get_missing_provinces()
    if missing:
        print(f"\nProvince mancanti ({len(missing)}): {', '.join(missing)}")


def import_taf():
    """Comando: importa TAF nel database con conversione WGS84."""
    parser = argparse.ArgumentParser(
        description="Importa file TAF nel database con conversione in WGS84"
    )
    parser.add_argument(
        "-i", "--input",
        default="data/taf",
        help="Directory con i file TAF (default: data/taf)"
    )
    parser.add_argument(
        "-d", "--database",
        default="data/pf_italia.db",
        help="Percorso database output (default: data/pf_italia.db)"
    )
    parser.add_argument(
        "-p", "--province",
        nargs="+",
        help="Importa solo le province specificate"
    )
    parser.add_argument(
        "--origini",
        help="File JSON con origini catastali aggiuntive"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Output dettagliato"
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    from .taf_parser import TafParser
    from .coordinate_converter import CoordinateConverter
    from .database import PfDatabase

    print(f"PF Italia v{__version__} - Import TAF")
    print(f"Input:    {args.input}")
    print(f"Database: {args.database}")
    print()

    # Inizializza componenti
    parser_taf = TafParser()
    converter = CoordinateConverter(origini_file=args.origini)
    db = PfDatabase(args.database)
    db.init_schema()

    # Trova file TAF
    input_dir = Path(args.input)
    taf_files = sorted(input_dir.glob("*.TAF")) + sorted(input_dir.glob("*.taf"))

    if args.province:
        province_upper = [p.upper() for p in args.province]
        taf_files = [f for f in taf_files if f.stem.upper() in province_upper]

    if not taf_files:
        print("Nessun file TAF trovato!")
        sys.exit(1)

    print(f"File TAF trovati: {len(taf_files)}")

    total_inserted = 0
    total_converted = 0
    total_errors = 0

    for taf_file in taf_files:
        provincia = taf_file.stem.upper()
        print(f"\nElaborazione {provincia}...")

        # Parse
        punti = list(parser_taf.parse_file(taf_file, provincia=provincia))
        print(f"  Punti parsati: {len(punti)}")

        # Converti
        converted = 0
        for pf in punti:
            result = converter.convert_to_wgs84(pf)
            if result:
                pf.lat_wgs84, pf.lon_wgs84 = result
                converted += 1

        print(f"  Convertiti in WGS84: {converted}")
        total_converted += converted

        # Inserisci nel database
        inserted, errors = db.insert_punti(iter(punti))
        print(f"  Inseriti nel DB: {inserted}")
        total_inserted += inserted
        total_errors += errors

    db.close()

    print()
    print("=" * 50)
    print(f"Totale punti inseriti:   {total_inserted}")
    print(f"Totale convertiti WGS84: {total_converted}")
    print(f"Totale errori:           {total_errors}")

    # Statistiche finali
    print()
    print("Statistiche database:")
    db = PfDatabase(args.database)
    stats = db.get_stats()
    db.close()

    print(f"  Punti totali:    {stats['totale_pf']}")
    print(f"  Con WGS84:       {stats['pf_con_wgs84']}")
    if stats.get("per_sistema"):
        print("  Per sistema coordinate:")
        for sistema, count in stats["per_sistema"].items():
            print(f"    {sistema}: {count}")


def query_pf():
    """Comando: cerca punti fiduciali per coordinata."""
    parser = argparse.ArgumentParser(
        description="Cerca punti fiduciali per coordinata WGS84"
    )
    parser.add_argument(
        "lat",
        type=float,
        help="Latitudine WGS84"
    )
    parser.add_argument(
        "lon",
        type=float,
        help="Longitudine WGS84"
    )
    parser.add_argument(
        "-b", "--buffer",
        type=float,
        default=1000,
        help="Raggio di ricerca in metri (default: 1000)"
    )
    parser.add_argument(
        "-d", "--database",
        default="data/pf_italia.db",
        help="Percorso database (default: data/pf_italia.db)"
    )
    parser.add_argument(
        "-n", "--limit",
        type=int,
        default=20,
        help="Numero massimo risultati (default: 20)"
    )
    parser.add_argument(
        "-o", "--output",
        help="File output GeoJSON (opzionale)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in formato JSON"
    )

    args = parser.parse_args()

    from .query import query_pf as do_query, get_pf_geojson

    # Esegui query
    if args.output or args.json:
        # Output GeoJSON
        result = get_pf_geojson(
            args.lat, args.lon,
            buffer_m=args.buffer,
            db_path=args.database,
            limit=args.limit,
        )

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"Risultati salvati in: {args.output}")
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        # Output tabellare
        risultati = do_query(
            args.lat, args.lon,
            buffer_m=args.buffer,
            db_path=args.database,
            limit=args.limit,
        )

        print(f"Ricerca: lat={args.lat}, lon={args.lon}, buffer={args.buffer}m")
        print(f"Trovati: {len(risultati)} punti fiduciali")
        print()

        if risultati:
            print(f"{'ID':<25} {'Dist(m)':<8} {'Prov':<4} {'Foglio':<6} {'Quota':<8} {'Mono':<4}")
            print("-" * 60)

            for pf in risultati:
                dist = pf.get("distanza_m", 0)
                quota = pf.get("quota")
                quota_str = f"{quota:.1f}" if quota else "-"
                mono = "Si" if pf.get("ha_monografia") else "No"

                print(
                    f"{pf['identificativo']:<25} "
                    f"{dist:<8.1f} "
                    f"{pf.get('provincia', ''):<4} "
                    f"{pf.get('foglio', ''):<6} "
                    f"{quota_str:<8} "
                    f"{mono:<4}"
                )


def main():
    """Entry point principale."""
    parser = argparse.ArgumentParser(
        description="PF Italia - Gestione Punti Fiduciali Catastali",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Comandi disponibili:
  download    Scarica i file TAF dall'Agenzia delle Entrate
  import      Importa TAF nel database con conversione WGS84
  query       Cerca punti fiduciali per coordinata

Esempio di utilizzo:
  python -m pf_italia download -p RM MI
  python -m pf_italia import
  python -m pf_italia query 41.9028 12.4964 -b 500
        """
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"PF Italia v{__version__}"
    )
    parser.add_argument(
        "command",
        choices=["download", "import", "query", "stats"],
        help="Comando da eseguire"
    )

    # Parse solo il primo argomento
    args, remaining = parser.parse_known_args()

    # Redireziona al comando appropriato
    sys.argv = [f"pf-{args.command}"] + remaining

    if args.command == "download":
        download_all()
    elif args.command == "import":
        import_taf()
    elif args.command == "query":
        query_pf()
    elif args.command == "stats":
        show_stats()


def show_stats():
    """Mostra statistiche del database."""
    parser = argparse.ArgumentParser(description="Mostra statistiche database")
    parser.add_argument(
        "-d", "--database",
        default="data/pf_italia.db",
        help="Percorso database"
    )
    args = parser.parse_args()

    from .query import get_statistics

    stats = get_statistics(args.database)

    print(f"Statistiche database: {args.database}")
    print()
    print(f"Totale punti fiduciali: {stats.get('totale_pf', 0):,}")
    print(f"Con coordinate WGS84:   {stats.get('pf_con_wgs84', 0):,}")
    print()

    if stats.get("per_provincia"):
        print("Per provincia (top 10):")
        sorted_prov = sorted(
            stats["per_provincia"].items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        for prov, count in sorted_prov:
            print(f"  {prov}: {count:,}")

    if stats.get("per_sistema"):
        print("\nPer sistema coordinate:")
        for sistema, count in stats["per_sistema"].items():
            print(f"  {sistema}: {count:,}")


if __name__ == "__main__":
    main()
