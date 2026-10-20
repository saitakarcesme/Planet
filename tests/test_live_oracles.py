"""Collection acceptance must verify ownership and table membership, not a title."""
import unittest
from unittest.mock import Mock, patch
from live_suite import native_collection_proof


def node(role, name, *children):
    result = Mock()
    result.get_role_name.return_value = role
    result.get_name.return_value = name
    result.get_child_count.return_value = len(children)
    result.get_child_at_index.side_effect = lambda index: children[index]
    return result


class CollectionOracleTests(unittest.TestCase):
    def proof(self, public=False, owner='Me', track_in_table=True):
        library = node('landmark', 'Main', node('table', 'Your Library',
                       node('button', 'Liked Songs Pinned Playlist • Me')))
        table = node('table', 'Liked Songs',
                     node('table row', 'Play Chosen Track by Artist' if track_in_table else 'Another item'))
        page = node('landmark', 'Spotify – Liked Songs',
                    node('static', 'Public Playlist' if public else 'Playlist'), node('link', owner), table)
        footer = node('landmark', 'Now playing view', node('link', 'Chosen Track'))
        frame = node('frame', 'Player', library, page, footer)
        app = node('application', 'Native player', frame)
        app.get_process_id.return_value = 7
        desktop = Mock()
        desktop.window.return_value = {'address': '0x1', 'pid': 7, 'title': 'Player'}
        with patch('live_suite.Atspi.get_desktop', return_value=[app]):
            return native_collection_proof(desktop, {'address': '0x1'}, 'Liked Songs', 'Chosen Track')

    def test_personal_collection_header_and_track_table(self):
        result = self.proof()
        self.assertTrue(result['personal_collection_verified'])
        self.assertTrue(result['track_observed'])
        self.assertTrue(result['complete'])

    def test_public_same_title_is_not_personal_collection(self):
        self.assertFalse(self.proof(public=True)['personal_collection_verified'])

    def test_different_owner_does_not_verify_personal_collection(self):
        self.assertFalse(self.proof(owner='Someone else')['personal_collection_verified'])

    def test_now_playing_footer_does_not_prove_membership(self):
        result = self.proof(track_in_table=False)
        self.assertTrue(result['personal_collection_verified'])
        self.assertFalse(result['track_observed'])


if __name__ == '__main__':
    unittest.main()
