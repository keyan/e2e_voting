import argparse
import sys

from src import election


def parse_cmd_line(args):
    parser = argparse.ArgumentParser(description='Run simulated electronic elections')

    parser.add_argument(
        '-v', '--voters',
        action='store',
        dest='num_voters',
        default=999,
        type=int,
        help='number of voters to use, set randomly if not specified',
    )

    return parser.parse_args(args)


if __name__ == '__main__':
    parsed = parse_cmd_line(sys.argv[1:])
    election.Election(num_voters=parsed.num_voters).run()
