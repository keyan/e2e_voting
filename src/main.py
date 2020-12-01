import argparse
import sys

from src import election


def parse_cmd_line(args):
    parser = argparse.ArgumentParser(description='Run simulated electronic elections')

    parser.add_argument(
        '-i', '--interactive',
        action='store_true',
        dest='interactive',
        default=False,
        help='start simulation in interactive mode, allowing user control of some election parameters like voting',
    )

    parser.add_argument(
        '-v', '--voters',
        action='store',
        dest='num_voters',
        default=5,
        type=int,
        help='number of voters to use, set randomly if not specified',
    )

    return parser.parse_args(args)


if __name__ == '__main__':
    parsed = parse_cmd_line(sys.argv[1:])
    if parsed.interactive:
        print('Interactive mode not implemented yet')
    else:
        election.Election(num_voters=parsed.num_voters).run()
