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
    def controller(self):
        desktop = Mock()
        desktop.catalog.return_value = [{'id': 'different.desktop', 'name': 'Different App'}]
        desktop.overview.return_value = {'windows': []}
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


if __name__ == '__main__': unittest.main()
