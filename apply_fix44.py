#!/usr/bin/env python3
"""FIX44: minimize original SSAO group-shared atomics using subgroup max.
Apply after FIX43 on OpenGothic 0.6.7 pinned tree. Quality settings unchanged.
"""
from pathlib import Path
import sys
r=Path(sys.argv[1]).resolve()

def replace(path, old, new):
    p=r/path
    s=p.read_text()
    n=s.count(old)
    if n!=1: raise SystemExit(f"FIX44 anchor mismatch {path} ({n}) {old!r}")
    p.write_text(s.replace(old,new,1))

# Compute shader 8x8 workgroup = 64 lanes; subgroupMax computes a per-wave
# max, and a single elected lane updates group-shared max, preserving overall
# max and convergence threshold for every lane.
replace("shader/ssao/convergence.glsl",
    "  atomicMax(ssaoMaxDiff, floatBitsToUint(diff));",
    """  const float subgroupDiff44 = subgroupMax(diff);
  if(subgroupElect())
    atomicMax(ssaoMaxDiff, floatBitsToUint(subgroupDiff44));""")
replace("shader/ssao/ssao.comp",
    "#extension GL_EXT_control_flow_attributes : enable",
    """#extension GL_EXT_control_flow_attributes : enable
// FIX44: subgroup arithmetic is used only in original 32-tap SSAO.
#extension GL_KHR_shader_subgroup_basic : require
#extension GL_KHR_shader_subgroup_arithmetic : require""")
replace("shader/ssao/ssao.comp",
    "  atomicMax(shMaxSteps, maxSteps);",
    """  // Workgroup maximum is identical; reduce 64 contended atomics to
  // one per hardware subgroup, with the existing barrier below unchanged.
  const int subgroupSteps44 = subgroupMax(maxSteps);
  if(subgroupElect())
    atomicMax(shMaxSteps, subgroupSteps44);""")
# Subgroup ops require SPIR-V >= 1.3 on Vulkan 1.1 / target Turnip 1.3.
# Restrict upgraded SPIR-V target to original full/half SSAO shaders.
replace("shader/CMakeLists.txt",
    "add_shader(ssao.comp                 ssao/ssao.comp)",
    "add_shader(ssao.comp                 ssao/ssao.comp --target-env spirv1.3)")
replace("shader/CMakeLists.txt",
    "add_shader(ssao_half.comp            ssao/ssao.comp -DSSAO_HALF_RES)",
    "add_shader(ssao_half.comp            ssao/ssao.comp -DSSAO_HALF_RES --target-env spirv1.3)")
p=(r/"shader/ssao/ssao.comp").read_text()
c=(r/"shader/ssao/convergence.glsl").read_text()
assert "const uint  numSamples     = 32;" in p
assert "const uint  numIter        = 8;" in p
assert "subgroupMax(maxSteps)" in p
assert "subgroupMax(diff)" in c
assert "if(valid && at0.z<1.0)" in p
assert "sampleHemisphereFast43" in p
print("FIX44: 32 AO taps, exact group maxima, subgroup reduction: PASS")
