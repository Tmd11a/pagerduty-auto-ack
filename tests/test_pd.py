import unittest

from pagerduty_auto_ack import pd


class FakeClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        return next(self.responses)


class PagerDutyTests(unittest.TestCase):
    def test_lists_all_pages_of_triggered_incidents(self):
        client = FakeClient(
            [
                {"incidents": [{"id": "P1"}], "more": True},
                {"incidents": [{"id": "P2"}], "more": False},
            ]
        )

        incidents = pd.get_triggered_incidents(
            client, user_ids=["U1"], urgencies=["high"]
        )

        self.assertEqual([{"id": "P1"}, {"id": "P2"}], incidents)
        self.assertEqual(2, len(client.calls))
        self.assertIn(("offset", 0), client.calls[0][2]["params"])
        self.assertIn(("offset", 1), client.calls[1][2]["params"])
        self.assertIn(("user_ids[]", "U1"), client.calls[0][2]["params"])
        self.assertIn(("urgencies[]", "high"), client.calls[0][2]["params"])

    def test_acknowledges_in_api_sized_batches(self):
        client = FakeClient(
            [
                {"incidents": [{"id": "P1"}]},
                {"incidents": [{"id": "P251"}]},
            ]
        )

        acknowledged = pd.acknowledge_incidents(
            client, [f"P{number}" for number in range(1, 252)]
        )

        self.assertEqual([{"id": "P1"}, {"id": "P251"}], acknowledged)
        self.assertEqual(2, len(client.calls))
        first_batch = client.calls[0][2]["body"]["incidents"]
        second_batch = client.calls[1][2]["body"]["incidents"]
        self.assertEqual(250, len(first_batch))
        self.assertEqual(["P251"], [incident["id"] for incident in second_batch])
        self.assertEqual("acknowledged", first_batch[0]["status"])

    def test_does_not_call_api_when_nothing_needs_acknowledging(self):
        client = FakeClient([])

        self.assertEqual([], pd.acknowledge_incidents(client, []))
        self.assertEqual([], client.calls)
