# Third-party notices

Audit date: 2026-10-01. This source-only release does not vendor third-party
code, Python wheels, Blender, interpreters or native libraries. Dependencies
are installed separately and retain their own copyright and licenses.
The project MIT grant do not replace any third-party terms.

The audit covers all non-standard runtime imports and the installed mandatory
dependency closure (6 direct packages, 10 transitive packages) on Windows
Python 3.11. Versions below are observed audit versions, not a new lockfile.
Optional extras are not requested; different platforms/resolutions may add terms.

| Package | Audited version | Relationship | License summary | Original notice |
| --- | --- | --- | --- | --- |
| [jsonschema](https://github.com/python-jsonschema/jsonschema) | 4.26.0 | Direct | MIT | [Unmodified text](references/third-party-licenses/jsonschema/jsonschema-4.26.0.dist-info/licenses/COPYING) |
| [pillow](https://github.com/python-pillow/Pillow) | 12.3.0 | Direct | MIT-CMU | [Unmodified text](references/third-party-licenses/pillow/pillow-12.3.0.dist-info/licenses/LICENSE) |
| [numpy](https://github.com/numpy/numpy) | 2.4.6 | Direct | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | [Unmodified text](references/third-party-licenses/numpy/numpy-2.4.6.dist-info/licenses/LICENSE.txt) |
| [scipy](https://github.com/scipy/scipy) | 1.17.1 | Direct | BSD-3-Clause; bundled component terms preserved in notices | [Unmodified text](references/third-party-licenses/scipy/scipy-1.17.1.dist-info/LICENSE.txt) |
| [opencv-python-headless](https://github.com/opencv/opencv-python) | 4.14.0.94 | Direct | MIT wrapper; Apache-2.0 OpenCV; bundled component notices | [Unmodified text](references/third-party-licenses/opencv-python-headless/cv2/LICENSE-3RD-PARTY.txt) |
| [scikit-image](https://github.com/scikit-image/scikit-image) | 0.26.0 | Direct | BSD-3-Clause plus per-file terms in LICENSE.txt | [Unmodified text](references/third-party-licenses/scikit-image/scikit_image-0.26.0.dist-info/LICENSE.txt) |
| [attrs](https://github.com/python-attrs/attrs) | 26.1.0 | Transitive | MIT | [Unmodified text](references/third-party-licenses/attrs/attrs-26.1.0.dist-info/licenses/LICENSE) |
| [jsonschema-specifications](https://github.com/python-jsonschema/jsonschema-specifications) | 2025.9.1 | Transitive | MIT | [Unmodified text](references/third-party-licenses/jsonschema-specifications/jsonschema_specifications-2025.9.1.dist-info/licenses/COPYING) |
| [referencing](https://github.com/python-jsonschema/referencing) | 0.37.0 | Transitive | MIT | [Unmodified text](references/third-party-licenses/referencing/referencing-0.37.0.dist-info/licenses/COPYING) |
| [rpds-py](https://github.com/crate-py/rpds) | 2026.6.3 | Transitive | MIT | [Unmodified text](references/third-party-licenses/rpds-py/rpds_py-2026.6.3.dist-info/licenses/LICENSE) |
| [networkx](https://github.com/networkx/networkx) | 3.6.1 | Transitive | BSD-3-Clause | [Unmodified text](references/third-party-licenses/networkx/networkx-3.6.1.dist-info/licenses/LICENSE.txt) |
| [ImageIO](https://github.com/imageio/imageio) | 2.37.4 | Transitive | BSD-2-Clause | [Unmodified text](references/third-party-licenses/ImageIO/imageio-2.37.4.dist-info/licenses/LICENSE) |
| [tifffile](https://github.com/cgohlke/tifffile) | 2026.3.3 | Transitive | BSD-3-Clause | [Unmodified text](references/third-party-licenses/tifffile/tifffile-2026.3.3.dist-info/licenses/LICENSE) |
| [packaging](https://github.com/pypa/packaging) | 26.3 | Transitive | Apache-2.0 OR BSD-2-Clause | [Unmodified text](references/third-party-licenses/packaging/packaging-26.3.dist-info/licenses/LICENSE) |
| [lazy-loader](https://github.com/scientific-python/lazy-loader) | 0.6 | Transitive | BSD-3-Clause | [Unmodified text](references/third-party-licenses/lazy-loader/lazy_loader-0.6.dist-info/licenses/LICENSE.md) |
| [typing_extensions](https://github.com/python/typing_extensions) | 4.16.0 | Transitive | PSF-2.0 | [Unmodified text](references/third-party-licenses/typing_extensions/typing_extensions-4.16.0.dist-info/licenses/LICENSE) |

## Complete evidence

All discovered upstream LICENSE/COPYING/NOTICE texts for these distributions
are retained byte-for-byte under `references/third-party-licenses/`, including
OpenCV LICENSE-3RD-PARTY, NumPy embedded notices, SciPy Qhull and other component
terms, and packaging LICENSE.APACHE and LICENSE.BSD. Their hashes, original
package-relative paths, dependency markers and original license metadata are
in [third-party-dependencies.json](references/third-party-dependencies.json).
This text-only preservation does not imply those binary components are bundled.

OpenCV wheel metadata says Apache 2.0, while its LICENSE.txt identifies the
Python packaging wrapper as MIT; both facts and the full third-party notices
are preserved rather than flattening the package to one misleading license.
Scientific wheels may carry OpenBLAS/LAPACK, compiler runtimes, image codecs
and their separate terms. Reassess actual wheel licenses before bundling them.

## External runtimes

- [CPython](https://docs.python.org/3/license.html): PSF and retained historical
  component licenses; interpreter/standard library not distributed here.
- [Blender](https://www.blender.org/about/license/): GPL; bpy, bmesh and mathutils
  come from a separately installed Blender. The audited installation is 5.1.2.
  OrnamentForge MIT covers its own source contributions, not Blender. Do not
  treat it as permission to relicense Blender or a combined GPL-covered work.
  Blender integration/distribution must respect applicable GPL obligations;
  MIT is a permissive compatible grant, not an exception to those obligations.
- Codex session image generation is an external product capability, not an
  included API SDK/model or an asset grant. Its outputs are not bundled.

`blender_contract` and `canonical_curve` are local OrnamentForge worker imports,
not missing third-party packages. Source scan found no vendored dependency code.

## Project material boundaries

Code: MIT. External reference materials:
not included / not licensed. Upstream notice texts keep their original terms
and are expressly excluded from blanket project relicensing.
