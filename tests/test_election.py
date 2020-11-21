from src import election


def test_election():
    elec = election.Election()
    elec.run()
    assert elec
