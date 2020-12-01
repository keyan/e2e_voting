import json
from typing import Dict, List, TextIO

from src import sv_vote
from src import util

FILENAME = 'sbb.txt'

# Define SBB headings used to later parse the SBB during proof.
BALLOT_RECEIPTS = 'ballot_receipts'
ORIGINAL_ORDER_COMMITMENTS = 'original_order_commitments'
MIXNET_VOTE_COMMITMENT_LIST = 'mixnet_vote_commitment_list'
END_SECTION = 'end_section'
ELECTION_OUTCOME = 'election_outcome'


class SBBContents:
    """
    Container type used for simplifying data access to the SBB.

    After parsing the SBB, data is loaded into an instance of
    SBBContents for consumers to access.
    """
    def __init__(self):
        # Maps bids to receipt hashes.
        self.ballot_receipts: Dict[int, str] = {}

        # List of SVR commitment n-tuples.
        # - 2m lists total
        # - each list is n (number of votes) long
        # - each entry in that list is a ComT value comprised of ComSV n-tuples
        # See Section IX - "Posting of split-value representations of mix-net outputs"
        self.vote_lists: List[List[List[util.ComSV]]] = []

        # Maps list index to a list of SVR n-tuples.
        # Where election_outcomes[i][j] is an n-tuple SVR representing the j'th vote
        # (remember the position is shuffled) in the i'th posted list from the PS.
        self.election_outcomes: Dict[int, List[List[sv_vote.PlaintextSVR]]] = {}

    def get_bid_receipt(self, bid: int) -> str:
        """
        Returns the ballot receipt for the provided bid.
        """
        return self.ballot_receipts[bid]


class SBB:
    """
    Implements an interface for the Secure Bulletin Board (SBB).
    """
    def __init__(self, num_voters: int, twoM: int):
        self._num_voters: int = num_voters
        self._twoM: int = twoM
        self._ballot_receipts: List[str] = []
        self._svr_commitments: List[str] = []
        self._db: TextIO = open(FILENAME, 'w')

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
        self.post_end_section()

        self._db.write(ORIGINAL_ORDER_COMMITMENTS + '\n')
        for com in self._svr_commitments:
            self._db.write(com + '\n')
        self.post_end_section()

        # The sbb file is still open while elsewhere it is being read, so make sure
        # output doesn't stay in the memory buffer.
        self._db.flush()

    def post_start_mixnet_output_list(self) -> None:
        """
        Called once by the PS prior to starting to post mixnet output lists,
        of which there are 2m in total.
        """
        self._db.write(MIXNET_VOTE_COMMITMENT_LIST + '\n')

    def post_one_mixnet_output_list(self, com_t: List[List[Dict[str, int]]]) -> None:
        """
        Called once for each of the 2m lists posted after mixing.

        For a 3 component SVR:
            ComT = (ComSV(X), ComSV(Y), ComSV(Z))

        There are N of these commitments, one per vote. Instead of x/y/z we use row
        indices so that arbitrary sized mix-nets can be used.
        """
        self._db.write(json.dumps(com_t) + '\n')

    def post_start_election_outcome_proof(self) -> None:
        """
        Called once by the PS prior to starting to post election outcome results,
        which are SVR commitment openings.
        """
        self._db.write(ELECTION_OUTCOME + '\n')

    def post_one_election_outcome_proof(self, list_idx: int, svrs: List[List[Dict[str, int]]]) -> None:
        """
        Called once for each of the m lists which have all SVR commitments opened publicly.
        """
        self._db.write(json.dumps({'list_idx': list_idx, 'svrs': svrs}) + '\n')

    def post_end_section(self) -> None:
        self._db.write(END_SECTION + '\n')
        self._db.flush()

    def get_sbb_contents(self) -> SBBContents:
        """
        Parses the SBB and returns a container type for easier data access.

        In practice this is something that each verifier would do either manually
        (i.e. looking at the SBB for their bid) or programmatically (i.e. writing
        a parser to verifier the SBB proof).
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
                assert len(sbb_contents.ballot_receipts) == self._num_voters
            elif heading == ORIGINAL_ORDER_COMMITMENTS:
                # TODO
                pass
            elif heading == MIXNET_VOTE_COMMITMENT_LIST:
                while line != END_SECTION:
                    votes: List[List[util.ComSV]] = []

                    vote_list = json.loads(line)
                    for vl in vote_list:
                        vote: List[util.ComSV] = []
                        for component in vl:
                            com_sv = util.ComSV(com_u=component['com_u'], com_v=component['com_v'])
                            vote.append(com_sv)
                        votes.append(vote)
                    sbb_contents.vote_lists.append(votes)
                    i += 1
                    line = lines[i]

                # Each vote commitment is a ComT, a n-tuple of ComSV values.
                # There are num_votes total ComT values per PS "list" (1 of 2m).
                assert len(sbb_contents.vote_lists) == self._twoM
                assert all(
                    len(sbb_contents.vote_lists[i]) == self._num_voters
                    for i in range(self._twoM)
                )
            elif heading == ELECTION_OUTCOME:
                while line != END_SECTION:
                    svrs: List[List[sv_vote.PlaintextSVR]] = []

                    outcome = json.loads(line)
                    for svr in outcome['svrs']:
                        opened_com_t: List[sv_vote.PlaintextSVR] = []
                        for component in svr:
                            p_svr = sv_vote.PlaintextSVR(
                                k1=util.bigint_to_bytes(component['k1']),
                                k2=util.bigint_to_bytes(component['k2']),
                                u=util.bigint_to_bytes(component['u']),
                                v=util.bigint_to_bytes(component['v']),
                            )
                            opened_com_t.append(p_svr)
                        svrs.append(opened_com_t)
                    sbb_contents.election_outcomes[outcome['list_idx']] = svrs
                    i += 1
                    line = lines[i]

                assert len(sbb_contents.election_outcomes) == self._twoM // 2
                for outcomes in sbb_contents.election_outcomes.values():
                    assert len(outcomes) == self._num_voters
            else:
                # TODO - uncomment below line once all parsing is complete.
                # raise Exception('Unexpected SBB content')
                pass

        return sbb_contents
