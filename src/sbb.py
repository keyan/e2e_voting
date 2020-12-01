import json
from typing import Dict, List

FILENAME = 'sbb.txt'

# Define SBB headings used to later parse the SBB during proof.
BALLOT_RECEIPTS = 'ballot_receipts'
COMMITMENTS = 'commitments'
VOTE_LIST = 'vote_list'
END_SECTION = 'end_section'


class SBBContents:
    """
    Container type used for simplifying data access to the SBB.

    After parsing the SBB, data is loaded into an instance of
    SBBContents for consumers to access.
    """
    def __init__(self):
        # Maps bids to receipt hashes.
        self.ballot_receipts: Dict[int, str] = {}

    def get_bid_receipt(self, bid: int) -> str:
        """
        Returns the ballot receipt for the provided bid.
        """
        return self.ballot_receipts[bid]


class SBB:
    """
    Implements an interface for the Secure Bulletin Board (SBB).
    """
    def __init__(self):
        self._ballot_receipts: List[str] = []
        self._svr_commitments: List[str] = []
        self._db: file = open(FILENAME, 'w')

    def close(self) -> None:
        self._db.close()

    def add_ballot_receipt(self, bid: int, receipt_str: str) -> None:
        """
        Add a single ballot to local receipt list, these are posted in bulk later.
        """
        self._ballot_receipts.append(json.dumps({'bid': bid, 'receipt': receipt_str}, sort_keys=True))

    def add_ballot_svr_commitment(self, com_u: int, com_v: int) -> None:
        """
        Add a component of a ballot SVR to local receipt list, these are posted in bulk later.

        It is important that the order of incoming ballots/components be retained for ballot
        verification in the proof step.
        """
        self._svr_commitments.append(json.dumps(
            {'com_u': com_u, 'com_v': com_v},
            sort_keys=True,
        ))

    def post_ballots_and_commitments(self) -> None:
        """
        Post all retained ballots and their SVR commitments to SBB.
        """
        self._db.write(BALLOT_RECEIPTS + '\n')
        for receipt in self._ballot_receipts:
            self._db.write(receipt + '\n')
        self._db.write(END_SECTION + '\n')

        self._db.write(COMMITMENTS + '\n')
        for com in self._svr_commitments:
            self._db.write(com + '\n')
        self._db.write(END_SECTION + '\n')

        # The sbb file is still open while elsewhere it is being read, so make sure
        # output doesn't stay in the memory buffer.
        self._db.flush()

    def post_one_mixnet_output_list(self, com_t: List[Dict[int, Dict[str, int]]]) -> None:
        """
        Called once for each of the 2m lists posted after mixing.

        For a 3 component SVR:
            ComT = (ComSV(X), ComSV(Y), ComSV(Z))

        There are N of these commitments, one per vote. Instead of x/y/z we use row
        indices so that arbitrary sized mix-nets can be used.
        """
        self._db.write(VOTE_LIST + '\n')
        self._db.write(json.dumps(com_t) + '\n')
        self._db.flush()

    def post_end_section(self) -> None:
        self._db.write(END_SECTION + '\n')
        self._db.flush()

    def get_sbb_contents(self) -> SBBContents:
        """
        Parses the SBB and returns a container type for easier data access.

        In practice this is something that each verifier would do either manually
        (i.e. looking at the SBB for their bid) or programmatically (i.e. writing
        a parser to verifier the SBB proof).

        TODO - The SBB design and my method of parsing seem messy/confusing. Maybe
        there is a way to simplify this.
        """
        sbb_contents = SBBContents()

        with open(FILENAME, 'r') as f:
            lines = f.read().splitlines()

        i = 0
        while i < len(lines) - 1:
            heading = lines[i]
            i += 1
            line = lines[i]

            if heading == BALLOT_RECEIPTS:
                while line != END_SECTION:
                    receipt = json.loads(line)
                    sbb_contents.ballot_receipts[receipt['bid']] = receipt['receipt']
                    i += 1
                    line = lines[i]
            elif heading == COMMITMENTS:
                pass
            elif heading == VOTE_LIST:
                pass
            else:
                # TODO - uncomment below line once all parsing is complete.
                # Or remove it if we go with a different parsing method.
                # raise Exception('Unexpected SBB content')
                pass

        return sbb_contents
