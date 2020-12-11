# e2e_voting

A limited implementation of Rabin and Rivest end-to-end verifiable electronic voting as described in [their paper](https://people.csail.mit.edu/rivest/pubs/RR14b.pdf).

The high level system architecture looks like:

<img src="https://raw.githubusercontent.com/keyan/e2e_voting/master/paper/figures/arch_diagram.png" alt="arch" width=80%/>

## Requirements

Install necessary packages in a virtualenv:
```
pip install -r requirements.txt
```

## Usage

```
⫸ python3 -m src.main  --help
usage: main.py [-h] [-v NUM_VOTERS]

Run simulated electronic elections

optional arguments:
  -h, --help            show this help message and exit
  -v NUM_VOTERS, --voters NUM_VOTERS
                        number of voters to use, set randomly if not specified
```

For example:
```
# Automated simulation mode
make run
```
