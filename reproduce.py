#!/usr/bin/env python3
"""Run the self-contained, offline CURE audit."""
from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
from cure_audit.analysis import analyze, verify_manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'results')
    parser.add_argument('--no-figures', action='store_true', help='Use only the Python standard library')
    parser.add_argument('--verify-only', action='store_true', help='Verify published input/source file hashes')
    args = parser.parse_args()
    if not __debug__:
        parser.error("Run without -O: scientific consistency checks must stay enabled")
    destination = args.output.resolve()
    if destination == ROOT or any(destination == ROOT/name or ROOT/name in destination.parents for name in ("data", "src", "sql", "expected", "docs", "tests")):
        parser.error("Choose a separate results directory")
    if args.verify_only:
        print('Integrity verified:', verify_manifest(ROOT), 'files')
        return
    result = analyze(ROOT, args.output.resolve())
    if not args.no_figures:
        from cure_audit.figures import generate
        from cure_audit.paper_figures import generate_paper_figures
        generate(ROOT, args.output.resolve())
        generate_paper_figures(ROOT, args.output.resolve())
    print('Verified:', result['primary_episodes'], 'episodes;', result['expected_numeric_cells_checked'], 'comparison cells')
    print('Results:', args.output.resolve())


if __name__ == '__main__':
    main()
