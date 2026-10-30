import argparse
from pathlib import Path
from .report import demo, read_gsw, curve_report
from .history import historical_contracts


def main():
    p = argparse.ArgumentParser(description="Policy calendars and curve risk; no broker orders")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--demo", action="store_true")
    group.add_argument("--gsw", type=Path, help="Official feds200628.csv, locally downloaded")
    group.add_argument("--futures", type=Path, help="Private licensed input directory; outputs must stay private")
    p.add_argument("--output", type=Path, default=Path("output"))
    args = p.parse_args()
    if args.demo:
        demo(args.output)
    elif args.gsw:
        frame, rejected, fingerprint = read_gsw(args.gsw)
        args.output.mkdir(parents=True, exist_ok=True)
        rejected.to_csv(args.output/"excluded.csv", index=False)
        print(curve_report(frame, args.output, fingerprint).to_string(index=False))
    else:
        print(historical_contracts(args.futures, args.output))


if __name__ == "__main__":
    main()
