#!/usr/bin/env python3
"""Execute classification, marker cap, and actual frame-log aggregation on host."""
import pathlib, subprocess, sys, tempfile
root=pathlib.Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix='shadow45-') as tmp:
    p=pathlib.Path(tmp)
    (p/'Tempest').mkdir()
    (p/'Tempest/Log').write_text('''#pragma once
#include <sstream>
#include <string>
#include <vector>
namespace Tempest {struct Log {inline static std::vector<std::string> lines;
template<class... A>static void i(const A&... a){std::ostringstream s;(s<<...<<a);lines.push_back(s.str());}};}
''')
    (p/'test.cpp').write_text(r'''
#include "graphics/shadowsource45.h"
#include "utils/androidframeprofile.h"
#include <cassert>
#include <string>
#include <vector>
struct Timing {std::string name; double milliseconds;};
int main(){
  for(unsigned i=0;i<6;++i) {
    assert(ShadowSource45::category(1u<<i,false)==i);
    assert(ShadowSource45::category(1u<<i,true)==7);
    }
  for(unsigned mask=0;mask<64;++mask) {
    auto c=ShadowSource45::category(mask,false);
    if(mask==0 || (mask&(mask-1))) assert(c==6);
    }
  // A merged landscape+static packet must not be claimed as landscape.
  assert(ShadowSource45::category(1u|2u,false)==6);
  ShadowSource45::Runs runs;
  unsigned n=0;
  for(unsigned i=0;i<10000;++i) {
    unsigned c=i%6;
    if(runs.change(c)) ++n;
    }
  assert(n==9 && runs.previous==8);
  unsigned c=0;assert(!runs.change(c));
  ShadowProjection45 projection;
  std::array<float,16> matrix{};
  projection.observe(matrix);projection.observe(matrix);
  assert(projection.comparisons==1 && projection.same==1);
  matrix[0]=0.00000001f;projection.observe(matrix);
  assert(projection.comparisons==2 && projection.same==1);
  projection.resetWindow();projection.observe(matrix);
  assert(projection.frames==1 && projection.comparisons==1 && projection.same==1);
  ShadowSource45::Runs same;
  c=2;assert(same.change(c));assert(!same.change(c));
  AndroidFrameMetrics<3> metrics;
  metrics.logGpu(std::vector<Timing>{
    {"ShadowMap #1",0.25},{"ShadowMap #1 solid",0.125},
    {"ShadowMap #1 src=landscape solid",2.0},
    {"ShadowMap #1 src=static solid",1.0},
    {"ShadowMap #1 src=landscape solid",0.5},
    {"ShadowMap #1 alpha",0.125},
    {"ShadowMap #1 src=texture-animated alpha",4.0},
    {"ShadowMap #1 particles",0.25},{"SSAO",8.0}});
  bool total=false, shadow=false;unsigned sources=0;
  for(const auto& s:Tempest::Log::lines) {
    total|=s.find("GPU sample: total-ms=16.25")!=std::string::npos;
    shadow|=s.find("layer=1 total-ms=8.25 solid-ms=3.625 alpha-ms=4.125 particles-ms=0.25 setup-ms=0.25")!=std::string::npos;
    sources+=s.find("FIX45 shadow source:")!=std::string::npos;
    }
  assert(total && shadow && sources==4);
  }
''')
    subprocess.run(['g++','-std=c++20','-fsanitize=undefined','-fno-sanitize-recover=all',
                    '-I'+str(p),'-I'+str(root/'common'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)

s=(root/'common/graphics/drawcommands.cpp').read_text()
assert 'cmd[i].shadowSources45 |= uint32_t(1)<<uint32_t(type);' in s
assert 'cmd[i].shadowTextureAnimation45 |= m.hasFrameAnimation();' in s
assert s.index('if(pso==nullptr)',s.index('void DrawCommands::drawCommon')) < s.index('unsigned category45=')
assert 'for(auto i=b; i!=e; ++i)' in s
assert 'cmd.drawIndirect(view.indirectCmd, sizeof(IndirectCmd)*id);' in s
print('FIX45 classification/merged packets/bounded runs/actual log totals, UBSan: PASS')
