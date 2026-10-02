"""Behavioral input-boundary regression tests; all raster inputs are test fixtures."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent / 'runtime/src'))
from ornamentforge.current.input.router import InputRouter
from ornamentforge.current.cli import main
from ornamentforge.current.design import DesignHandoff
from ornamentforge.current.planar.contract import PlanarMasterV1
from jsonschema import ValidationError
from PIL import Image, ImageDraw


class InputRoutes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.source = self.work / 'fixture.png'
        image = Image.new('RGB', (100, 100), 'white')
        ImageDraw.Draw(image).ellipse((25, 25, 75, 75), fill=(60, 130, 160))
        image.save(self.source)
        self.router = InputRouter(self.work)

    def reference(self, **kwargs):
        return self.router.route(reference_images=[self.source],
                                 reference_options={'reference_mode': 'color_block'}, **kwargs)

    def test_prompt_without_tool_holds(self):
        result = self.router.route(prompt='莲花团花')
        self.assertEqual((result.code, result.status, result.master),
                         ('AI_IMAGE_TOOL_UNAVAILABLE', 'HOLD', None))
        self.assertEqual(list(self.work.iterdir()), [self.source])

    def test_declared_tool_still_requires_selected_image(self):
        result = self.router.route(prompt='lotus', image_tool_available=True)
        self.assertEqual((result.code, result.status, result.master),
                         ('AI_IMAGE_GENERATION_REQUIRED', 'HOLD', None))

    def test_empty_input_holds(self):
        self.assertEqual(self.router.route().status, 'HOLD')

    def test_reference_reconstructs(self):
        result = self.reference()
        self.assertEqual(result.status, 'READY')
        self.assertEqual(result.master.to_dict()['route'], 'FIDELITY_RECONSTRUCTION')

    def test_reference_precedes_prompt_and_spec(self):
        result = self.reference(prompt='completely different subject', spec={'invalid': True})
        self.assertEqual(result.master.to_dict(), self.reference().master.to_dict())

    def test_missing_reference_holds(self):
        result = self.router.route(reference_images=['missing.png'], prompt='lotus')
        self.assertEqual((result.status, result.master), ('HOLD', None))

    def test_corrupt_reference_holds(self):
        self.source.write_bytes(b'corrupt')
        result = self.reference(prompt='lotus')
        self.assertEqual((result.status, result.master), ('HOLD', None))

    def test_multiple_references_stop(self):
        result = self.router.route(reference_images=[self.source, self.source])
        self.assertEqual((result.code, result.status), ('MULTI_REFERENCE', 'NOT_SUPPORTED'))

    def test_unsupported_format_stops(self):
        result = self.router.route(reference_images=['reference.svg'])
        self.assertEqual((result.code, result.status), ('REFERENCE_FORMAT', 'NOT_SUPPORTED'))

    def test_invalid_scale_holds(self):
        self.assertEqual(self.reference(millimeters_per_unit=-1).code, 'INVALID_SCALE')

    def handoff(self):
        return DesignHandoff.create(original_user_prompt='test fixture', design_prompt='not AI art',
            candidates={'A': self.source}, selected_candidate='A', generator='test_fixture',
            selection_notes='Synthetic test only', provenance={'fixture': True})

    def test_selected_handoff_reconstructs(self):
        result = self.reference(design_handoff=self.handoff())
        self.assertEqual(result.status, 'READY')

    def test_changed_selected_image_holds(self):
        handoff = self.handoff()
        Image.new('RGB', (100, 100), 'black').save(self.source)
        result = self.reference(design_handoff=handoff)
        self.assertEqual((result.status, result.master), ('HOLD', None))

    def test_changed_candidate_holds(self):
        candidate = self.work / 'candidate.png'
        candidate.write_bytes(self.source.read_bytes())
        handoff = DesignHandoff.create(original_user_prompt='fixture', design_prompt='fixture',
            candidates={'A': self.source, 'B': candidate}, selected_candidate='A',
            generator='test_fixture', selection_notes='fixture', provenance={'fixture': True})
        candidate.write_bytes(b'changed')
        self.assertEqual(self.reference(design_handoff=handoff).status, 'HOLD')

    def test_unrecognized_master_route_rejected(self):
        data = self.reference().master.to_dict()
        data['route'] = 'UNSUPPORTED_INPUT_ROUTE'
        with self.assertRaises(ValidationError):
            PlanarMasterV1.from_dict(data)

    def test_cli_prompt_writes_structured_hold(self):
        output = self.work / 'intake.json'
        with contextlib.redirect_stdout(io.StringIO()):
            code = main(['route', '--prompt', 'lotus', '--output', str(output)])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.read_text())['code'], 'AI_IMAGE_TOOL_UNAVAILABLE')


if __name__ == '__main__':
    unittest.main(verbosity=2)
