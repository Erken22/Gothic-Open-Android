#!/usr/bin/env python3
"""FIX40: conservative ray/frustum rejection for the original HQ fog mask.
Run AFTER apply_067.py on pinned OpenGothic 0.6.7 source.
Only the experimental shader differs; Original remains available in Video.
"""
from pathlib import Path
import sys

root=Path(sys.argv[1]).resolve()

def swap(path, old, new):
    p=root/path
    s=p.read_text(encoding="utf-8")
    count=s.count(old)
    if count!=1:
        raise SystemExit(f"FIX40 anchor in {path}: expected once, found {count}: {old[:100]!r}")
    p.write_text(s.replace(old,new,1),encoding="utf-8")

swap("shader/sky/fog.frag",
     "  const vec3  ray      = pos1.xyz - pos0.xyz;\n",
     """#if defined(FIX40_FOG_TRIVIAL_OUTSIDE) && defined(GL_COMPUTE_SHADER) && !defined(VIRTUAL_SHADOW)
  // Existing 32 samples have t=(i+0.5)/32+noise/32, with 0<=noise<1.
  // Thus t is in [0, 65/64). The homogeneous shadow point is affine
  // in t. If BOTH endpoints of this superset lie outside the SAME
  // shadow clip half-space, all 32 original shadowFactor() checks return
  // true: no depth fetch is needed. Use a generous positive guard band
  // to avoid changing comparisons near edges due to FP rounding.
  const vec4 shLast40 = shPos1 + (shPos1-shPos0)*(1.0/64.0);
  const float edge40 = max(max(abs(shPos0.w),abs(shLast40.w)),1.0)*0.001;
  const bool outside40 =
    (shPos0.x > shPos0.w+edge40 && shLast40.x > shLast40.w+edge40) ||
    (-shPos0.x > shPos0.w+edge40 && -shLast40.x > shLast40.w+edge40) ||
    (shPos0.y > shPos0.w+edge40 && shLast40.y > shLast40.w+edge40) ||
    (-shPos0.y > shPos0.w+edge40 && -shLast40.y > shLast40.w+edge40);
  if(outside40) {
    imageStore(occlusionLut, ivec2(invocationID.xy), uvec4(0xFFFFFFFFu));
    return vec4(0.0);
    }
#endif
  const vec3  ray      = pos1.xyz - pos0.xyz;
""")

swap("shader/CMakeLists.txt",
     "add_shader(fog3d.comp                sky/fog.frag -S comp -DVOLUMETRIC)",
     "add_shader(fog3d.comp                sky/fog.frag -S comp -DVOLUMETRIC)\n"
     "add_shader(fog3d_cull40.comp         sky/fog.frag -S comp -DVOLUMETRIC -DFIX40_FOG_TRIVIAL_OUTSIDE)")

swap("common/graphics/shaders.h",
     "    Tempest::ComputePipeline cloudsLut, fogOcclusion;",
     "    Tempest::ComputePipeline cloudsLut, fogOcclusion, fogOutside40;")

swap("common/graphics/shaders.cpp",
     '  fogOcclusion       = computeShader("fog3d.comp.sprv");',
     """  fogOcclusion       = computeShader("fog3d.comp.sprv");
#if defined(__ANDROID__)
  if(AndroidSaoCompare39::supported())
    fogOutside40      = computeShader("fog3d_cull40.comp.sprv");
#endif""")

swap("common/graphics/renderer.h",
     "      bool           ssaoHalfResolution = false;",
     "      bool           ssaoHalfResolution = false;\n      bool           fogOutside40       = false;")

# Prior FIX39 test's saved Compare=2 is deliberately normalized to Original.
# SAO remains available only by explicit manual selection (mode 1).
swap("common/graphics/renderer.cpp",
     '  settings.aoMethod39 = std::clamp(Gothic::settingsGetI("ENGINE","aoMethod39"),0,2);',
     '  settings.aoMethod39 = (Gothic::settingsGetI("ENGINE","aoMethod39")==1) ? 1 : 0;\n'
     '  settings.fogOutside40 = Gothic::settingsGetI("ENGINE","fogOutside40")!=0;')

swap("common/gothic.cpp",
     '  defaults->set("ENGINE",       "aoMethod39", 2); // Experimental FIX39: bounded comparison, then original.',
     '  defaults->set("ENGINE",       "aoMethod39", 0); // FIX40: previous SAO loses on phone, prefer original.\n'
     '  defaults->set("ENGINE",       "fogOutside40", 1); // FIX40 test, change to Original in Video settings.')

swap("common/graphics/renderer.cpp",
     '        cmd.setPipeline(shaders.fogOcclusion);\n        cmd.dispatchThreads(occlusionLut.size());',
     """#if defined(__ANDROID__)
        const bool use40 = settings.fogOutside40 && AndroidSaoCompare39::supported();
        static int lastFog40=-1;
        if(lastFog40!=int(use40)) {
          lastFog40=int(use40);
          Log::i("FIX40 fog outside: ",use40 ? "TEST" : "ORIGINAL",
                 " (same raymarch and output; conservative out-of-map shortcut)");
          }
        cmd.setPipeline(use40 ? shaders.fogOutside40 : shaders.fogOcclusion);
#else
        cmd.setPipeline(shaders.fogOcclusion);
#endif
        cmd.dispatchThreads(occlusionLut.size());""")

swap("common/ui/gamemenu.cpp",
     '    {"ANDROID_AO39","AO method","Original|SAO test|Compare","ENGINE","aoMethod39"},',
     '    {"ANDROID_AO39","AO method","Original|SAO test","ENGINE","aoMethod39"},\n'
     '    {"ANDROID_FOG40","Fog shadow clip","Original|Test","ENGINE","fogOutside40"},')
swap("common/ui/gamemenu.cpp", "    y+=625;", "    y+=550;")

# Validate independent original compiler path and experimental path both exist.
checks={
 "shader/sky/fog.frag": ["#if defined(FIX40_FOG_TRIVIAL_OUTSIDE)", "const vec3  ray      = pos1.xyz - pos0.xyz;", "imageStore(occlusionLut, ivec2(invocationID.xy), uvec4(occlusion));"],
 "shader/CMakeLists.txt": ["fog3d.comp", "fog3d_cull40.comp"],
 "common/graphics/renderer.cpp": ["FIX40 fog outside:", "shaders.fogOutside40", "settings.aoMethod39 ="],
}
for path, needles in checks.items():
    s=(root/path).read_text(encoding="utf-8")
    for needle in needles:
        if needle not in s:
            raise SystemExit(f"Missing FIX40 integrity needle: {path}: {needle}")
print("FIX40 source anchors and original-path integrity: PASS")
