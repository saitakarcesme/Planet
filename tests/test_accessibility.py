import types
import unittest
from scripts.accessibility import snapshot, has_readable_content
from scripts.bridge import model_data


class Node:
    def __init__(self, role='panel', name='', children=(), showing=True, text='', actions=()):
        self.role, self.name, self.children = role, name, list(children)
        self.showing, self.text, self.actions = showing, text, actions

    def get_role_name(self): return self.role
    def get_name(self): return self.name
    def get_state_set(self):
        return types.SimpleNamespace(contains=lambda state: self.showing if state == 'showing' else False)
    def is_action(self): return bool(self.actions)
    def get_n_actions(self): return len(self.actions)
    def get_action_name(self, i): return self.actions[i]
    def is_editable_text(self): return self.role == 'entry'
    def is_text(self): return bool(self.text)
    def get_text_iface(self): return self
    def get_character_count(self): return len(self.text)
    def get_text(self): raise AssertionError('Wrong GI interface: use Atspi.Text.get_text')
    def get_child_count(self): return len(self.children)
    def get_child_at_index(self, i): return self.children[i]


API = types.SimpleNamespace(
    StateType=types.SimpleNamespace(SHOWING='showing', FOCUSED='focused', SELECTED='selected'),
    Text=types.SimpleNamespace(get_text=lambda node, start, end: node.text[start:end]))


class AccessibilityTests(unittest.TestCase):
    def test_button_only_tree_still_requires_ocr_for_custom_readout(self):
        self.assertFalse(has_readable_content([{'role': 'button', 'name': 'Equals'},
                                               {'role': 'button', 'name': '7'}]))
        self.assertTrue(has_readable_content([{'role': 'label', 'name': '391'}]))

    def test_deep_native_controls_and_explicit_text_interface(self):
        button = Node('button', 'Open personal collection', text='Open personal collection', actions=('press',))
        root = button
        for _ in range(22):
            root = Node(children=[root])
        root = Node('table', 'My library', [root])
        nodes = {}
        items, truncated = snapshot(root, API, 1, '0x1', nodes)
        found = next(item for item in items if item['role'] == 'button')
        self.assertEqual(found['context'], ['table: My library'])
        self.assertEqual(found['actions'], ['press'])
        self.assertIs(nodes[found['id']][1], button)
        self.assertFalse(truncated)

    def test_hidden_rows_and_passwords_never_expose_controls(self):
        root = Node(children=[
            Node('table row', 'Offscreen', [Node('button', 'Hidden action', actions=('press',))], showing=False),
            Node('password text', 'Secret', text='private'),
            Node('button', 'Visible', actions=('press',)),
        ])
        nodes = {}
        items, _ = snapshot(root, API, 1, '0x1', nodes)
        self.assertEqual([item['name'] for item in items], ['Visible'])
        self.assertEqual(len(nodes), 1)

    def test_snapshot_limit_is_explicit(self):
        root = Node(children=[Node('button', str(i), actions=('press',)) for i in range(10)])
        items, truncated = snapshot(root, API, 1, '0x1', {}, limit=3)
        self.assertEqual(len(items), 3)
        self.assertTrue(truncated)

    def test_prompt_compaction_preserves_scope_values_and_action_identity(self):
        result = {'window': {'address': '0x1'}, 'elements': [
            {'id': 'a1:0', 'role': 'button', 'name': 'Play chosen song',
             'actions': ['press'], 'context': ['table: My collection']},
            {'id': 'a1:1', 'role': 'entry', 'name': 'File name', 'text': '/home/test/new.txt',
             'editable': True, 'focused': True, 'context': ['dialog: Save']}
        ]}
        data = model_data(result)
        self.assertEqual(data['controls'][0]['within'], ['table: My collection'])
        self.assertEqual(data['controls'][0]['rows'][0][0], 'a1:0')
        self.assertEqual(data['controls'][1]['rows'][0][3], '/home/test/new.txt')
        self.assertIn('focused', data['controls'][1]['rows'][0][5])
        self.assertIn('elements', result)  # Private evidence is not mutated.

    def test_large_ui_is_bounded_and_can_request_narrower_inspection(self):
        result = {'elements': [
            {'id': f'a1:{i}', 'role': 'button', 'name': 'A long observed label ' * 12,
             'actions': ['press'], 'context': [f'table: Region {i % 5}']}
            for i in range(240)]}
        import json
        compact = model_data(result)
        self.assertGreater(compact['omitted_controls'], 0)
        self.assertLess(len(json.dumps(compact, ensure_ascii=False)), 20000)
        self.assertEqual(len(compact['controls']), 5)


if __name__ == '__main__':
    unittest.main()
