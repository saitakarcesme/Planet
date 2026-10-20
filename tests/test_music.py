import unittest
from unittest.mock import Mock,patch
from scripts.music import play_selection,playing_progress,wait_for_controls,ensure_spotify_controls
from scripts.capabilities import CapabilityError,Executor
from scripts.skills import match

class MusicTests(unittest.TestCase):
    def test_unspecified_music_resumes_without_literal_search(self):
        for query in ['some music','something','bir şey','bir şarkı']:
            d=Mock();d.apps={'spotify.desktop':Mock()};d.launch.return_value={'verified':True,'window':{'address':'0x1'}}
            d.media_status.return_value={'players':[{'name':'Spotify'}]}
            with patch('scripts.music.playing_progress',return_value={'verified':True}):
                self.assertTrue(play_selection(d,query)['verified'])
            d.fill_field.assert_not_called();d.observe.assert_not_called();d.launch.assert_not_called()
            self.assertEqual(d.bus_call.call_args.args[-1],'Play')

    def test_turkish_spotify_requests_keep_music_scope(self):
        for text in ["Spotify'da bir şey çal", 'Spotifyda bir şarkı aç']:
            id,args=match(text)
            self.assertEqual(id,'media.search')
            self.assertTrue(args['query'].startswith('bir '))

    def test_playing_without_position_progress_is_not_success(self):
        d=Mock();d.media_status.return_value={'players':[{'name':'Spotify','state':'Playing','title':'Song','track_id':'1','position_us':42}]}
        self.assertIsNone(playing_progress(d,lambda p:True,seconds=0))

    def test_position_progress_checks_same_track(self):
        d=Mock();d.media_status.side_effect=[{'players':[{'name':'Spotify','state':'Playing','track_id':'1','position_us':1}]},{'players':[{'name':'Spotify','state':'Playing','track_id':'1','position_us':200001}]}]
        with patch('scripts.music.time.sleep'):
            self.assertTrue(playing_progress(d,lambda p:True)['verified'])

    def test_controls_wait_for_actual_ready_tree(self):
        d=Mock();d.observe.side_effect=[{'elements':[]},{'elements':[{'name':'ready','id':'fresh'}]}]
        with patch('scripts.music.time.sleep'):
            observation,control=wait_for_controls(d,'0x1',{'elements':[]},lambda ns:ns,'Missing')
        self.assertEqual(control['id'],'fresh');self.assertEqual(d.observe.call_count,2)

    def test_ambiguous_controls_are_not_clicked(self):
        d=Mock()
        with self.assertRaises(CapabilityError):wait_for_controls(d,'0x1',{'elements':[{},{}]},lambda ns:ns,'Missing')
        d.click.assert_not_called()

    def test_healthy_accessibility_does_not_restart_spotify(self):
        d=Mock();d.accessibility_registered.return_value=True
        self.assertEqual(ensure_spotify_controls(d,'0x1'),'0x1');d.bus_call.assert_not_called()

    def test_missing_accessibility_restarts_once_then_verifies_new_process(self):
        d=Mock();d.accessibility_registered.side_effect=[False,True]
        d.apps={'spotify.desktop':Mock()};d.apps['spotify.desktop'].get_commandline.return_value='spotify --force-renderer-accessibility'
        d.windows.return_value=[];d.launch.return_value={'verified':True,'window':{'address':'0x2'}}
        with patch('scripts.music.time.monotonic',side_effect=[0,1,2,3]):
            self.assertEqual(ensure_spotify_controls(d,'0x1'),'0x2')
        d.launch.assert_called_once_with('spotify.desktop');d.bus_call.assert_called_once()
        self.assertEqual(d.bus_call.call_args.args[-1],'Quit')

    def test_unconfigured_app_is_not_blindly_restarted(self):
        d=Mock();d.accessibility_registered.return_value=False
        d.apps={'spotify.desktop':Mock()};d.apps['spotify.desktop'].get_commandline.return_value='spotify'
        with patch('scripts.music.time.monotonic',side_effect=[0,1]):
            with self.assertRaises(CapabilityError):ensure_spotify_controls(d,'0x1')
        d.bus_call.assert_not_called();d.launch.assert_not_called()

    def test_app_suffix_resolves_catalog_not_invented_executable(self):
        d=Mock();d.catalog.return_value=[{'id':'chatgpt.desktop','name':'ChatGPT'}]
        e=Executor(d)
        for name in ['chatgpt app','the ChatGPT application','ChatGPT uygulaması']:
            self.assertEqual(e.app_id(name),'chatgpt.desktop')

if __name__=='__main__':unittest.main()
