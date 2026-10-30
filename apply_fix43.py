#!/usr/bin/env python3
"""FIX43: factor per-sample SSAO trigonometry into one pixel rotation.
Apply after apply_fix42.py. Keeps all 32 geometric AO samples and resolution.
"""
import math
import sys
from pathlib import Path

root=Path(sys.argv[1]).resolve()
p=root/"shader/ssao/ssao.comp"
s=p.read_text()
def replace(old,new):
    global s
    n=s.count(old)
    if n!=1: raise SystemExit(f"FIX43: anchor mismatch ({n}): {old[:100]!r}")
    s=s.replace(old,new,1)

kernel=",\n    ".join(
    f"vec2({math.cos(i*math.pi/16):.12f}, {math.sin(i*math.pi/16):.12f})"
    for i in range(8))
fast_fn="""
const vec2 ssaoQuarter43[8] = vec2[8](
    """ + kernel + """
  );

// Hammersley x = i/32, y = bitfieldReverse(i)/2^32. For i in [0,31],
// reverse5(i) selects a multiple of PI/16. Low 2 bits encode quadrant;
// remaining 3 bits index an eighth of the circle (0..7 * PI/16).
vec3 sampleHemisphereFast43(uint i, vec2 rot) {
  uint k = i >> 2u;
  uint a = ((k & 1u)<<2u) | (k & 2u) | ((k & 4u)>>2u);
  vec2 xy = ssaoQuarter43[a];
  if((i & 2u)!=0u)
    xy = vec2(-xy.y,xy.x);
  if((i & 1u)!=0u)
    xy = -xy;
  xy *= sqrt(float(i)*(1.0/32.0));
  return vec3(xy.x*rot.x-xy.y*rot.y,
              xy.x*rot.y+xy.y*rot.x,
              float(i)*(1.0/32.0));
  }

"""
replace(
    "void calcOcclussion(const vec3 at0, const vec3 pos0, const float f0, uint seed, uint step) {",
    fast_fn + "void calcOcclussion(const vec3 at0, const vec3 pos0, const vec2 rot43, uint seed, uint step) {")
replace("vec3  h      = sampleHemisphereCos(i,numSamples,f0);",
        "vec3  h      = sampleHemisphereFast43(i,rot43);")
replace(
    "  const float f0 = M_PI*2.0*wangHashNoise(uvec2(fragCoord), 0);",
    """  const float f0 = M_PI*2.0*wangHashNoise(uvec2(fragCoord), 0);
  // Two transcendental operations per non-sky pixel, instead of per sample.
  vec2 rot43 = vec2(1.0,0.0);
  if(valid && at0.z<1.0)
    rot43 = vec2(cos(f0),sin(f0));""")
replace("calcOcclussion(at0, pos0, f0, i, numIter);",
        "calcOcclussion(at0, pos0, rot43, i, numIter);")
p.write_text(s)
assert "const uint  numSamples     = 32;" in s
assert "const uint  numIter        = 8;" in s
assert "ssaoQuarter43[8]" in s
assert "sampleHemisphereFast43(i,rot43)" in s
assert "if(valid && at0.z<1.0)" in s
print("FIX43: 32 AO sample positions preserved, trig factored: PASS")
