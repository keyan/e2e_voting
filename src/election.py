import random
from typing import List, Optional, Set

from src import sbb
from src import tablet
from src import voter
from src import proof_server
from src import verifier


class Election:
    def __init__(
        self,
        num_voters: int,
        M: int = 5,
        twoM: int = 24,
        num_tablets: int = 3,
        num_proof_srv_rows: int = 3,
    ):
        # M should be prime
        self.M = M
        # Explained in detail in Section IX, the higher this value is the greater the
        # level of assurance in the SBB posted proof. But increasing 2m also increases
        # memory usage and computation time.
        self.twoM = twoM

        self.sbb = sbb.SBB(num_voters=num_voters, twoM=self.twoM)
        self.proof_server = proof_server.ProofServer(
            M=self.M, twoM=self.twoM, rows=num_proof_srv_rows, sbb=self.sbb,
        )
        self.verifier = verifier.Verifier(M=self.M, sbb=self.sbb, num_voters=num_voters)
        self.voters = [voter.Voter(voter_id=i, M=self.M) for i in range(num_voters)]
        self.tablets = [
            tablet.Tablet(srv=self.proof_server, M=self.M, sbb=self.sbb)
            for _ in range(num_tablets)
        ]

    def _finish_election(self, outcome_lists: Set[int]) -> None:
        """
        Uses independent verifier to check tally using SBB and print results
        if the SBB data passes verification.
        """
        # In theory this step can be taken by anyone because it only relies on
        # data which is publically posted to the SBB.
        print('Tallying and verifying election outcomes...\n')
        final_tally = self.verifier.tally_and_verify_election_outcome(outcome_lists)

        print('Final election tally:')
        print("{:<10} {:<10}".format('Choice', 'Votes'))
        winners: List[int] = []
        most_votes = 0
        for choice, votes in sorted(final_tally.items(), key=lambda x: x[0]):
            if votes > most_votes:
                winners = [choice]
                most_votes = votes
            elif votes == most_votes:
                winners.append(choice)
            print ("{:<10} {:<10}".format(choice, votes))

        print()

        if len(winners) == 1:
            print(f'Election winner is choice: {winners[0]}')
        else:
            print(f'Election is a tie between choices: {winners}')

        print('\nElection complete')

    def run(self):
        print('Running election...')

        # Step 2
        for v in self.voters:
            t = self._get_tablet()
            v.do_vote(t)

        # Step 3
        self.sbb.post_ballots_and_commitments()

        # Step 4
        # Verify election results for each voter.
        sbb_contents = self.sbb.get_sbb_contents()
        for v in self.voters:
            if not v.verify(sbb_contents):
                raise Exception('Voter ballot failed validation')
            else:
                print(f'Voter ID: {v.voter_id}, verified posted ballot hash: {v.ballot_hash}')

        # Step 5
        # End the election and mix votes.
        print('Mixing votes...')
        self.proof_server.mix_votes()

        # Step 6
        # Create a random challenge specifying which `m` lists to use for proving
        # consistency and (implicitly) which `m` votes to use for posting the
        # election outcome.
        print('Creating random challenge...')
        all_two_m = set(range(self.twoM))
        proof_lists: Set[int] = set(random.sample(all_two_m, self.twoM // 2))
        outcome_lists: Set[int] = all_two_m - proof_lists
        assert len(proof_lists) == len(outcome_lists) == self.twoM // 2

        # Step 7
        # Tell PS which lists to un-shuffle, partially decrypt, and post to the SBB.
        print('Publishing consistency proof...')
        self.proof_server.publish_vote_consistency_proof(proof_lists)
        # A unrelated verifier server should be able to read the SBB and verify the
        # proof that the partially decrypted votes are eqivalent to the SBB published
        # cast votes from Step 3.
        print('Verifying consistency proof...')
        if not self.verifier.verify_ballot_consistency():
            raise Exception('Could not verifier consistency of SBB posted ballots')

        # Step 8
        # Tell PS which (still shuffled) lists to fully decrypt and post to the SBB.
        print('Publishing election outcomes...')
        self.proof_server.publish_election_outcome(outcome_lists)
        # Nothing left to publish to SBB.
        self.sbb.close()
        # Compute tally and if verified, print results.
        self._finish_election(outcome_lists)

    def _get_tablet(self) -> tablet.Tablet:
        """
        Select random tablet and return it.
        """
        return random.choice(self.tablets)
