#!/usr/bin/env python3
"""FIX41: Enable ZenKit compressed Union ZippedStream VDF support on Android.
Apply AFTER apply_067.py, apply_fix40.py and apply_fix40t.py to a clean tree.
"""
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
cmake = root / "CMakeLists.txt"
content = cmake.read_text()
anchor = 'set(ZK_ENABLE_DEPRECATION      OFF CACHE INTERNAL "")'
if content.count(anchor) != 1:
    raise SystemExit(f"FIX41: expected exactly one ZenKit CMake anchor, got {content.count(anchor)}")
content = content.replace(anchor, anchor + '\n# FIX41: compressed Union ZippedStream VDF resources (Union.vdf, Plugins/zGamePad.vdf).\n# The existing ZenKit CMake integrates this opt-in with miniz and squish.\nset(ZK_ENABLE_ZIPPED_VDF      ON CACHE INTERNAL "")', 1)
# ZenKit's compressed VDF option FetchContent-provides a miniz target.
# Reuse that target instead of re-declaring the bundled miniz project target.
miniz_anchor = 'add_library(miniz STATIC EXCLUDE_FROM_ALL "lib/miniz/miniz.h" "lib/miniz/miniz.c")'
if content.count(miniz_anchor) != 1:
    raise SystemExit(f"FIX41: expected one bundled miniz target, got {content.count(miniz_anchor)}")
content = content.replace(miniz_anchor, "if(NOT TARGET miniz)" + chr(10) + "  " + miniz_anchor + chr(10) + "endif()", 1)
cmake.write_text(content)
assert 'set(ZK_ENABLE_ZIPPED_VDF      ON CACHE INTERNAL "")' in cmake.read_text()\nassert "if(NOT TARGET miniz)" in cmake.read_text()
print("FIX41 zipped VDF build option: PASS")
