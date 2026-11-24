import time
import unittest

from custom_components.ripple_presence.history import KEEP_S, History

NOW = time.time() - 1000


class HistoryTests(unittest.TestCase):
    def test_only_changes_are_kept(self):
        h = History()
        h.add('a', 'b', True, 'live', NOW + 0)
        h.add('a', 'b', True, 'diag', NOW + 1)
        h.add('a', 'b', False, 'live', NOW + 2)
        self.assertEqual([(e['on'], e['src']) for e in h.query(since=0)], [(False, 'live'), (True, 'live')])

    def test_first_off_is_not_an_event(self):
        h = History()
        self.assertFalse(h.add('a', 'b', False, 'diag', NOW + 0))

    def test_lines_are_per_receiver(self):
        h = History()
        h.add('a', 'x', True, 'live', NOW + 0)
        h.add('b', 'x', True, 'live', NOW + 1)
        self.assertEqual([e['rx'] for e in h.query({('a', 'x')}, since=0)], ['a'])

    def test_window_and_prune(self):
        h = History()
        t = time.time()
        h.add('a', 'b', True, 'live', t - KEEP_S - 10)
        h.add('a', 'b', False, 'live', t - 50)
        h.add('a', 'b', True, 'live', t - 10)
        self.assertEqual(len(h.events), 2)
        self.assertEqual([e['on'] for e in h.query(since=t - 60, until=t - 20)], [False])


if __name__ == '__main__':
    unittest.main()
