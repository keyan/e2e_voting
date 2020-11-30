from src import election


def test_election():
    elec = election.Election(num_voters=3)
    elec.run()
    assert elec
