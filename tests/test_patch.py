from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.patch_playwright_profile import (
    DEFAULT_CONTEXT_MARKER,
    MARKER,
    PROFILE_ENV,
    PatchError,
    patch_playwright,
)

PROFILE_LOGIC = """\
// _sharedBrowser selects launchServerShared.
class BrowserType {
  async launch(progress, options, protocolLogger) {
    return this._innerLaunchWithRetries(progress, options, void 0, helper.debugProtocolLogger(protocolLogger)).catch((error) => { throw error; });
  }
}
async function prepare() {
  const tempDirectories = [];
  let userDataDir;
  if (userDataDir) {
    assert(path.isAbsolute(userDataDir), "userDataDir must be an absolute path");
    if (!await existsAsync(userDataDir))
      await fs.promises.mkdir(userDataDir, { recursive: true, mode: 448 });
  } else {
    userDataDir = await fs.promises.mkdtemp(path.join(os.tmpdir(), `playwright_${this._name}dev_profile-`));
    tempDirectories.push(userDataDir);
  }
}
"""


class PlaywrightPatchTests(unittest.TestCase):
    def test_patch_injects_guard_and_preserves_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary)
            target = package / "lib" / "coreBundle.js"
            target.parent.mkdir()
            target.write_text(PROFILE_LOGIC, encoding="utf-8")

            patched_target = patch_playwright(package, check_syntax=False)
            source = patched_target.read_text(encoding="utf-8")

            self.assertEqual(patched_target, target)
            self.assertEqual(source.count(MARKER), 1)
            self.assertEqual(source.count(DEFAULT_CONTEXT_MARKER), 1)
            self.assertEqual(source.count(PROFILE_ENV), 3)
            self.assertNotIn("return // CAMOUFOX", source)
            self.assertIn("return this._innerLaunchWithRetries", source)
            self.assertIn('this._name === "firefox"', source)
            self.assertIn("dev_profile-", source)
            self.assertIn("tempDirectories.push(userDataDir)", source)
            self.assertTrue(Path(str(target) + ".pre-camoufox-patch").is_file())

    def test_patch_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary)
            target = package / "coreBundle.js"
            target.write_text(PROFILE_LOGIC, encoding="utf-8")
            patch_playwright(package, check_syntax=False)
            first = target.read_text(encoding="utf-8")
            patch_playwright(package, check_syntax=False)
            self.assertEqual(target.read_text(encoding="utf-8"), first)

    def test_no_candidate_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary)
            (package / "other.js").write_text("const userDataDir = null;", encoding="utf-8")
            with self.assertRaisesRegex(PatchError, "Unable to safely locate"):
                patch_playwright(package, check_syntax=False)

    def test_multiple_candidates_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary)
            (package / "one.js").write_text(PROFILE_LOGIC, encoding="utf-8")
            (package / "two.js").write_text(PROFILE_LOGIC, encoding="utf-8")
            with self.assertRaisesRegex(PatchError, "candidate files: 2"):
                patch_playwright(package, check_syntax=False)

    def test_unconfirmed_candidate_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary)
            target = package / "coreBundle.js"
            target.write_text(
                "const userDataDir = `playwright_firefoxdev_profile-`;",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(PatchError, "Unable to locate userDataDir branch"):
                patch_playwright(package, check_syntax=False)


if __name__ == "__main__":
    unittest.main()
