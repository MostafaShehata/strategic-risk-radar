import argparse

from .runner import EnrichmentRunner


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    runner = EnrichmentRunner()
    if args.once:
        runner.run_once()
    else:
        runner.run_forever()


if __name__ == "__main__":
    main()
