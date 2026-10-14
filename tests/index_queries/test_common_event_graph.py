import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from vxace_common_event_graph import cycles
from vxace_copy_patcher import current_inventory
from vxace_event_lint import FLAGS, lint, main


def command(code, parameters=None, indent=0):
    return {'__class__': 'RPG::EventCommand', 'code': code, 'indent': indent, 'parameters': parameters or []}


class CommonEventGraphTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.index = self.base / 'index'; self.game = self.base / 'game'
        (self.game / 'Data').mkdir(parents=True); (self.game / 'Data/CommonEvents.rvdata2').write_bytes(b'hashed fixture only')
        (self.index / 'maps').mkdir(parents=True)
        self.write('project.json', {'errors': [], 'map_count': 0, 'database_files_decoded': ['CommonEvents.rvdata2']})
        self.write('manifest.json', {'read_only': True, 'files': [{'path': k, 'sha256': v} for k, v in current_inventory(self.game).items()]})

    def write(self, path, value):
        file = self.index / path; file.parent.mkdir(parents=True, exist_ok=True); file.write_text(json.dumps(value), encoding='utf-8')

    def graph(self, targets):
        self.common = [None] + [{'__class__': 'RPG::CommonEvent', 'id': i, 'trigger': 0,
                      'list': [command(117, [target]) for target in row] + [command(0)]}
                     for i, row in enumerate(targets, 1)]
        self.write('database/common-events.json', self.common)
        return lint(self.index)

    def recursion(self, result):
        return [x for x in result['findings'] if x['code'] == 'possible_common_event_recursion']

    def test_self_call_has_exact_native_evidence(self):
        result = self.graph([[1]]); finding = self.recursion(result)[0]
        self.assertEqual(finding['common_event_ids'], [1])
        self.assertEqual(finding['evidence'], {'file': 'database/common-events.json', 'path': [1, 'list', 0], 'scope': 'common_event', 'common_event_id': 1})
        self.assertFalse(result['mutation_authorized']); self.assertTrue(result['coverage_complete'])

    def test_mutual_calls_form_one_component(self):
        result = self.graph([[2], [1]])
        self.assertEqual([x['common_event_ids'] for x in self.recursion(result)], [[1, 2]])
        self.assertEqual(result['common_event_graph']['unique_edges'], 2)

    def test_acyclic_nested_calls_are_not_reported_as_recursion(self):
        self.assertFalse(self.recursion(self.graph([[2], [3], []])))

    def test_downstream_nodes_are_not_falsely_included_in_cycle(self):
        result = self.graph([[2], [3], [2, 4], [5], []])
        self.assertEqual([x['common_event_ids'] for x in self.recursion(result)], [[2, 3]])

    def test_disconnected_cycles_remain_distinct(self):
        result = self.graph([[1], [3], [2], [], [5]])
        self.assertEqual([x['common_event_ids'] for x in self.recursion(result)], [[1], [2, 3], [5]])

    def test_conditional_call_is_potential_not_termination_proof(self):
        self.graph([[], [1]])
        self.common[1]['list'] = [command(111, [0, 1, 0]), command(117, [2], 1), command(412), command(0)]
        self.write('database/common-events.json', self.common)
        finding = self.recursion(lint(self.index))[0]
        self.assertIn('may prevent or bound', finding['detail'])
        self.assertEqual(finding['severity'], 'warning')

    def test_missing_call_target_is_separate_from_a_cycle(self):
        result = self.graph([[99]])
        self.assertFalse(self.recursion(result))
        self.assertEqual(result['findings'][0]['code'], 'missing_common_event_call')
        self.assertEqual(result['findings'][0]['target_common_event_id'], 99)

    def test_opaque_call_arguments_mark_partial_coverage(self):
        for params in ([True], ['1'], [], [1, 2], [0]):
            self.graph([[]]); self.common[1]['list'] = [command(117, params), command(0)]
            self.write('database/common-events.json', self.common)
            result = lint(self.index)
            self.assertEqual(result['findings'][0]['code'], 'opaque_common_event_call')
            self.assertFalse(result['coverage_complete'])

    def test_owner_ids_must_match_native_array_slots(self):
        self.graph([[]]); self.common[1]['id'] = 2; self.write('database/common-events.json', self.common)
        with self.assertRaisesRegex(ValueError, 'native array slots'): lint(self.index)

    def test_repeated_calls_have_bounded_evidence_without_losing_count(self):
        result = self.graph([[1] * 50]); finding = self.recursion(result)[0]
        self.assertEqual(finding['call_sites'], 50); self.assertEqual(len(finding['call_evidence']), 40)
        self.assertTrue(finding['call_evidence_truncated'])

    def test_map_entry_is_not_a_common_event_graph_node(self):
        self.graph([[1]])
        page = {'__class__': 'RPG::Event::Page', 'trigger': 0,
                'condition': {field: False for field in FLAGS}, 'list': [command(117, [1]), command(0)]}
        self.write('maps/map-001.json', {'__class__': 'RPG::Map', 'events': {'1': {'__class__': 'RPG::Event', 'id': 1, 'pages': [page]}}})
        self.write('project.json', {'errors': [], 'map_count': 1, 'database_files_decoded': ['CommonEvents.rvdata2']})
        result = lint(self.index)
        self.assertEqual(result['common_event_graph']['entry_call_sites'], 1)
        self.assertEqual(result['common_event_graph']['nodes'], 1)

    def test_cli_source_index_integrity_and_stale_refusal(self):
        self.graph([[2], [1]])
        before = (current_inventory(self.game), current_inventory(self.index))
        args = [str(self.index), '--project', str(self.game), '--output', str(self.base / 'report')]
        self.assertEqual(main(args), 3)
        self.assertEqual(before, (current_inventory(self.game), current_inventory(self.index)))
        (self.game / 'Data/CommonEvents.rvdata2').write_bytes(b'changed')
        args[-1] = str(self.base / 'stale'); self.assertEqual(main(args), 2); self.assertFalse(Path(args[-1]).exists())

    def test_troop_calls_are_entry_sites_not_common_event_nodes(self):
        self.graph([[]])
        self.write('database/troops.json', [None, {'__class__': 'RPG::Troop', 'id': 1,
                   'pages': [{'list': [command(117, [1]), command(0)]}]}])
        result = lint(self.index)
        self.assertEqual(result['common_event_graph']['entry_call_sites'], 1)
        self.assertEqual(result['common_event_graph']['unique_edges'], 0)
        self.assertFalse(self.recursion(result))

    def test_deep_graph_uses_iterative_walk_instead_of_python_recursion(self):
        nodes = set(range(5000)); edges = {(i, i + 1) for i in range(4999)} | {(4999, 4998)}
        self.assertEqual(cycles(nodes, edges, lambda amount=1: None), [[4998, 4999]])

    def test_call_graph_budget_refuses_instead_of_returning_partial_cycles(self):
        with self.assertRaisesRegex(ValueError, 'graph budget'): self.graph([[1] * 10001])


if __name__ == '__main__':
    unittest.main()
