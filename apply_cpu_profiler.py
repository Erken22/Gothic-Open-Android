#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()

def replace_once(rel, old, new):
    p = root / rel
    s = p.read_text(encoding="utf-8")
    if old not in s:
        raise SystemExit(f"CPU profiler patch anchor not found in {rel}: {old[:180]!r}")
    p.write_text(s.replace(old,new,1),encoding="utf-8")

replace_once(
    "common/mainwindow.cpp",
    '#include <Tempest/Log>\n',
    '#include <Tempest/Log>\n#include <chrono>\n'
)

replace_once(
    "common/mainwindow.cpp",
'''  try {
    static uint64_t time=Application::tickCount();
''',
'''  try {
    static uint64_t time=Application::tickCount();
#if defined(__ANDROID__)
    using PerfClock = std::chrono::steady_clock;
    const auto perfFrameStart = PerfClock::now();
    static uint64_t perfTickUs=0, perfUiUs=0, perfEncodeUs=0;
    static uint64_t perfSubmitUs=0, perfPresentUs=0, perfFrameUs=0;
    static uint32_t perfFrameCount=0;
#endif
'''
)

replace_once(
    "common/mainwindow.cpp",
'''      tickCamera(dt);
      }
''',
'''      tickCamera(dt);
#if defined(__ANDROID__)
      const auto perfTickEnd = PerfClock::now();
#endif
      }
'''
)

replace_once(
    "common/mainwindow.cpp",
'''    inventory.setCovered(document.isActive() || chapter.isActive() || video.isActive());

    CommandBuffer& cmd = commands[cmdId];
''',
'''    inventory.setCovered(document.isActive() || chapter.isActive() || video.isActive());

#if defined(__ANDROID__)
    const auto perfUiEnd = PerfClock::now();
#endif
    CommandBuffer& cmd = commands[cmdId];
'''
)

replace_once(
    "common/mainwindow.cpp",
'''#endif
    }
    sync = device.submit(cmd);
    device.present(swapchain);
''',
'''#endif
    }
#if defined(__ANDROID__)
    const auto perfEncodeEnd = PerfClock::now();
#endif
    sync = device.submit(cmd);
#if defined(__ANDROID__)
    const auto perfSubmitEnd = PerfClock::now();
#endif
    device.present(swapchain);
#if defined(__ANDROID__)
    const auto perfPresentEnd = PerfClock::now();
    auto perfUs = [](auto a, auto b)->uint64_t {
      return uint64_t(std::chrono::duration_cast<std::chrono::microseconds>(b-a).count());
      };
    perfTickUs    += perfUs(perfFrameStart,perfTickEnd);
    perfUiUs      += perfUs(perfTickEnd,perfUiEnd);
    perfEncodeUs  += perfUs(perfUiEnd,perfEncodeEnd);
    perfSubmitUs  += perfUs(perfEncodeEnd,perfSubmitEnd);
    perfPresentUs += perfUs(perfSubmitEnd,perfPresentEnd);
    perfFrameUs   += perfUs(perfFrameStart,perfPresentEnd);
    ++perfFrameCount;
#endif
'''
)

replace_once(
    "common/mainwindow.cpp",
'''      Log::i("Runtime FPS: ",fps.get(),", target=",
             AndroidInput::preferences().fps,", frameLimitMs=",maxFpsInv,
             ", gpuFenceBusy=",gpuFenceBusy);
      gpuFenceBusy = 0;
''',
'''      Log::i("Runtime FPS: ",fps.get(),", target=",
             AndroidInput::preferences().fps,", frameLimitMs=",maxFpsInv,
             ", gpuFenceBusy=",gpuFenceBusy);
      if(perfFrameCount>0) {
        const double k = 1.0/(1000.0*double(perfFrameCount));
        Log::i("Frame CPU avg ms: tick=",double(perfTickUs)*k,
               ", ui=",double(perfUiUs)*k,
               ", encode=",double(perfEncodeUs)*k,
               ", submit=",double(perfSubmitUs)*k,
               ", present=",double(perfPresentUs)*k,
               ", total=",double(perfFrameUs)*k,
               ", frames=",perfFrameCount);
        }
      perfTickUs=perfUiUs=perfEncodeUs=perfSubmitUs=perfPresentUs=perfFrameUs=0;
      perfFrameCount=0;
      gpuFenceBusy = 0;
'''
)

print("Detailed Android CPU frame profiler applied")
