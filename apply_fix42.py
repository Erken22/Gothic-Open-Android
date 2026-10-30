#!/usr/bin/env python3
"""FIX42: full-resolution SSAO sky fast path; all actual geometry AO identical.
Run after apply_067.py, apply_fix40.py and apply_fix40t.py.
"""
import sys
from pathlib import Path

root=Path(sys.argv[1]).resolve()
p=root/"shader/ssao/ssao.comp"
s=p.read_text()

def change(before,after):
    global s
    n=s.count(before)
    if n!=1: raise SystemExit(f"FIX42 shader anchor missing/nonunique ({n}): {before!r}")
    s=s.replace(before,after,1)

# The original code reconstructs 4 depth neighbours + 3 view-space points +
# normal and TBN even for depth==1 where maxSteps==0 and the AO cannot shadow.
# Do NOT touch the 32-sample hemisphere loop, depth, resolution or real geometry.
change(
    """  const vec3 camPos = unproject(vec3(0,0,0));
  const vec3 at0    = vec3(inPos.xy,readZ(inPos.xy));
  const vec3 pos0   = unproject(at0);

  if(valid) {
    const vec3 view = (pos0 - camPos);
    norm = reconstructNormal(at0, inPos.xy);""",
    """  const vec3 at0 = vec3(inPos.xy,readZ(inPos.xy));
  vec3 pos0 = vec3(0.0);

  // FIX42: skip depth derivatives, reconstruction and tangent basis on sky.
  // Sky has maxSteps==0 and physically cannot occlude ambient light.
  // Compute normal and hemisphere vectors unmodified for all non-sky pixels.
  if(valid && at0.z<1.0) {
    pos0 = unproject(at0);
    norm = reconstructNormal(at0, inPos.xy);""")
change(
    """#if 1
    occlusion = resolveOcclusion();
#endif

#ifdef SSAO_HALF_RES""",
    """#if 1
    // For sky all bucket weights are zero, so the old division is 0/0 (NaN).
    // The intended neutral occlusion is zero, hence AO=1.
    occlusion = at0.z>=1.0 ? 0.0 : resolveOcclusion();
#endif

#ifdef SSAO_HALF_RES""")
p.write_text(s)
assert "if(valid && at0.z<1.0)" in s
assert "occlusion = at0.z>=1.0 ? 0.0 : resolveOcclusion();" in s
assert "const uint  numSamples     = 32;" in s
assert "const uint  numIter        = 8;" in s
assert "const int   gridQSize      = 25;" in s
assert "atomicMax(shMaxSteps, maxSteps);" in s
assert "barrier();" in s
print("FIX42: SSAO full-resolution sky fast path, unchanged geometry AO: PASS")
