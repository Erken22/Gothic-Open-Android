#!/usr/bin/env python3
"""FIX45: bound and label shadow timing intervals without reordering draws."""
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
def swap(path, old, new):
    p = root/path
    s = p.read_text()
    if s.count(old) != 1:
        raise SystemExit(f'FIX45 anchor mismatch: {path}: {s.count(old)}')
    p.write_text(s.replace(old, new, 1))

header = r'''#pragma once
#include <cstdint>
#include <array>

// Source classes, not a promise that an object can be cached.
// DrawCommands can merge different source types when their pipelines match.
struct ShadowSource45 {
  static constexpr unsigned Mixed=6, TextureAnimated=7, Overflow=8;
  static constexpr unsigned MarkerLimit=8;
  static unsigned category(uint32_t sourceMask, bool textureAnimated) {
    if(textureAnimated) return TextureAnimated;
    for(unsigned i=0;i<6;++i)
      if(sourceMask==(uint32_t(1)<<i)) return i;
    return Mixed;
    }
  static const char* name(unsigned i) {
    constexpr const char* names[]={"landscape","static","movable","animated",
                                 "particles","morph","mixed","texture-animated","overflow"};
    return names[i<=Overflow ? i : Overflow];
    }
  struct Runs {
    unsigned previous=Overflow+1, emitted=0;
    bool change(unsigned& category) {
      if(previous==Overflow) return false;
      if(category==previous) return false;
      if(emitted>=MarkerLimit) category=Overflow;
      previous=category;
      ++emitted;
      return true;
      }
    };
  };

struct ShadowProjection45 {
  std::array<float,16> previous{};
  uint32_t frames=0, comparisons=0, same=0;
  bool initialized=false;
  void observe(const std::array<float,16>& matrix) {
    ++frames;
    if(initialized) {
      ++comparisons;
      same+=uint32_t(previous==matrix);
      }
    previous=matrix;
    initialized=true;
    }
  void resetWindow() {frames=0; comparisons=0; same=0;}
  };
'''
(root/'common/graphics/shadowsource45.h').write_text(header)
swap('common/graphics/drawcommands.h',
     '      Type                           type         = Type::Landscape;',
     '      Type                           type         = Type::Landscape;\n'
     '      uint32_t                       shadowSources45 = 0;\n'
     '      bool                           shadowTextureAnimation45 = false;')
swap('common/graphics/drawcommands.cpp', '#include "drawcommands.h"',
     '#include "drawcommands.h"\n#include "shadowsource45.h"\n#include "utils/string_frm.h"')
swap('common/graphics/drawcommands.cpp',
     '    return uint16_t(i);\n    }\n\n  auto ret = uint16_t(cmd.size());',
     '    cmd[i].shadowSources45 |= uint32_t(1)<<uint32_t(type);\n'
     '    cmd[i].shadowTextureAnimation45 |= m.hasFrameAnimation();\n'
     '    return uint16_t(i);\n    }\n\n  auto ret = uint16_t(cmd.size());')
swap('common/graphics/drawcommands.cpp', '  cx.type        = type;',
     '  cx.type        = type;\n'
     '  cx.shadowSources45 = uint32_t(1)<<uint32_t(type);\n'
     '  cx.shadowTextureAnimation45 = m.hasFrameAnimation();')
# Limit instrumentation to ordinary shadow views, retain original iteration order.
swap('common/graphics/drawcommands.cpp',
     '  auto& view = views[viewId];\n  for(auto i=b; i!=e; ++i) {',
     '  auto& view = views[viewId];\n'
     '#if defined(__ANDROID__)\n'
     '  ShadowSource45::Runs shadowRuns45;\n'
     '  const int shadowLayer45 = viewId==SceneGlobals::V_Shadow0 ? 0 :\n'
     '                            (viewId==SceneGlobals::V_Shadow1 ? 1 : -1);\n'
     '#endif\n'
     '  for(auto i=b; i!=e; ++i) {')
needle='''    if(pso==nullptr)
      continue;

    auto id  = size_t(std::distance(this->cmd.data(), &cx));'''
replacement='''    if(pso==nullptr)
      continue;

#if defined(__ANDROID__)
    if(shadowLayer45>=0) {
      unsigned category45=ShadowSource45::category(cx.shadowSources45,cx.shadowTextureAnimation45);
      if(shadowRuns45.change(category45))
        cmd.setDebugMarker(string_frm("ShadowMap #",shadowLayer45," src=",ShadowSource45::name(category45),
                                     func==Material::Solid ? " solid" : " alpha"));
      }
#endif
    auto id  = size_t(std::distance(this->cmd.data(), &cx));'''
swap('common/graphics/drawcommands.cpp', needle, replacement)
swap('common/utils/androidframeprofile.h',
     '    // Aggregate all shadow subpasses, even if they are absent from the top four.',
     '''    // FIX45 intervals retain draw order; repeated source tags must be summed.
    // No new query readbacks: consume only this existing sparse GPU sample.
    for(const auto& pass:timings) {
      const std::string_view tag=pass.name;
      if(tag.starts_with("ShadowMap #") && tag.find(" src=")!=std::string_view::npos)
        Tempest::Log::i("FIX45 shadow source: tag=",tag," ms=",pass.milliseconds," frame-ms=",total);
      }
    // Aggregate all shadow subpasses, even if they are absent from the top four.''')
swap('common/graphics/renderer.cpp', '#include "utils/androidframeprofile.h"',
     '#include "utils/androidframeprofile.h"\n#include "graphics/shadowsource45.h"')
swap('common/graphics/renderer.cpp',
     'void Renderer::drawShadowMap(Encoder<CommandBuffer>& cmd, uint8_t fId, WorldView& view) {',
     '''void Renderer::drawShadowMap(Encoder<CommandBuffer>& cmd, uint8_t fId, WorldView& view) {
#if defined(__ANDROID__)
  if(!shadowMap[1].isEmpty() && view.mainLight().dir().y>Camera::minShadowY) {
    static ShadowProjection45 projection45;
    std::array<float,16> matrix45{};
    const auto& matrix=view.sceneGlobals().viewShadow(1);
    for(int c=0;c<4;++c)
      for(int r=0;r<4;++r)
        matrix45[size_t(c*4+r)]=matrix.at(c,r);
    projection45.observe(matrix45);
    if(projection45.frames>=120) {
      Log::i("FIX45 shadow projection: layer=1 comparisons=",projection45.comparisons,
             " identical=",projection45.same," changed=",projection45.comparisons-projection45.same,
             " (exact matrix equality only; geometry/material invalidation not checked)");
      projection45.resetWindow();
      }
    }
#endif''')
print('FIX45: source masks, bounded in-order shadow intervals and sparse logging: PASS')
