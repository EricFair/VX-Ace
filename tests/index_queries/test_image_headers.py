import json
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from vxace_image_headers import png_header, read_header, layout_checks, PNG_SIGNATURE
from vxace_asset_audit import audit, review_required, main
import test_asset_audit as fixtures


def ihdr(width=384, height=256, depth=8, color=6, compression=0, filtering=0, interlace=0):
    payload = b'IHDR' + struct.pack('>IIBBBBB', width, height, depth, color, compression, filtering, interlace)
    return PNG_SIGNATURE + struct.pack('>I', 13) + payload + struct.pack('>I', zlib.crc32(payload) & 0xffffffff)


class PNGHeaderTests(unittest.TestCase):
    def test_header_dimensions_do_not_require_or_claim_pixel_decoding(self):
        result = png_header(ihdr(768, 512))
        self.assertEqual((result['width'], result['height']), (768, 512))
        self.assertNotIn('decoded', result)

    def test_truncated_signature_and_wrong_first_chunk_are_refused(self):
        for raw in (b'', ihdr()[:32], b'not a png' + b'0' * 24,
                    ihdr()[:8] + b'\x00\x00\x00\x0dIDAT' + ihdr()[16:]):
            with self.subTest(raw=raw), self.assertRaises(ValueError): png_header(raw)

    def test_crc_is_checked_before_dimensions_are_trusted(self):
        raw = bytearray(ihdr()); raw[19] ^= 1
        with self.assertRaisesRegex(ValueError, 'checksum'): png_header(bytes(raw))

    def test_illegal_dimensions_and_header_fields_are_refused(self):
        for fields in ({'width': 0}, {'height': 0}, {'width': 2**31}, {'height': 2**31},
                       {'color': 1}, {'depth': 4, 'color': 6}, {'color': 3, 'depth': 16},
                       {'compression': 1}, {'filtering': 1}, {'interlace': 2}):
            with self.subTest(fields=fields), self.assertRaises(ValueError): png_header(ihdr(**fields))

    def test_legal_paletted_and_interlaced_headers_are_observed(self):
        self.assertEqual(png_header(ihdr(color=3, depth=4))['color_type'], 3)
        self.assertEqual(png_header(ihdr(interlace=1))['interlace'], 1)

    def test_character_prefix_matches_default_rgss3_reference_semantics(self):
        header = {'status': 'header_observed', 'width': 96, 'height': 128}
        for name, single in (('$Hero', True), ('!$Door', True), ('$!Door', True),
                             ('!Door', False), ('Hero$', False), ('nested/$Hero', False), ('$', False)):
            result = layout_checks('Graphics/Characters', name, header)[0]
            self.assertEqual(result['columns'], 3 if single else 12, name)
            self.assertEqual(result['default_frame_width'], 32 if single else 8)

    def test_irregular_and_too_small_character_grids_report_truncation(self):
        for width, height in ((13, 9), (11, 7), (384, 255)):
            result = layout_checks('Graphics/Characters', 'Hero', {'status': 'header_observed', 'width': width, 'height': height})[0]
            self.assertEqual(result['status'], 'character_grid_remainder')

    def test_standard_tileset_slots_and_nonstandard_sizes_are_advisory(self):
        for slot, size in enumerate(((512,384),(512,384),(512,256),(512,480),(256,512),*( [(512,512)] * 4))):
            result = layout_checks('Graphics/Tilesets', 'AnyName', {'status': 'header_observed', 'width': size[0], 'height': size[1]}, [slot])[0]
            self.assertEqual(result['status'], 'standard_layout')
        result = layout_checks('Graphics/Tilesets', 'AnyName', {'status': 'header_observed', 'width': 32, 'height': 32}, [5])[0]
        self.assertEqual(result['status'], 'nonstandard_tileset_dimensions')
        with self.assertRaises(ValueError): layout_checks('Graphics/Tilesets', 'AnyName', {'status': 'header_observed', 'width': 32, 'height': 32}, [9])


# Reuse only fixture helpers, not the other test methods (avoids duplicate suites).
class ImageAuditIntegrationTests(unittest.TestCase):
    setUp = fixtures.AssetAuditTests.setUp
    write = fixtures.AssetAuditTests.write
    refresh = fixtures.AssetAuditTests.refresh
    asset = fixtures.AssetAuditTests.asset

    def png(self, relative, raw=None):
        file = self.asset(self.rtp, relative)
        file.write_bytes(ihdr() if raw is None else raw)
        return file

    def test_header_feature_is_opt_in_and_invalid_png_requires_review(self):
        self.png('Graphics/Characters/Hero.png', b'not a png')
        self.assertFalse(review_required(audit(self.index, self.game, self.rtp)))
        result = audit(self.index, self.game, self.rtp, True)
        self.assertEqual(result['counts'], {'found': 1})
        self.assertEqual(result['image_counts'], {'invalid_png_header': 1})
        self.assertTrue(review_required(result))
        with self.assertRaises(ValueError): audit(self.index, self.game, self.rtp, 'true')

    def test_header_only_png_still_does_not_establish_full_validity(self):
        self.png('Graphics/Characters/Hero.png')
        result = audit(self.index, self.game, self.rtp, True)
        self.assertEqual(result['image_counts'], {'header_observed': 1})
        self.assertEqual(result['layout_counts'], {'standard_layout': 1})
        self.assertFalse(review_required(result))
        self.assertTrue(any('pixel data' in x for x in result['limits']))

    def test_unsupported_jpeg_header_is_explicitly_uncertain(self):
        self.asset(self.rtp, 'Graphics/Characters/Hero.jpg')
        result = audit(self.index, self.game, self.rtp, True)
        self.assertEqual(result['image_counts'], {'unsupported_header_format': 1})
        self.assertTrue(review_required(result))

    def test_reads_only_33_bytes_even_for_large_payload(self):
        file = self.png('Graphics/Characters/Hero.png', ihdr() + b'not decoded' * 10000)
        header, digest = read_header(file)
        import hashlib
        self.assertEqual(digest, hashlib.sha256(ihdr()).hexdigest())
        self.assertEqual(header['width'], 384)

    def test_changed_header_with_same_metadata_is_detected_at_final_recheck(self):
        file = self.png('Graphics/Characters/Hero.png')
        import os
        stamp = file.stat()
        from vxace_index_query import Index
        data = Index(self.index)
        def change():
            file.write_bytes(ihdr(768, 512))
            os.utime(file, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        data.unchanged = change
        with self.assertRaisesRegex(ValueError, 'header changed'):
            audit(data, self.game, self.rtp, True)

    def test_tileset_all_roles_retained_beyond_three_evidence_samples(self):
        self.write('database/actors.json', [{'__class__': 'RPG::Tileset', 'tileset_names': ['Shared'] * 9}])
        self.png('Graphics/Tilesets/Shared.png', ihdr(512, 512))
        row = audit(self.index, self.game, self.rtp, True)['references'][0]
        self.assertEqual(len(row['evidence']), 3)
        self.assertEqual(len(row['layout_checks']), 9)
        self.assertEqual(sum(c['status'] == 'standard_layout' for c in row['layout_checks']), 4)

    def test_audio_and_ambiguous_graphics_are_not_opened_as_headers(self):
        self.asset(self.rtp, 'Graphics/Characters/Hero.png'); self.asset(self.rtp, 'Graphics/Characters/Hero.jpg')
        self.write('database/actors.json', [self.actors[1], {'__class__': 'RPG::SE', 'name': 'Chime'}])
        self.asset(self.rtp, 'Audio/SE/Chime.wav')
        with patch('vxace_asset_audit.read_header', side_effect=AssertionError('Unexpected open')):
            result = audit(self.index, self.game, self.rtp, True)
        self.assertEqual(result['image_counts'], {})

    def test_cli_layout_warning_keeps_presence_and_never_changes_source(self):
        self.png('Graphics/Characters/Hero.png', ihdr(13, 9))
        from vxace_copy_patcher import current_inventory
        before = [current_inventory(p) for p in (self.game, self.rtp, self.index)]
        output = self.base / 'report'
        self.assertEqual(main([str(self.index), '--project', str(self.game), '--rtp', str(self.rtp),
                               '--image-headers', '--output', str(output)]), 3)
        result = json.loads((output / 'asset-audit.json').read_text())
        self.assertEqual(result['counts'], {'found': 1})
        self.assertEqual(result['layout_counts'], {'character_grid_remainder': 1})
        self.assertEqual(before, [current_inventory(p) for p in (self.game, self.rtp, self.index)])


if __name__ == '__main__':
    unittest.main()
