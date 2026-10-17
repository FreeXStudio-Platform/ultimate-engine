"""`video_script.py` is a real capability — retained counter-examples proving it, `OG-120`.

**Why this file exists.** An AST import graph over all 72 tracked `.py` files found exactly two
modules with no Python importer that are neither tests nor CLI entry points: `fetch_public_fact.py`
(registered, dispositioned `NOT_A_DEFECT` at `OG-17`) and this one. `CAPABILITIES.json` declared it
a shipped capability with `"entry": "video_script.py"` — the shape of a runnable file — while
nothing in the repository called it, no test covered it, and it appeared in no register row, no
changelog entry and no session state. Pass 6 recorded that as `P6-37` and it was never actioned.

The module is not dead code: it is a small library, and re-deriving that (`L-27`, verify the
finding and not only the fix) showed the functions work. What was missing was proof, and a
declaration that described it accurately. Both are supplied here — the declaration now names the
callable rather than implying a command, and these probes make the capability *proven* instead of
*assumed*, which is the whole difference this engine exists to enforce.

Eligibility is the interesting half: `generate_for_manifest_row` is a gate, and a gate with no
counter-example is a gate nobody has watched refuse anything.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.docgen.models import ManifestRow, Surface, Tier, VideoScene, VideoScript
from tools.docgen.video_script import (
    generate_for_manifest_row,
    render_video_script,
    write_video_script,
)


def _row(content_role: str) -> ManifestRow:
    return ManifestRow(
        id="EDU",
        title="Explainers",
        type="EDU",
        variants=[Tier.PUBLIC],
        content_role=content_role,
        surface=Surface.WEB,
        status="active",
    )


_SCENES = [
    VideoScene(beat="hook", narration="A gate nobody runs is not a gate.", animation_ref="anim-1"),
    VideoScene(beat="mechanism", narration="It fails closed instead."),
]


class VideoScriptRenders(unittest.TestCase):
    def test_every_scene_reaches_the_output(self) -> None:
        out = render_video_script(VideoScript(doc_id="EDU-501", title="Gates", scenes=_SCENES))
        for scene in _SCENES:
            with self.subTest(beat=scene.beat):
                self.assertIn(scene.narration, out)
                self.assertIn(scene.beat, out)
        self.assertIn("Gates", out)

    def test_an_animation_ref_is_carried_through(self) -> None:
        """The whole point of the format: narration paired with the animation it belongs to."""
        out = render_video_script(VideoScript(doc_id="EDU-501", title="Gates", scenes=_SCENES))
        self.assertIn("anim-1", out)

    def test_rendering_is_deterministic(self) -> None:
        """The module docstring claims determinism — no timestamps, stable scene order."""
        script = VideoScript(doc_id="EDU-501", title="Gates", scenes=_SCENES)
        self.assertEqual(render_video_script(script), render_video_script(script))


class VideoScriptEligibilityGate(unittest.TestCase):
    """`generate_for_manifest_row` refuses every content role but `article`."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="vscript-")
        self.addCleanup(tmp.cleanup)
        self.out = Path(tmp.name)

    def test_an_article_row_writes_a_script(self) -> None:
        path = generate_for_manifest_row(
            _row("article"), doc_id="EDU-501", title="Gates", scenes=_SCENES, out_dir=self.out
        )
        self.assertIsNotNone(path)
        assert path is not None
        self.assertTrue(path.is_file())
        self.assertEqual(path.name, "EDU-501.video-script.md")

    def test_every_other_content_role_is_refused(self) -> None:
        for role in ("project-doc", "asset", "", "Article", "articles"):
            with self.subTest(content_role=role):
                path = generate_for_manifest_row(
                    _row(role), doc_id="EDU-501", title="Gates", scenes=_SCENES, out_dir=self.out
                )
                self.assertIsNone(path, f"{role!r} was accepted as an article")

    def test_two_instances_of_one_row_do_not_overwrite_each_other(self) -> None:
        """The module docstring's stated hazard: keying output by `row.id` — the bare TYPE prefix —
        would make every `EDU-5NN` article write to `EDU.video-script.md`. Keyed by `doc_id`.
        """
        first = generate_for_manifest_row(
            _row("article"), doc_id="EDU-501", title="One", scenes=_SCENES, out_dir=self.out
        )
        second = generate_for_manifest_row(
            _row("article"), doc_id="EDU-502", title="Two", scenes=_SCENES, out_dir=self.out
        )
        self.assertNotEqual(first, second)
        assert first is not None and second is not None
        self.assertTrue(first.is_file() and second.is_file())

    def test_write_creates_its_output_directory(self) -> None:
        nested = self.out / "deep" / "deeper"
        path = write_video_script(
            VideoScript(doc_id="EDU-501", title="Gates", scenes=_SCENES), nested
        )
        self.assertTrue(path.is_file())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
