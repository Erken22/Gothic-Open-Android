#!/usr/bin/env python3
"""FIX40T: mode-tagged fog GPU timestamps. Apply after FIX39 + FIX40.
No shader, framebuffer, synchronization, shadow, AO or rendering changes.
"""
from pathlib import Path
import sys
root=Path(sys.argv[1]).resolve()
def swap(name,old,new):
    file=root/name
    content=file.read_text()
    count=content.count(old)
    if count!=1:
        raise SystemExit(f"FIX40T patch anchor mismatch in {name}: {count} occurrences")
    file.write_text(content.replace(old,new,1))

swap("common/graphics/renderer.cpp",
    '      cmd.setDebugMarker("Fog-sunshaft-occlusion");',
    '''#if defined(__ANDROID__)
      const bool fog40Test = settings.fogOutside40 && AndroidSaoCompare39::supported() &&
                            !(settings.vsmEnabled && !settings.rtsmEnabled && !settings.pathTraceEnabled);
      cmd.setDebugMarker(fog40Test ? "Fog-sunshaft-occlusion TEST" : "Fog-sunshaft-occlusion ORIGINAL");
#else
      cmd.setDebugMarker("Fog-sunshaft-occlusion");
#endif''')

swap("common/utils/androidframeprofile.h",
    '    Tempest::Log::i("FIX39 GPU sample: total-ms=",total);',
    '''    Tempest::Log::i("FIX39 GPU sample: total-ms=",total);
    // GPU timestamps already read following the existing submission fence.
    // Include fog timing even when it is not in the four slowest passes.
    // Labels are captured with GPU commands, not sampled from current UI state.
    for(const auto& pass:timings) {
      if(std::string_view(pass.name).starts_with("Fog-sunshaft-occlusion"))
        Tempest::Log::i("FIX40T fog GPU: ",pass.name," ms=",pass.milliseconds," frame-ms=",total);
      }''')

s=(root/"common/graphics/renderer.cpp").read_text()
h=(root/"common/utils/androidframeprofile.h").read_text()
assert 'Fog-sunshaft-occlusion TEST' in s
assert 'Fog-sunshaft-occlusion ORIGINAL' in s
assert 'FIX40T fog GPU:' in h
assert 'captureGpu(uint64_t time)' in h
print("FIX40T profiling-only patch validation: PASS")
