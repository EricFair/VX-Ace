import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tests/structure'))
sys.path.insert(0, str(ROOT / 'tests/smoke'))
import vxace_recipe as recipe
import vxace_python_mutator as backend
from vxace_copy_patcher import current_inventory

EXAMPLE = ROOT / 'tools/recipes/example_cave.json'


def example():
    return json.loads(EXAMPLE.read_text(encoding='utf-8'))


class ValidationTests(unittest.TestCase):
    def bad(self, mutate, text):
        data = example()
        mutate(data)
        with self.assertRaises(recipe.RecipeError) as ctx:
            recipe.validate_recipe(data)
        self.assertIn(text, str(ctx.exception))

    def test_example_is_valid(self):
        self.assertEqual(len(recipe.validate_recipe(example())), 4)
        self.assertEqual(recipe.load_recipe(EXAMPLE)['title'], 'Cave bats')

    def test_unknown_type_and_keys(self):
        self.bad(lambda d: d['steps'][0].update(type='delete_entry'), 'unknown or missing type')
        self.bad(lambda d: d['steps'][0].update(extra=1), 'unknown keys')
        self.bad(lambda d: d.update(extra=1), 'only "title" and "steps"')
        self.bad(lambda d: d['steps'][0].pop('overrides'), 'missing keys')
        self.bad(lambda d: d.update(steps=[]), 'steps must be')

    def test_bad_table_and_types(self):
        self.bad(lambda d: d['steps'][0].update(table='items'), 'table must be')
        self.bad(lambda d: d['steps'][0].update(template_id=True), 'template_id')
        self.bad(lambda d: d['steps'][3].update(weight='10'), 'weight')
        self.bad(lambda d: d['steps'][3].update(region_ids=[1.5]), 'region_ids')

    def test_from_step_must_be_backward_and_typed(self):
        self.bad(lambda d: d['steps'][2]['overrides']['members'][0].update(enemy_id={'from_step': 3}), 'earlier step')
        self.bad(lambda d: d['steps'][2]['overrides']['members'][0].update(enemy_id={'from_step': 9}), 'earlier step')
        self.bad(lambda d: d['steps'][2]['overrides']['members'][0].update(enemy_id={'from_step': 2}), 'table enemies')
        self.bad(lambda d: d['steps'][3].update(troop_id={'from_step': 1}), 'table troops')
        self.bad(lambda d: d['steps'][3].update(troop_id={'from_step': 3, 'x': 1}), 'exactly')
        self.bad(lambda d: d['steps'][0]['overrides'].update(exp={'from_step': 1}), 'only allowed')
        self.bad(lambda d: d['steps'][3].update(weight={'from_step': 1}), 'weight')

    def test_append_learning_validation(self):
        good = {'type': 'append_learning', 'class_id': 1, 'skill_id': {'from_step': 2}, 'level': 5}

        def bad(step, text):
            data = example()
            data['steps'].append(step)
            with self.assertRaises(recipe.RecipeError) as ctx:
                recipe.validate_recipe(data)
            self.assertIn(text, str(ctx.exception))
        data = example()
        data['steps'].append(good)
        self.assertEqual(len(recipe.validate_recipe(data)), 5)
        data['steps'][4]['skill_id'] = 7
        recipe.validate_recipe(data)
        bad({**good, 'skill_id': {'from_step': 1}}, 'table skills')
        bad({**good, 'skill_id': {'from_step': 5}}, 'earlier step')
        bad({**good, 'skill_id': {'from_step': 9}}, 'earlier step')
        bad({**good, 'skill_id': {'from_step': 2, 'x': 1}}, 'exactly')
        bad({**good, 'skill_id': 0}, 'skill_id')
        bad({**good, 'skill_id': True}, 'skill_id')
        bad({**good, 'class_id': 0}, 'class_id')
        bad({**good, 'class_id': {'from_step': 2}}, 'class_id')
        bad({**good, 'level': {'from_step': 2}}, 'level')
        bad({**good, 'level': '5'}, 'level')
        bad({**good, 'level': 5.0}, 'level')
        bad({**good, 'extra': 1}, 'unknown keys')
        bad({'type': 'append_learning', 'class_id': 1, 'level': 5}, 'missing keys')
        bad({**good, 'expected_class_sha256': '0' * 64}, 'unknown keys')

    def shop_recipe(self):
        return {'steps': [
            {'type': 'append_entry', 'table': 'weapons', 'template_id': 1, 'overrides': {'name': 'Blade'}},
            {'type': 'append_entry', 'table': 'armors', 'template_id': 1, 'overrides': {'name': 'Plate'}},
            {'type': 'append_key_item', 'template_item': 1, 'name': 'Charm', 'description': 'x'},
            {'type': 'append_dialogue_event', 'map_id': 1, 'template_event': 1, 'x': 3, 'y': 4, 'name': 'Smith', 'lines': ['Hello.']},
            {'type': 'add_shop', 'map_id': 1, 'event_id': {'from_step': 4}, 'purchase_only': False,
             'goods': [{'type': 'weapon', 'id': {'from_step': 1}, 'price': None}, {'type': 'armor', 'id': {'from_step': 2}, 'price': 5},
                       {'type': 'item', 'id': {'from_step': 3}, 'price': 0}, {'type': 'item', 'id': 2, 'price': None}]}]}

    def shop_bad(self, mutate, text):
        data = self.shop_recipe()
        mutate(data)
        with self.assertRaises(recipe.RecipeError) as ctx:
            recipe.validate_recipe(data)
        self.assertIn(text, str(ctx.exception))

    def test_shop_and_dialogue_event_steps_validate(self):
        self.assertEqual(len(recipe.validate_recipe(self.shop_recipe())), 5)
        data = self.shop_recipe()
        data['steps'][4].update(event_id=2, purchase_only=True)
        recipe.validate_recipe(data)

    def test_dialogue_event_step_is_strict(self):
        for key, value, text in (('map_id', 0, 'map_id'), ('map_id', True, 'map_id'), ('template_event', 0, 'template_event'), ('x', -1, 'x'),
                                 ('y', True, 'y'), ('name', '', 'name'), ('name', 3, 'name'), ('lines', [], 'lines'), ('lines', ['a'] * 5, 'lines'),
                                 ('lines', 'text', 'lines'), ('lines', [1], 'lines'), ('lines', [{'from_step': 1}], 'lines')):
            self.shop_bad(lambda d, k=key, v=value: d['steps'][3].update({k: v}), text)
        self.shop_bad(lambda d: d['steps'][3].update(graphic={}), 'unknown keys')
        self.shop_bad(lambda d: d['steps'][3].pop('lines'), 'missing keys')
        self.shop_bad(lambda d: d['steps'][3].update(expected_map_sha256='0' * 64), 'unknown keys')
        self.shop_bad(lambda d: d['steps'][3].update(x={'from_step': 1}), 'x')

    def test_shop_step_is_strict(self):
        self.shop_bad(lambda d: d['steps'][4].update(purchase_only='no'), 'purchase_only')
        self.shop_bad(lambda d: d['steps'][4].update(purchase_only=1), 'purchase_only')
        self.shop_bad(lambda d: d['steps'][4].pop('purchase_only'), 'missing keys')
        self.shop_bad(lambda d: d['steps'][4].update(goods=[]), 'goods')
        self.shop_bad(lambda d: d['steps'][4].update(goods=[{'type': 'item', 'id': 1, 'price': None}] * 2), 'duplicate')
        self.shop_bad(lambda d: d['steps'][4].update(goods=[{'type': 'item', 'id': i % 5 + 1, 'price': None} for i in range(33)]), 'goods')
        self.shop_bad(lambda d: d['steps'][4].update(map_id=0), 'map_id')
        self.shop_bad(lambda d: d['steps'][4].update(event_id=0), 'event_id')
        self.shop_bad(lambda d: d['steps'][4].update(event_id=True), 'event_id')
        self.shop_bad(lambda d: d['steps'][4].update(expected_items_sha256='0' * 64), 'unknown keys')
        for good, text in (({'type': 'gem', 'id': 1, 'price': None}, 'each good'), ({'type': 'item', 'id': 1}, 'each good'),
                           ({'type': 'item', 'id': 1, 'price': None, 'x': 1}, 'each good'), ({'type': 'item', 'id': 0, 'price': None}, 'goods id'),
                           ({'type': 'item', 'id': True, 'price': None}, 'goods id'), ({'type': 'item', 'id': 1.5, 'price': None}, 'goods id'),
                           ({'type': 'item', 'id': 1, 'price': -1}, 'price'), ({'type': 'item', 'id': 1, 'price': 10000000}, 'price'),
                           ({'type': 'item', 'id': 1, 'price': True}, 'price'), ({'type': 'item', 'id': 1, 'price': '5'}, 'price'),
                           ({'type': 'item', 'id': 1, 'price': {'from_step': 1}}, 'price'), ('item', 'each good')):
            self.shop_bad(lambda d, g=good: d['steps'][4].update(goods=[g]), text)

    def test_shop_from_step_rules(self):
        self.shop_bad(lambda d: d['steps'][4].update(event_id={'from_step': 5}), 'earlier step')
        self.shop_bad(lambda d: d['steps'][4].update(event_id={'from_step': 9}), 'earlier step')
        self.shop_bad(lambda d: d['steps'][4].update(event_id={'from_step': 1}), 'append_dialogue_event')
        self.shop_bad(lambda d: d['steps'][4].update(event_id={'from_step': 4, 'x': 1}), 'exactly')
        self.shop_bad(lambda d: d['steps'][4].update(map_id=2), 'different map')
        self.shop_bad(lambda d: d['steps'][4]['goods'][0].update(id={'from_step': 2}), 'table weapons')
        self.shop_bad(lambda d: d['steps'][4]['goods'][1].update(id={'from_step': 1}), 'table armors')
        self.shop_bad(lambda d: d['steps'][4]['goods'][2].update(id={'from_step': 1}), 'append_key_item')
        self.shop_bad(lambda d: d['steps'][4]['goods'][0].update(id={'from_step': 4}), 'table weapons')
        self.shop_bad(lambda d: d['steps'][4]['goods'][0].update(id={'from_step': 5}), 'earlier step')
        self.shop_bad(lambda d: d['steps'][4]['goods'][0].update(id={'from_step': 1, 'y': 2}), 'exactly')
        self.shop_bad(lambda d: d['steps'][4]['goods'][0].update(type='item'), 'append_key_item')
        self.shop_bad(lambda d: d['steps'][3].update(name={'from_step': 1}), 'name')
        self.shop_bad(lambda d: d['steps'][1]['overrides'].update(price={'from_step': 1}), 'only allowed')

    def blank_recipe(self):
        return {'steps': [
            {'type': 'append_blank_event', 'map_id': 1, 'donor_event': 1, 'x': 5, 'y': 5},
            {'type': 'append_dialogue_event', 'map_id': 1, 'template_event': {'from_step': 1}, 'x': 7, 'y': 7, 'name': 'Smith', 'lines': ['Hello.']},
            {'type': 'add_shop', 'map_id': 1, 'event_id': {'from_step': 2}, 'purchase_only': False,
             'goods': [{'type': 'item', 'id': 1, 'price': 20}]}]}

    def test_blank_event_step_validates_and_is_strict(self):
        self.assertEqual(len(recipe.validate_recipe(self.blank_recipe())), 3)
        data = self.blank_recipe()
        data['steps'][0]['name'] = 'EV009'
        recipe.validate_recipe(data)
        for key, value, text in (('map_id', 0, 'map_id'), ('map_id', True, 'map_id'), ('donor_event', 0, 'donor_event'), ('donor_event', True, 'donor_event'),
                                 ('donor_event', {'from_step': 1}, 'donor_event'), ('x', -1, 'x'), ('y', True, 'y'), ('name', '', 'name'),
                                 ('name', 'x' * 101, 'name'), ('name', 3, 'name'), ('name', {'from_step': 1}, 'name')):
            data = self.blank_recipe()
            data['steps'][0][key] = value
            with self.assertRaises(recipe.RecipeError) as ctx:
                recipe.validate_recipe(data)
            self.assertIn(text, str(ctx.exception))
        for extra in ({'expected_map_sha256': '0' * 64}, {'lines': ['x']}, {'graphic': {}}):
            data = self.blank_recipe()
            data['steps'][0].update(extra)
            with self.assertRaises(recipe.RecipeError):
                recipe.validate_recipe(data)

    def test_template_event_from_step_rules(self):
        for mutate, text in ((lambda d: d['steps'][1].update(template_event={'from_step': 2}), 'earlier step'),
                             (lambda d: d['steps'][1].update(template_event={'from_step': 9}), 'earlier step'),
                             (lambda d: d['steps'][1].update(template_event={'from_step': 1, 'x': 1}), 'exactly'),
                             (lambda d: d['steps'][1].update(map_id=2), 'different map'),
                             (lambda d: d['steps'].insert(0, {'type': 'append_key_item', 'template_item': 1, 'name': 'C', 'description': 'x'}), 'append_blank_event'),
                             (lambda d: d['steps'][1].update(x={'from_step': 1}), 'x must be'),
                             (lambda d: d['steps'][0].update(donor_event={'from_step': 1}), 'donor_event')):
            data = self.blank_recipe()
            mutate(data)
            with self.assertRaises(recipe.RecipeError) as ctx:
                recipe.validate_recipe(data)
            self.assertIn(text, str(ctx.exception))

    def test_blank_event_spec_takes_hashes_id_and_default_name_from_snapshot(self):
        step = {'type': 'append_blank_event', 'map_id': 2, 'donor_event': 3, 'x': 1, 'y': 2}
        snap = {'next_event_id': 7, 'default_name': 'EV007', 'map_sha256': 'm' * 64, 'donor_sha256': 'd' * 64}
        change = recipe.build_spec('T', 1, step, snap)['changes'][0]
        self.assertEqual((change['kind'], change['locator']), ('map_event', {'map_id': 2}))
        self.assertEqual(change['mutation'], {'action': 'append_blank_event', 'donor_event_id': 3, 'new_id': 7, 'name': 'EV007', 'x': 1, 'y': 2,
                                              'expected_map_sha256': 'm' * 64, 'expected_donor_sha256': 'd' * 64})
        named = recipe.build_spec('T', 1, dict(step, name='Gate'), snap)['changes'][0]
        self.assertEqual(named['mutation']['name'], 'Gate')
        self.assertEqual(recipe.created_id(step, snap), 7)

    def test_resolve_from_step(self):
        value = {'a': [{'enemy_id': {'from_step': 1}}, {'from_step': 3}], 'b': 2}
        self.assertEqual(recipe.resolve_refs(value, {1: 31, 3: 7}), {'a': [{'enemy_id': 31}, 7], 'b': 2})
        with self.assertRaises(recipe.RecipeError):
            recipe.resolve_refs({'from_step': 2}, {1: 31})
        self.assertEqual(value['a'][0]['enemy_id'], {'from_step': 1})

    def test_created_id_from_snapshot_only(self):
        self.assertEqual(recipe.created_id({'type': 'append_entry'}, {'next_id': 31}), 31)
        self.assertEqual(recipe.created_id({'type': 'append_key_item'}, {'next_item_id': 17}), 17)
        self.assertIsNone(recipe.created_id({'type': 'append_encounter'}, {}))
        self.assertIsNone(recipe.created_id({'type': 'append_learning'}, {'next_id': 5}))


class SpecBuildingTests(unittest.TestCase):
    ENTRY = {'array_sha256': 'a' * 64, 'template_sha256': 'b' * 64, 'enemies_sha256': 'c' * 64, 'next_id': 31, 'append_slot_supported': True}

    def test_entry_spec_takes_hashes_and_id_from_snapshot(self):
        step = {'type': 'append_entry', 'table': 'enemies', 'template_id': 1, 'overrides': {'name': 'Bat'}}
        spec = recipe.build_spec('T', 1, step, self.ENTRY)
        mutation = spec['changes'][0]['mutation']
        self.assertEqual((mutation['new_id'], mutation['expected_array_sha256'], mutation['expected_template_sha256']), (31, 'a' * 64, 'b' * 64))
        self.assertNotIn('expected_enemies_sha256', mutation)
        self.assertEqual(spec['changes'][0]['locator'], {'table': 'enemies'})
        step.update(table='troops')
        self.assertEqual(recipe.build_spec('T', 1, step, self.ENTRY)['changes'][0]['mutation']['expected_enemies_sha256'], 'c' * 64)

    def test_recipe_cannot_inject_hashes(self):
        data = example()
        data['steps'][0]['expected_array_sha256'] = '0' * 64
        with self.assertRaises(recipe.RecipeError):
            recipe.validate_recipe(data)

    def test_full_array_refuses(self):
        step = {'type': 'append_entry', 'table': 'enemies', 'template_id': 1, 'overrides': {'name': 'Bat'}}
        with self.assertRaises(recipe.RecipeError):
            recipe.build_spec('T', 1, step, {**self.ENTRY, 'append_slot_supported': False})

    def test_learning_spec_takes_hashes_and_count_from_snapshot(self):
        snap = {'array_sha256': 'a' * 64, 'class_sha256': 'b' * 64, 'skills_sha256': 'c' * 64, 'learning_count': 4, 'append_supported': True}
        spec = recipe.build_spec('T', 3, {'type': 'append_learning', 'class_id': 2, 'skill_id': 9, 'level': 5}, snap)
        change = spec['changes'][0]
        self.assertEqual((change['kind'], change['locator']), ('database_entry', {'table': 'classes', 'id': 2}))
        self.assertEqual(change['mutation'], {'action': 'append_class_learning', 'expected_array_sha256': 'a' * 64,
                                              'expected_class_sha256': 'b' * 64, 'expected_learning_count': 4,
                                              'expected_skills_sha256': 'c' * 64, 'skill_id': 9, 'level': 5})
        with self.assertRaises(recipe.RecipeError):
            recipe.build_spec('T', 3, {'type': 'append_learning', 'class_id': 2, 'skill_id': 9, 'level': 5}, {**snap, 'append_supported': False})

    def test_key_item_encounter_name_and_script_specs(self):
        item = recipe.build_spec('T', 1, {'type': 'append_key_item', 'template_item': 2, 'name': 'Key', 'description': 'd'},
                                 {'array_sha256': 'a' * 64, 'template_sha256': 'b' * 64, 'next_item_id': 17, 'append_slot_supported': True})
        self.assertEqual((item['changes'][0]['mutation']['new_id'], item['changes'][0]['mutation']['template_id']), (17, 2))
        enc = recipe.build_spec('T', 2, {'type': 'append_encounter', 'map_id': 1, 'troop_id': 3, 'weight': 10},
                                {'map_sha256': 'm' * 64, 'encounter_count': 4, 'troops_sha256': 't' * 64})
        mutation = enc['changes'][0]['mutation']
        self.assertEqual((mutation['expected_encounter_count'], mutation['expected_map_sha256'], mutation['region_ids'], mutation['encounter_step']),
                         (4, 'm' * 64, [], None))
        name = recipe.build_spec('T', 3, {'type': 'set_map_display_name', 'map_id': 1, 'name': 'Cave'},
                                 {'map_id': 1, 'map_sha256': 'm' * 64, 'display_name': 'Old'})
        self.assertEqual(name['changes'][0]['mutation']['expected_display_name'], 'Old')
        script = recipe.build_spec('T', 4, {'type': 'insert_script', 'name': 'Ext', 'source_file': 'x.rb'},
                                   {'before_index': 5, 'unused_id_candidate': 99, 'archive_sha256': 'a' * 64, 'anchor_sha256': 'b' * 64}, 'puts 1')
        self.assertEqual((script['changes'][0]['locator'], script['changes'][0]['mutation']['new_id']), ({'before_index': 5}, 99))


    SHOP = {'map_sha256': 'm' * 64, 'event_sha256': 'e' * 64, 'list_sha256': 'l' * 64, 'items_sha256': 'i' * 64,
            'weapons_sha256': 'w' * 64, 'armors_sha256': 'a' * 64, 'append_supported': True}

    def test_dialogue_event_and_shop_specs_take_everything_from_snapshots(self):
        step = {'type': 'append_dialogue_event', 'map_id': 2, 'template_event': 3, 'x': 1, 'y': 2, 'name': 'Smith', 'lines': ['Hi.']}
        spec = recipe.build_spec('T', 1, step, {'next_event_id': 7, 'map_sha256': 'm' * 64, 'template_sha256': 't' * 64})
        change = spec['changes'][0]
        self.assertEqual((change['kind'], change['locator']), ('map_event', {'map_id': 2}))
        self.assertEqual(change['mutation'], {'action': 'append_dialogue_event', 'template_id': 3, 'new_id': 7, 'name': 'Smith', 'x': 1, 'y': 2,
                                              'text': ['Hi.'], 'expected_map_sha256': 'm' * 64, 'expected_template_sha256': 't' * 64})
        shop = {'type': 'add_shop', 'map_id': 2, 'event_id': 7, 'purchase_only': True, 'goods': [{'type': 'weapon', 'id': 3, 'price': None}]}
        change = recipe.build_spec('T', 2, shop, self.SHOP)['changes'][0]
        self.assertEqual((change['kind'], change['locator']), ('map_shop', {'map_id': 2, 'event_id': 7}))
        self.assertEqual(change['mutation'], {'action': 'add_shop', 'expected_map_sha256': 'm' * 64, 'expected_event_sha256': 'e' * 64,
                                              'expected_list_sha256': 'l' * 64, 'expected_items_sha256': 'i' * 64, 'expected_weapons_sha256': 'w' * 64,
                                              'expected_armors_sha256': 'a' * 64, 'goods': [{'type': 'weapon', 'id': 3, 'price': None}], 'purchase_only': True})
        with self.assertRaises(recipe.RecipeError):
            recipe.build_spec('T', 2, shop, {**self.SHOP, 'append_supported': False, 'unsupported_reason': 'two pages'})
        self.assertEqual(recipe.created_id(step, {'next_event_id': 7}), 7)
        self.assertIsNone(recipe.created_id(shop, {'next_event_id': 7}))

@unittest.skipUnless(shutil.which('ruby'), 'Ruby required for the authored native fixture project')
class EndToEndTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        import test_database_append as table_tests
        import test_troop_append as troop_tests
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.game = self.base / 'game'
        subprocess.run(['ruby', str(ROOT / 'tests/structure/make_map_template.rb'), str(self.game)], check=True, capture_output=True)
        fixture = (ROOT / 'tests/project_reader/make_fixture.rb').read_text()
        prelude = 'module RPG' + fixture.split('module RPG', 1)[1].split('actor =', 1)[0]
        for name, source in (('tables.rb', table_tests.AppendCopyTests.RUBY), ('troops.rb', troop_tests.TroopCopyTests.RUBY)):
            script = self.base / name
            script.write_text(prelude + '\n' + source, encoding='utf-8')
            subprocess.run(['ruby', str(script), str(self.game)], check=True, capture_output=True)
        # A canonical Main entry so script-slot steps and the smoke harness have their anchor.
        main = self.base / 'main.rb'
        main.write_text("require 'zlib'\np=ARGV[0]+'/Data/Scripts.rvdata2'\ns=Marshal.load(File.binread(p))\n"
                        "s << [104,'Main',Zlib::Deflate.deflate(\"rgss_main { SceneManager.run }\\r\\n\").force_encoding('UTF-8')]\n"
                        "File.binwrite(p,Marshal.dump(s))\n", encoding='utf-8')
        subprocess.run(['ruby', str(main), str(self.game)], check=True, capture_output=True)
        import test_class_learning as learning_tests
        script = self.base / 'classes.rb'
        script.write_text(prelude + '\n' + learning_tests.CLASS_RUBY, encoding='utf-8')
        subprocess.run(['ruby', str(script), str(self.game)], check=True, capture_output=True)
        self.work = self.base / 'recipe-work'

    def cli(self, recipe_path, *extra, work=None):
        return subprocess.run([sys.executable, str(ROOT / 'tools/vxace_recipe.py'), 'run', str(recipe_path), '--project', str(self.game),
                               '--work', str(work or self.work), *extra], capture_output=True, text=True)

    def report(self, work=None):
        return json.loads(((work or self.work) / 'recipe-report.json').read_text(encoding='utf-8'))

    def test_four_step_example_chains_copies(self):
        before = current_inventory(self.game)
        result = self.cli(EXAMPLE)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(current_inventory(self.game), before)
        report = self.report()
        self.assertEqual(report['status'], 'pass')
        self.assertTrue(report['original_unchanged'])
        self.assertFalse(report['mutation_performed_on_original'])
        self.assertEqual([s['status'] for s in report['steps']], ['ok'] * 4)
        self.assertEqual([s['created_id'] for s in report['steps']], [3, 3, 3, None])
        members = report['steps'][2]['resolved_parameters']['overrides']['members']
        self.assertEqual([m['enemy_id'] for m in members], [3, 3])
        self.assertEqual(report['steps'][3]['resolved_parameters']['troop_id'], 3)
        final = Path(report['final_copy'])
        self.assertEqual(final, self.work.resolve() / 'step-04/copy')
        self.assertFalse((self.work / 'final').exists())
        # step k builds on step k-1's copy
        self.assertEqual([s['source'] for s in report['steps']],
                         [str(self.game.resolve())] + [str(self.work.resolve() / f'step-0{k}/copy') for k in (1, 2, 3)])
        foes, _ = backend.load(final / 'Data/Enemies.rvdata2')
        skills, _ = backend.load(final / 'Data/Skills.rvdata2')
        troops, _ = backend.load(final / 'Data/Troops.rvdata2')
        self.assertEqual(foes[-1].get('name').data, b'Cave Bat')
        self.assertEqual(skills[-1].get('name').data, b'Fang Strike')
        self.assertEqual(troops[-1].get('name').data, b'Cave Bat Pair')
        self.assertEqual([m.get('enemy_id') for m in troops[-1].get('members')], [len(foes) - 1] * 2)
        game_map, _ = backend.load(final / 'Data/Map001.rvdata2')
        encounters = game_map.get('encounter_list')
        self.assertEqual((encounters[-1].get('troop_id'), encounters[-1].get('weight'), game_map.get('encounter_step')),
                         (len(troops) - 1, 10, 5))
        for step in report['steps']:
            for key in ('spec', 'plan', 'impact', 'audit', 'copy'):
                self.assertTrue(Path(step[key]).exists(), (step['step'], key))
            self.assertEqual(set(step['exit_codes'].values()), {0})
        self.assertTrue((self.work / 'recipe-report.md').is_file())

    def test_failing_step_stops_chain_and_keeps_earlier_outputs(self):
        data = example()
        data['steps'][1]['overrides']['note'] = '<x>'
        bad = self.base / 'bad.json'
        bad.write_text(json.dumps(data), encoding='utf-8')
        before = current_inventory(self.game)
        result = self.cli(bad)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(current_inventory(self.game), before)
        report = self.report()
        self.assertEqual(report['status'], 'step_failed')
        self.assertEqual([s['status'] for s in report['steps']], ['ok', 'failed'])
        self.assertEqual(report['final_copy'], str(self.work.resolve() / 'step-01/copy'))
        self.assertTrue((self.work / 'step-01/copy/Data/Enemies.rvdata2').is_file())
        self.assertFalse((self.work / 'step-03').exists())
        self.assertFalse((self.work / 'step-02/copy').exists())
        self.assertIn('step 2', report['error'])

    def test_invalid_recipe_and_existing_work_refuse_before_writing(self):
        data = example()
        data['steps'][3]['troop_id'] = {'from_step': 4}
        bad = self.base / 'bad.json'
        bad.write_text(json.dumps(data), encoding='utf-8')
        self.assertEqual(self.cli(bad).returncode, 2)
        self.assertFalse(self.work.exists())
        self.work.mkdir()
        self.assertEqual(self.cli(EXAMPLE).returncode, 2)
        self.assertEqual(self.cli(EXAMPLE, work=self.game / 'inside').returncode, 2)
        self.assertFalse((self.game / 'inside').exists())

    def test_new_skill_then_class_learning_with_from_step(self):
        data = {'title': 'Learn', 'steps': [
            {'type': 'append_entry', 'table': 'skills', 'template_id': 1, 'overrides': {'name': 'Fang Strike', 'mp_cost': 4}},
            {'type': 'append_learning', 'class_id': 1, 'skill_id': {'from_step': 1}, 'level': 6}]}
        path = self.base / 'learn.json'
        path.write_text(json.dumps(data), encoding='utf-8')
        before = current_inventory(self.game)
        result = self.cli(path)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(current_inventory(self.game), before)
        report = self.report()
        self.assertEqual([s['status'] for s in report['steps']], ['ok', 'ok'])
        self.assertEqual([s['created_id'] for s in report['steps']], [3, None])
        self.assertEqual(report['steps'][1]['resolved_parameters']['skill_id'], 3)
        self.assertEqual(report['steps'][1]['source'], str(self.work.resolve() / 'step-01/copy'))
        final = Path(report['final_copy'])
        classes, _ = backend.load(final / 'Data/Classes.rvdata2')
        skills, _ = backend.load(final / 'Data/Skills.rvdata2')
        self.assertEqual(skills[3].get('name').data, b'Fang Strike')
        self.assertEqual([(x.get('level'), x.get('skill_id')) for x in classes[1].get('learnings')], [(1, 1), (6, 3)])
        self.assertEqual(classes[2].get('learnings'), [])
        read_spec = json.loads(Path(report['steps'][1]['spec']).read_text(encoding='utf-8'))
        self.assertEqual(read_spec['changes'][0]['locator'], {'table': 'classes', 'id': 1})
        self.assertEqual(read_spec["changes"][0]["mutation"]["skill_id"], 3)
        for key in ('spec', 'plan', 'impact', 'audit', 'copy'):
            self.assertTrue(Path(report['steps'][1][key]).exists(), key)

    def test_learning_step_duplicate_skill_stops_chain(self):
        data = {'title': 'Dup', 'steps': [{'type': 'append_learning', 'class_id': 1, 'skill_id': 1, 'level': 9}]}
        path = self.base / 'dup.json'
        path.write_text(json.dumps(data), encoding='utf-8')
        result = self.cli(path)
        self.assertEqual(result.returncode, 3, result.stderr)
        report = self.report()
        self.assertEqual((report['status'], report['steps'][0]['status']), ('step_failed', 'failed'))
        self.assertIsNone(report['final_copy'])

    def test_display_name_and_encounter_steps(self):
        data = {'title': 'Misc', 'steps': [
            {'type': 'set_map_display_name', 'map_id': 1, 'name': 'Bat Cave'},
            {'type': 'append_encounter', 'map_id': 1, 'troop_id': 2, 'weight': 20},
            {'type': 'insert_script', 'name': 'Recipe Ext', 'source_file': 'ext.rb'}]}
        (self.base / 'ext.rb').write_bytes(b'# recipe extension\n')
        path = self.base / 'misc.json'
        path.write_text(json.dumps(data), encoding='utf-8')
        result = self.cli(path)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        report = self.report()
        game_map, _ = backend.load(Path(report['final_copy']) / 'Data/Map001.rvdata2')
        self.assertEqual(game_map.get('display_name').data, b'Bat Cave')
        self.assertEqual(game_map.get('encounter_list')[-1].get('troop_id'), 2)
        scripts, _ = backend.load(Path(report['final_copy']) / 'Data/Scripts.rvdata2')
        self.assertEqual([e[1].data for e in scripts][-2:], [b'Recipe Ext', b'Main'])
        self.assertEqual(report['steps'][2]['resolved_parameters']['source_bytes'], len(b'# recipe extension\n'))

    def test_text_import_step_applies_main_spec(self):
        import csv
        index = self.base / 'export-index'
        subprocess.run([sys.executable, str(ROOT / 'tools/vxace_project_reader.py'), str(self.game), '--output', str(index)],
                       check=True, capture_output=True)
        exported = self.base / 'text.csv'
        subprocess.run([sys.executable, str(ROOT / 'tools/vxace_text_export.py'), str(index), '--project', str(self.game), '--csv', str(exported)],
                       check=True, capture_output=True)
        with exported.open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        fields = list(rows[0])
        row = next(r for r in rows if r['key'] == 'db:actors/1/name')
        row['translation'] = 'Alicia the Bold'
        edited = self.base / 'edited.csv'
        with edited.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        path = self.base / 'import.json'
        path.write_text(json.dumps({'steps': [{'type': 'text_import', 'csv': 'edited.csv', 'allow_shorter': True}]}), encoding='utf-8')
        result = self.cli(path)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        report = self.report()
        self.assertEqual(report['steps'][0]['status'], 'ok')
        self.assertIsNone(report['steps'][0]['created_id'])
        self.assertTrue(Path(report['steps'][0]['spec']).is_file())
        actors, _ = backend.load(Path(report['final_copy']) / 'Data/Actors.rvdata2')
        self.assertEqual(actors[1].get('name').data, b'Alicia the Bold')

    def add_items(self):
        script = self.base / 'items.rb'
        script.write_text("module RPG; class Item; end; end\nitem = RPG::Item.new\nitem.instance_variable_set(:@id, 1)\n"
                          "item.instance_variable_set(:@name, 'Potion')\n"
                          "File.binwrite(ARGV[0] + '/Data/Items.rvdata2', Marshal.dump([nil, item]))\n", encoding='utf-8')
        subprocess.run(['ruby', str(script), str(self.game)], check=True, capture_output=True)

    def test_new_weapon_dialogue_event_and_shop_chain_with_from_step(self):
        self.add_items()
        data = {'title': 'Smithy', 'steps': [
            {'type': 'append_entry', 'table': 'weapons', 'template_id': 1, 'overrides': {'name': 'Smith Blade', 'price': 300}},
            {'type': 'append_dialogue_event', 'map_id': 1, 'template_event': 1, 'x': 8, 'y': 8, 'name': 'Smith', 'lines': ['Fine steel.']},
            {'type': 'add_shop', 'map_id': 1, 'event_id': {'from_step': 2}, 'purchase_only': True,
             'goods': [{'type': 'weapon', 'id': {'from_step': 1}, 'price': None}, {'type': 'weapon', 'id': 1, 'price': 150},
                       {'type': 'item', 'id': 1, 'price': 20}, {'type': 'armor', 'id': 2, 'price': None}]}]}
        path = self.base / 'smithy.json'
        path.write_text(json.dumps(data), encoding='utf-8')
        before = current_inventory(self.game)
        result = self.cli(path)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(current_inventory(self.game), before)
        report = self.report()
        self.assertEqual([s['status'] for s in report['steps']], ['ok'] * 3)
        self.assertEqual([s['created_id'] for s in report['steps']], [3, 2, None])
        resolved = report['steps'][2]['resolved_parameters']
        self.assertEqual(resolved['event_id'], 2)
        self.assertEqual([g['id'] for g in resolved['goods']], [3, 1, 1, 2])
        self.assertEqual(report['steps'][2]['source'], str(self.work.resolve() / 'step-02/copy'))
        final = Path(report['final_copy'])
        game_map, _ = backend.load(final / 'Data/Map001.rvdata2')
        event = dict(game_map.get('events').pairs)[2]
        commands = event.get('pages')[0].get('list')
        self.assertEqual([c.get('code') for c in commands], [101, 401, 302, 605, 605, 605, 0])
        self.assertEqual([c.get('parameters') for c in commands[2:6]],
                         [[1, 3, 0, 0, True], [1, 1, 1, 150], [0, 1, 1, 20], [2, 2, 0, 0]])
        weapons, _ = backend.load(final / 'Data/Weapons.rvdata2')
        self.assertEqual(weapons[3].get('name').data, b'Smith Blade')
        original, _ = backend.load(self.game / 'Data/System.rvdata2')
        system, _ = backend.load(final / 'Data/System.rvdata2')
        self.assertEqual(system.get('version_id'), original.get('version_id') + 2)
        spec = json.loads(Path(report['steps'][2]['spec']).read_text(encoding='utf-8'))
        self.assertEqual(spec['changes'][0]['locator'], {'map_id': 1, 'event_id': 2})
        for step in report['steps']:
            for key in ('spec', 'plan', 'impact', 'audit', 'copy'):
                self.assertTrue(Path(step[key]).exists(), (step['step'], key))
            self.assertEqual(set(step['exit_codes'].values()), {0})

    def strip_blank_events(self):
        # Make the fixture map's only event non-blank so no v0.26 blank template exists (the donor keeps the native schema).
        path = self.game / 'Data/Map001.rvdata2'
        root, _ = backend.load(path)
        page = root.get('events').pairs[0][1].get('pages')[0]
        page.set('priority_type', 2)
        page.set('trigger', 3)
        page.get('list').insert(0, backend.marshal_rb.load(backend.marshal_rb.dump(page.get('list')[0])))
        page.get('list')[0].set('code', 101)
        path.write_bytes(backend.marshal_rb.dump(root))

    def test_blank_event_dialogue_event_and_shop_chain_on_map_without_blank_event(self):
        self.add_items()
        self.strip_blank_events()
        data = {'title': 'Blank smithy', 'steps': [
            {'type': 'append_blank_event', 'map_id': 1, 'donor_event': 1, 'x': 5, 'y': 5},
            {'type': 'append_dialogue_event', 'map_id': 1, 'template_event': {'from_step': 1}, 'x': 8, 'y': 8, 'name': 'Smith', 'lines': ['Fine steel.']},
            {'type': 'add_shop', 'map_id': 1, 'event_id': {'from_step': 2}, 'purchase_only': True,
             'goods': [{'type': 'weapon', 'id': 1, 'price': 150}, {'type': 'item', 'id': 1, 'price': 20}]}]}
        path = self.base / 'blank-smithy.json'
        path.write_text(json.dumps(data), encoding='utf-8')
        before = current_inventory(self.game)
        # The only existing event is not a blank template, so a literal template_event 1 is refused.
        literal = self.base / 'literal.json'
        literal.write_text(json.dumps({'steps': [dict(data['steps'][1], template_event=1)]}), encoding='utf-8')
        self.assertNotEqual(self.cli(literal, work=self.base / 'literal-work').returncode, 0)
        result = self.cli(path)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(current_inventory(self.game), before)
        report = self.report()
        self.assertEqual([s['status'] for s in report['steps']], ['ok'] * 3)
        self.assertEqual([s['created_id'] for s in report['steps']], [2, 3, None])
        self.assertEqual(report['steps'][1]['resolved_parameters']['template_event'], 2)
        self.assertEqual(report['steps'][2]['resolved_parameters']['event_id'], 3)
        final = Path(report['final_copy'])
        game_map, _ = backend.load(final / 'Data/Map001.rvdata2')
        by_id = dict(game_map.get('events').pairs)
        self.assertEqual(sorted(by_id), [1, 2, 3])
        self.assertEqual((by_id[2].get('name').data, by_id[2].get('x'), by_id[2].get('y')), (b'EV002', 5, 5))
        self.assertEqual([c.get('code') for c in by_id[3].get('pages')[0].get('list')], [101, 401, 302, 605, 0])
        original, _ = backend.load(self.game / 'Data/System.rvdata2')
        system, _ = backend.load(final / 'Data/System.rvdata2')
        self.assertEqual(system.get('version_id'), original.get('version_id') + 3)

    def test_shop_step_with_absent_goods_id_stops_chain(self):
        self.add_items()
        data = {'title': 'Bad shop', 'steps': [
            {'type': 'add_shop', 'map_id': 1, 'event_id': 1, 'purchase_only': False, 'goods': [{'type': 'item', 'id': 9, 'price': None}]}]}
        path = self.base / 'bad_shop.json'
        path.write_text(json.dumps(data), encoding='utf-8')
        before = current_inventory(self.game)
        result = self.cli(path)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(current_inventory(self.game), before)
        report = self.report()
        self.assertEqual((report['status'], report['steps'][0]['status']), ('step_failed', 'failed'))
        self.assertIsNone(report['final_copy'])

    def test_smoke_option_with_fake_launcher(self):
        import test_smoke as smoke_tests
        launcher = self.base / 'fake_game.py'
        launcher.write_text(smoke_tests.FAKE_GAME, encoding='utf-8')
        data = {'title': 'One', 'steps': [example()['steps'][0]]}
        path = self.base / 'one.json'
        path.write_text(json.dumps(data), encoding='utf-8')
        result = self.cli(path, '--smoke-mode', 'test', '--smoke-frames', '30', '--smoke-auto-confirm', '2',
                          '--smoke-launcher', json.dumps([sys.executable, str(launcher)]))
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        report = self.report()
        self.assertEqual(report['smoke']['status'], 'pass')
        self.assertTrue((self.work / 'smoke-result.json').is_file())
        self.assertEqual(report['smoke']['result']['frames'], 30)
        self.assertTrue((self.work / 'smoke/copy/Data/Enemies.rvdata2').is_file())

    def test_smoke_suite_requires_mode(self):
        self.assertEqual(self.cli(EXAMPLE, '--smoke-suite', str(EXAMPLE)).returncode, 2)
        self.assertFalse(self.work.exists())


if __name__ == '__main__':
    unittest.main()
