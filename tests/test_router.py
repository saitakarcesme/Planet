"""Controller boundaries: real model decisions are required for every action."""
import contextlib
import io
import json
import time
import unittest
from unittest.mock import Mock, patch
from scripts.bridge import Controller, run
from scripts.desktop import Desktop


def tool(name, **args):
    return {'role': 'assistant', 'tool_calls': [{'id': 't', 'type': 'function',
            'function': {'name': name, 'arguments': json.dumps(args)}}]}


class ControllerTests(unittest.TestCase):
    def test_empty_action_reply_skips_translation_model(self):
        c = self.controller()
        with patch('scripts.bridge.http') as request:
            self.assertEqual(Controller.english(c, ''), '')
        request.assert_not_called()

    def test_action_completion_is_silent_but_requested_information_is_kept(self):
        for route, expected in [('desktop', ''), ('desktop_answer', 'The result is 391.')]:
            c = self.controller()
            c.call = Mock(side_effect=[
                tool('media_status'),
                tool('finish', status='done', message='The result is 391.', evidence='391')])
            c.desktop.media_status.return_value = {'value': '391'}
            with patch('scripts.bridge.decision', return_value=(route, 1)), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(c.run(), (True, expected, 'done'))

    def test_initial_observation_only_uses_confident_observed_window_selection(self):
        for choice, probability, expected in [('w0', .99, True), ('w0', .5, False), ('none', .99, False)]:
            c = self.controller()
            c.desktop.overview.return_value = {'windows': [{'address': '0xa', 'class': 'Native', 'title': 'Document'}]}
            c.desktop.observe.return_value = {'window': {'address': '0xa'}, 'elements': []}
            with patch('scripts.bridge.decision', return_value=(choice, probability)), contextlib.redirect_stdout(io.StringIO()):
                result = c.initial_context()
            self.assertEqual('initial_observation' in result, expected)
            self.assertEqual(c.desktop.observe.called, expected)
            c.desktop.catalog.assert_not_called()

    def test_answer_to_desktop_switch_keeps_fresh_initial_controls(self):
        c = self.controller()
        c.initial_context = Mock(return_value={'initial_observation': {'fresh_control': 'a1:4'}})
        captured = []
        def reply(messages, tools):
            captured.append(json.loads(json.dumps(messages)))
            return (tool('request_desktop') if len(captured) == 1 else
                    tool('finish', status='blocked', message='Missing information.', evidence=''))
        c.call = reply
        with patch('scripts.bridge.decision', return_value=('answer', 1)), contextlib.redirect_stdout(io.StringIO()):
            c.run()
        self.assertIn('a1:4', captured[1][-1]['content'])

    def test_fill_field_rejects_stale_label_before_editing(self):
        d = Desktop.__new__(Desktop)
        node = Mock()
        node.get_name.return_value = 'Actual field'
        d.nodes = {'a1': ('atspi', node, '0xa', [])}
        d.guard = Mock()
        with self.assertRaisesRegex(ValueError, 'label changed'):
            d.fill_field('a1', 'Different field', 'new value', 'Return')
        node.set_text_contents.assert_not_called()
        node.get_component_iface.assert_not_called()

    def test_fill_field_requires_focus_and_rejects_multiline(self):
        d = Desktop.__new__(Desktop)
        node = Mock()
        node.get_name.return_value = 'Search'
        node.get_component_iface.return_value.grab_focus.return_value = False
        d.nodes = {'a1': ('atspi', node, '0xa', [])}
        d.guard = Mock()
        with self.assertRaisesRegex(ValueError, 'focus'):
            d.fill_field('a1', 'Search', 'query', 'Return')
        node.set_text_contents.assert_not_called()
        with self.assertRaisesRegex(ValueError, 'plain-text'):
            d.fill_field('a1', 'Search', 'query\ncommand', 'Return')

    def test_cef_field_waits_for_focus_before_keyboard_replacement(self):
        from scripts.desktop import Atspi
        d = Desktop.__new__(Desktop)
        node = Mock()
        node.get_name.return_value = 'Search'
        node.is_editable_text.return_value = False
        focused = iter([False, True, True])
        node.get_state_set.return_value.contains.side_effect = lambda s: (
            True if s == Atspi.StateType.EDITABLE else next(focused))
        d.nodes = {'a1': ('atspi', node, '0xa', [])}
        d.guard = Mock(return_value={'xwayland': True})
        d.x11 = Mock()
        d.type_text = Mock(return_value={'verified': True})
        with patch('scripts.desktop.time.sleep'):
            result = d.fill_field('a1', 'Search', 'Requested artist', 'Return')
        self.assertTrue(result['verified'])
        d.x11.assert_called_once_with(['key', '--clearmodifiers', 'ctrl+a'])
        d.type_text.assert_called_once_with('0xa', 'Requested artist', 'Return')
        node.set_text_contents.assert_not_called()

    def controller(self):
        desktop = Mock()
        desktop.catalog.return_value = [{'id': 'different.desktop', 'name': 'Different App'}]
        desktop.overview.return_value = {'windows': []}
        desktop.media_status.return_value = {'players': []}
        desktop.describe.return_value = {'window': {'address': '0x1', 'class': 'test'}}
        with patch('scripts.bridge.generator', return_value=('http://localhost/v1', 'test')):
            c = Controller('Open the requested app', desktop=desktop)
        c.english = lambda text: text
        c.confirm_completion = Mock()
        return c

    def test_examples_cannot_execute_without_model(self):
        with patch('scripts.bridge.generator', side_effect=RuntimeError('Model unavailable')), patch('scripts.desktop.Gio.AppInfo.get_all', return_value=[]), patch('subprocess.Popen') as process:
            for text in ['GitHub aç', 'Open Spotify', 'Create a folder', 'github; touch /tmp/planet-injected']:
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    run(text)
                self.assertFalse(json.loads(output.getvalue())['ok'])
            process.assert_not_called()

    def test_unknown_tool_and_extra_arguments_rejected(self):
        c = self.controller()
        for name, args in [('exec', {'command': 'touch /tmp/bad'}), ('launch', {'app_id': 'different.desktop', 'command': 'echo bad'}), ('scroll', {'address': '0x1', 'steps': True})]:
            with self.assertRaises(ValueError): c.validate(name, args)

    def test_no_completion_without_observed_evidence(self):
        c = self.controller()
        c.call = Mock(side_effect=[tool('finish', status='done', message='Opened.', evidence='invented'),
                                  tool('finish', status='blocked', message='Could not verify.', evidence='')])
        with patch('scripts.bridge.decision', return_value=('desktop', 1)), contextlib.redirect_stdout(io.StringIO()):
            result = c.run()
        self.assertFalse(result[0])
        c.desktop.launch.assert_not_called()

    def test_model_selected_generic_app_and_observed_result(self):
        c = self.controller()
        c.desktop.launch.return_value = {'verified': True, 'application': 'Different App'}
        c.call = Mock(side_effect=[tool('launch', app_id='different.desktop'),
                                  tool('finish', status='done', message='Different App is open.', evidence='Different App')])
        with patch('scripts.bridge.decision', side_effect=[('desktop', 1), ('allowed', 1)]), contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(c.run()[0])
        c.desktop.launch.assert_called_once_with(app_id='different.desktop')

    def test_unapproved_step_never_reaches_executor(self):
        c = self.controller()
        c.call = Mock(return_value=tool('assess_step', allowed=False, reason='Not requested.'))
        with patch('scripts.bridge.decision', return_value=('clarify', 1)), self.assertRaises(PermissionError):
            c.execute('launch', {'app_id': 'different.desktop'})
        c.desktop.launch.assert_not_called()

    def test_uncertain_navigation_is_reviewed_against_human_request(self):
        c = self.controller()
        c.call = Mock(return_value=tool('assess_step', allowed=True, reason='Routine requested navigation.'))
        c.desktop.keys.return_value = {'window': {'address': '0x1'}}
        with patch('scripts.bridge.decision', return_value=('clarify', .5)), contextlib.redirect_stdout(io.StringIO()):
            c.execute('keys', {'address':'0x1','keys':'Ctrl+Home'})
        c.desktop.keys.assert_called_once_with(address='0x1',keys='Ctrl+Home')

    def test_malformed_review_never_authorizes_a_step(self):
        c = self.controller()
        c.call = Mock(return_value={'role':'assistant','content':'It is fine.'})
        with patch('scripts.bridge.decision',return_value=('clarify',.6)), self.assertRaises(PermissionError):
            c.execute('launch',{'app_id':'different.desktop'})
        c.desktop.launch.assert_not_called()

    def test_observed_name_alone_does_not_prove_personal_collection(self):
        c=self.controller();c.confirm_completion=Controller.confirm_completion.__get__(c)
        c.trace=[{'kind':'tool','name':'observe','arguments':{},'result':{'text':'Public Playlist — Liked Songs'}}]
        c.call=Mock(return_value=tool('assess_outcome',supported=False,reason='Public playlist, not the personal collection.'))
        with self.assertRaisesRegex(ValueError,'not verified'):
            c.confirm_completion('Opened your liked collection.','Liked Songs')

    def test_public_scope_contradiction_cannot_be_overruled_by_generator(self):
        c=self.controller();c.confirm_completion=Controller.confirm_completion.__get__(c)
        c.trace=[{'kind':'tool','name':'observe','arguments':{},'result':{'elements':[{'text':'Public Playlist'},{'text':'Liked Songs'}]}}]
        c.call=Mock(return_value=tool('assess_outcome',supported=True,reason='A matching name.'))
        with patch('scripts.bridge.decision',return_value=('personal',1)), self.assertRaisesRegex(ValueError,'Public Playlist'):
            c.confirm_completion('Opened your personal collection.','Liked Songs')
        c.call.assert_not_called()

    def test_completion_retains_collection_context_after_media_polling(self):
        c = self.controller()
        c.confirm_completion = Controller.confirm_completion.__get__(c)
        c.trace = [{'kind': 'tool', 'name': 'observe', 'arguments': {}, 'result': {
            'elements': [{'id': 'a1:0', 'role': 'table', 'name': 'Personal collection', 'context': ['library: Mine']}]
        }}] + [{'kind': 'tool', 'name': 'media_status', 'arguments': {}, 'result': {'state': 'Playing'}} for _ in range(5)]
        c.call = Mock(return_value=tool('assess_outcome', supported=True, reason='Verified.'))
        c.confirm_completion('Playing.', 'Playing')
        self.assertIn('Personal collection', c.call.call_args.args[0][1]['content'])

    def test_parallel_calls_do_not_execute(self):
        c = self.controller()
        multiple = tool('launch', app_id='different.desktop')
        multiple['tool_calls'] *= 2
        c.call = Mock(side_effect=[multiple, tool('finish', status='blocked', message='Stopped.', evidence='')])
        with patch('scripts.bridge.decision', return_value=('desktop', 1)), contextlib.redirect_stdout(io.StringIO()):
            c.run()
        c.desktop.launch.assert_not_called()

    def test_non_english_response_is_translated_without_new_actions(self):
        c = self.controller()
        c.english = Controller.english.__get__(c)
        with patch('scripts.bridge.decision', return_value=('rewrite', 1)), patch('scripts.bridge.http', return_value={
                'choices': [{'message': {'content': 'Opened the Günlük Notlar folder.'}}]}) as request:
            self.assertEqual(c.english('Günlük Notlar klasörü açıldı.'), 'Opened the Günlük Notlar folder.')
        self.assertNotIn('tools', request.call_args.args[1])
        c.desktop.launch.assert_not_called()


class DesktopBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.d = Desktop.__new__(Desktop)
        self.d.apps = {}; self.d.nodes = {}; self.d.observed = {}

    def test_no_browser_fallback_or_unregistered_launch(self):
        with patch('subprocess.Popen') as p, self.assertRaises(ValueError):
            self.d.launch('https://example.com')
        p.assert_not_called()

    def test_stale_control_does_not_click(self):
        with self.assertRaises(ValueError): self.d.click('old-id')

    def test_focus_change_prevents_typing(self):
        w = {'address': '0x1', 'at': [0, 0], 'size': [400, 400]}
        self.d.observed['0x1'] = {**w, 'time': time.monotonic()}
        with patch.object(self.d, 'window', return_value=w), patch('scripts.desktop.hypr', return_value={'address': '0x2'}), patch('scripts.desktop.command') as cmd:
            with self.assertRaises(ValueError): self.d.type_text('0x1', 'hello')
            cmd.assert_not_called()

    def test_folder_outside_home_is_rejected(self):
        with self.assertRaises(ValueError): self.d.mkdir('/etc/planet-test')

    def test_label_mismatch_does_not_activate_control(self):
        node = Mock();node.get_name.return_value = 'Cancel'
        self.d.nodes['a1:button:cancel:2'] = ('atspi', node, '0x1', ['Press'])
        with patch.object(self.d, 'guard'), self.assertRaises(ValueError):
            self.d.click('a1:button:cancel:2', 'Press', 'Save')
        node.do_action.assert_not_called()

    def test_unverified_launch_is_not_repeated(self):
        app = Mock();app.get_executable.return_value = 'test-app'
        app.get_startup_wm_class.return_value = 'TestApp';app.get_name.return_value = 'Test App'
        self.d.apps = {'test.desktop': app};self.d.launch_attempts = {'test.desktop'}
        with patch.object(self.d, 'windows', return_value=[]):
            result = self.d.launch('test.desktop')
        self.assertFalse(result['verified'])
        app.launch_uris_as_manager_with_fds.assert_not_called()

    def test_unobserved_media_player_cannot_be_controlled(self):
        with patch.object(self.d, 'bus_call') as bus, self.assertRaises(ValueError):
            self.d.media_control('org.mpris.MediaPlayer2.invented', 'Play')
        bus.assert_not_called()

    def test_media_wait_requires_chosen_title_and_advancing_playback(self):
        self.d.players = {'player': {}}
        def status(title, position):
            return {'players': [{'player': 'player', 'title': title, 'state': 'Playing',
                                 'track_id': '/track/chosen' if title == 'Chosen' else '/track/old',
                                 'position_us': position}]}
        with patch.object(self.d, 'media_status', side_effect=[
            status('Old', 900000), status('Chosen', 0), status('Chosen', 400000)
        ]), patch.object(self.d, 'bus_call') as mutation, patch('scripts.desktop.time.sleep'):
            result = self.d.wait_for_media('player', 'Chosen', 'Playing', 3)
        self.assertTrue(result['verified'])
        self.assertEqual(result['position_advanced_us'], 400000)
        mutation.assert_not_called()

    def test_media_wait_does_not_accept_wrong_track_or_stationary_position(self):
        self.d.players = {'player': {}}
        status = {'players': [{'player': 'player', 'title': 'Chosen', 'state': 'Playing',
                               'track_id': '/track/chosen', 'position_us': 0}]}
        with patch.object(self.d, 'media_status', return_value=status), patch('scripts.desktop.time.sleep'), \
             patch('scripts.desktop.time.monotonic', side_effect=[0, 0, 2]):
            self.assertFalse(self.d.wait_for_media('player', 'Chosen', 'Playing', 1)['verified'])

    def test_unreadable_search_is_not_reported_as_complete(self):
        def walk(path, followlinks, onerror):
            onerror(PermissionError('private directory'))
            return iter([])
        with patch('scripts.desktop.os.walk', side_effect=walk):
            from pathlib import Path
            result = self.d.find_files('missing', str(Path.home()), 'folder')
        self.assertFalse(result['complete'])
        self.assertEqual(result['unreadable_directories'], 1)

    def test_new_application_dialog_is_observed_without_refocusing_parent(self):
        with patch('scripts.desktop.hypr',return_value={'address':'0x2','pid':42}), patch.object(self.d,'window',return_value={'pid':42}), patch.object(self.d,'observe') as observe, patch('scripts.desktop.time.sleep'):
            self.d.after_input('0x1')
        observe.assert_called_once_with('0x2')

    def test_xwayland_text_uses_x11_transport(self):
        with patch.object(self.d,'guard',return_value={'xwayland':True}), patch.object(self.d,'after_input'), patch.object(self.d,'x11') as x11, patch('scripts.desktop.command') as wayland, patch('scripts.desktop.time.sleep'):
            self.d.type_text('0x1','A note: Günlük','')
        self.assertEqual(x11.call_args.args[0][-1],'A note: Günlük')
        wayland.assert_not_called()

    def test_conventional_uppercase_shortcut_spelling(self):
        with patch.object(self.d, 'guard', return_value={'xwayland': True}), \
             patch.object(self.d, 'after_input'), patch.object(self.d, 'x11') as x11, \
             patch('scripts.desktop.time.sleep'):
            self.d.keys('0x1', 'Ctrl+Shift+S')
        self.assertEqual(x11.call_args.args[0][-1], 'ctrl+shift+s')

    def test_saved_file_verification_checks_content_not_just_filename(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory(dir=Path.home()) as folder:
            path = Path(folder)/'result.txt'
            path.write_text('\ufeffRequested line\r\n', encoding='utf-8')
            self.assertTrue(self.d.verify_text_file(str(path), 'Requested line')['verified'])
            self.assertFalse(self.d.verify_text_file(str(path), 'Different line')['verified'])
            self.assertFalse(self.d.verify_text_file(str(path.with_name('missing.txt')), 'Requested line')['verified'])
            self.assertNotIn('content', self.d.verify_text_file(str(path), 'Requested line'))
            path.write_text('Requested line\n\n')
            self.assertFalse(self.d.verify_text_file(str(path), 'Requested line')['verified'])


if __name__ == '__main__': unittest.main()
