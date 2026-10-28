"""Explicit offline run: python -m app.sync_simulator --run. No DB/network use."""
import argparse
from app.simulation.report import create_report,write_report

def main(argv=None):
    parser=argparse.ArgumentParser(description='V2 isolated synthetic synchronization simulator (no devices/DB writes)')
    parser.add_argument('--run',action='store_true',help='Create a new isolated five-router run artifact; preserve previous runs')
    args=parser.parse_args(argv)
    if not args.run:parser.print_help();return 0
    try:
        id=write_report(create_report());print('SIMULATOR RECORDED:',id,'(synthetic only; no browser claim)');return 0
    except (ValueError,OSError):print('SIMULATOR BLOCKED: isolated report could not be published; existing business data unchanged.');return 1
if __name__=='__main__':raise SystemExit(main())
