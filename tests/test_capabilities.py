import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from scripts.skills import SKILLS, BY_ID, match, validate
from scripts.fast import select, direct_plan, resolved_plan
from scripts.capabilities import Executor, CapabilityError, calculate

class CapabilitiesTests(unittest.TestCase):
    def test_catalog_has_100_distinct_executable_recipes(self):
        self.assertEqual(len(BY_ID),100)
        expected={'app':2,'window':18,'media':15,'files':15,'system':15,'workspace':5,'monitor':5,'dev':10,'search':10,'helper':5}
        self.assertEqual({g:sum(s['id'].startswith(g+'.') for s in SKILLS) for g in expected},expected)
        for s in SKILLS:self.assertTrue(callable(getattr(Executor,s['id'].split('.')[0])))

    def test_all_documented_aliases_select_their_intended_capability(self):
        samples={'app':'Spotify','path':'/home/test/My Project','query':'Queen','percent':30,'number':2,'expression':'17 * 23','text':'test note','minutes':1}
        for s in SKILLS:
            for alias in s['aliases']:
                with self.subTest(skill=s['id'],alias=alias):
                    id,args=match(alias.format(**samples));self.assertEqual(id,s['id']);validate(id,args)

    def test_unknown_or_compound_requests_do_not_partially_execute(self):
        for text in ['open Spotify and delete my files','pause music; send an email','create folder /tmp/a\nshutdown','foo', 'open Spotify then play ABBA','sesi ac ve muzigi durdur']:
            self.assertIsNone(match(text))

    def test_original_unicode_paths_and_note_punctuation_are_preserved(self):
        self.assertEqual(match('Şu not'),None)
        self.assertEqual(match('create folder /home/test/Çağrı'),('files.mkdir',{'path':'/home/test/Çağrı'}))
        self.assertEqual(match('not al Çağrı!'),('helper.note',{'text':'Çağrı!'}))

    def test_recognized_chains_are_all_or_nothing(self):
        self.assertEqual(direct_plan('calculate 2+3 and calculate 7*8'), [
            ('helper.calculate', {'expression':'2+3'}, 'alias-chain'),
            ('helper.calculate', {'expression':'7*8'}, 'alias-chain')])
        self.assertIsNone(direct_plan('open Spotify and delete my files'))
        self.assertIsNone(direct_plan(' and '.join(['pause music']*5)))

    def test_decomposed_unicode_is_preserved(self):
        self.assertEqual(match('note Cafe\u0301'), ('helper.note', {'text':'Cafe\u0301'}))

    def test_specific_aliases_win_over_generic_app_or_music_patterns(self):
        self.assertEqual(match('sesi aç')[0],'system.unmute')
        self.assertEqual(match('müzik çal')[0],'media.play')
        self.assertEqual(match('ev klasörünü aç')[0],'files.home')
        self.assertEqual(match('spotifydan ABBA şarkısı aç bir tane'),('media.search',{'query':'ABBA'}))

    def test_validation_rejects_unknown_tools_extra_keys_and_bad_types(self):
        for id,args in [('shell',{}),('app.open',{'app':'Spotify','command':'rm'}),('system.volume',{'percent':True}),('system.volume',{'percent':-1}),('files.open',{'path':'a\nb'})]:
            with self.assertRaises(ValueError):validate(id,args)

    def test_direct_alias_does_not_call_models(self):
        model=Mock(side_effect=AssertionError('No model needed'))
        self.assertEqual(select('pause music',model,model),('media.pause',{},'alias'))

    def test_search_wildcard_cannot_swallow_collection_or_conditions(self):
        for text in ['Play a song from my liked songs on Spotify',
                     'play ABBA without live recordings on spotify',
                     'play songs by ABBA on spotify',
                     'play my workout playlist on spotify']:
            with self.subTest(text=text):
                self.assertIsNone(match(text))

    def test_semantic_unspecified_music_needs_no_generator(self):
        decision=Mock(side_effect=[('media.search',.99),('resume',.99)])
        generate=Mock(side_effect=AssertionError('No named target to extract'))
        self.assertEqual(select('Can you put something on in Spotify?',decision,generate),
                         ('media.search',{'query':'some music'},'semantic'))

    def test_semantic_music_conditions_cannot_be_dropped(self):
        for scope,confidence in [('other',.99),('resume',.8)]:
            decision=Mock(side_effect=[('media.search',.99),(scope,confidence)])
            self.assertIsNone(select('Play something relaxing without vocals',decision,Mock()))

    def test_unresolved_app_slot_goes_to_planner_before_execution(self):
        with patch('scripts.fast.Executor') as executor:
            executor.return_value.app_id.side_effect=CapabilityError('Not exact')
            self.assertIsNone(resolved_plan('open Spotify please'))
            executor.return_value.run.assert_not_called()

    def test_resolved_app_remains_a_direct_native_action(self):
        with patch('scripts.fast.Executor') as executor:
            executor.return_value.app_id.return_value='spotify.desktop'
            self.assertEqual(resolved_plan('open Spotify'),[('app.open',{'app':'Spotify'},'alias')])
            executor.return_value.run.assert_not_called()

    def test_uncertain_semantic_routing_falls_back_without_execution(self):
        self.assertIsNone(select('some task',lambda *a:('media.pause',.7)))
        self.assertIsNone(select('some task',lambda *a:('other',1)))
        self.assertIsNone(select('some task',lambda *a:('app.open',1),lambda *a:None))

    def test_calculator_is_bounded_and_cannot_execute_python(self):
        self.assertEqual(calculate('17 * 23'),391)
        self.assertEqual(calculate('-(5+3)/2'),-4)
        for text in ['__import__("os").system("true")','2 ** 99999','[1]*1000000','True','(1).__class__']:
            with self.assertRaises((CapabilityError,ValueError)):calculate(text)

    def test_file_write_never_overwrites_existing_note(self):
        with tempfile.TemporaryDirectory() as folder,patch('scripts.capabilities.DATA',Path(folder)):
            e=Executor(desktop=Mock())
            first=e.run('helper.note',{'text':'first'})
            second=e.run('helper.note',{'text':'second'})
            self.assertNotEqual(first['path'],second['path'])
            self.assertEqual(Path(first['path']).read_text(),'first\n')
            self.assertEqual(Path(second['path']).read_text(),'second\n')

    def test_out_of_range_volume_does_not_mutate_audio(self):
        e=Executor(desktop=Mock())
        with patch('scripts.capabilities.command',return_value='Volume: 0.50') as cmd:
            with self.assertRaises(CapabilityError):e.run('system.volume',{'percent':120})
            self.assertEqual(cmd.call_count,1)

    def test_unverified_handler_result_cannot_be_success(self):
        e=Executor(desktop=Mock());e.app=Mock(return_value={'verified':False,'note':'No window'})
        with self.assertRaisesRegex(CapabilityError,'No window'):e.run('app.open',{'app':'Spotify'})

if __name__=='__main__':unittest.main()
