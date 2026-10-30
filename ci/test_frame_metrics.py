#!/usr/bin/env python3
"""Check frame summary math and bounded sparse GPU sampling without a GPU."""
import ast,pathlib,subprocess,tempfile
repo=pathlib.Path(__file__).resolve().parent.parent
header=None
for node in ast.walk(ast.parse((repo/'apply_067.py').read_text())):
    if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='write_text' and node.args:
        try: text=ast.literal_eval(node.args[0])
        except (ValueError,TypeError):continue
        if isinstance(text,str) and 'struct AndroidFrameMetrics' in text:header=text
assert header
with tempfile.TemporaryDirectory(prefix='gothic-frame-metrics-') as tmp:
    p=pathlib.Path(tmp);inc=p/'Tempest';inc.mkdir()
    (inc/'Log').write_text('''#pragma once
#include <sstream>
#include <vector>
#include <string>
namespace Tempest {struct Log {inline static std::vector<std::string> lines;template<class... Args>static void i(const Args&...args){std::ostringstream s;(s<<...<<args);lines.push_back(s.str());}};}
''')
    (p/'metrics.h').write_text(header)
    (p/'test.cpp').write_text(r'''
#include "metrics.h"
#include <cassert>
#include <cstdio>
#include <vector>
#include <string>
struct Timing {std::string name;double milliseconds;};
int main(){
  AndroidFrameMetrics<3> m;
  for(int i=0;i<16;++i){assert(m.captureGpu(1+uint64_t(i)*1000000));assert(!m.captureGpu(2+uint64_t(i)*1000000));}
  for(int i=16;i<24;++i){assert(m.captureGpu(15000001+uint64_t(i-15)*10000000));}
  assert(!m.captureGpu(1000000000));
  m.skip();m.skip();
  for(uint64_t i=0;i<50;++i){uint64_t b=1+i*40000;m.frame(b,b+1000,b+5000,b+18000,b+20000,b+40000,b+6000,2400,1080);}
  assert(Tempest::Log::lines.size()==1);
  auto line=Tempest::Log::lines[0];
  for(auto value:{"fps=25","sim-ms=4","ui-ms=1","record-ms=12","submit-ms=2","present-ms=20","skipped=2","output=2400x1080"})assert(line.find(value)!=std::string::npos);
  assert(m.frames==0 && m.samples==24);
  m.logGpu(std::vector<Timing>{{"tiny",0.5},{"small",2},{"middle",4},{"large",8},{"largest",16}});
  assert(Tempest::Log::lines.size()==6);
  assert(Tempest::Log::lines[1].find("total-ms=30.5")!=std::string::npos);
  assert(Tempest::Log::lines[2].find("largest")!=std::string::npos);
  assert(Tempest::Log::lines[5].find("small")!=std::string::npos);
  Tempest::Log::lines.clear();
  m.logGpu(std::vector<Timing>{{"ShadowMap #0",0.5},{"ShadowMap #0 solid",2},{"ShadowMap #0 alpha",4},{"ShadowMap #0 particles",0.25},
    {"ShadowMap #1",1},{"ShadowMap #1 solid",3},{"ShadowMap #1 alpha",5},{"ShadowMap #1 particles",0.5},{"SSAO",8}});
  assert(Tempest::Log::lines[1].find("layer=0 total-ms=6.75 solid-ms=2 alpha-ms=4 particles-ms=0.25 setup-ms=0.5")!=std::string::npos);
  assert(Tempest::Log::lines[2].find("layer=1 total-ms=9.5 solid-ms=3 alpha-ms=5 particles-ms=0.5 setup-ms=1")!=std::string::npos);
  assert(Tempest::Log::lines[0].find("total-ms=24.25")!=std::string::npos);
  auto reset=[](){AndroidSsaoLazy38::state()={};AndroidSsaoLazy38::configure(true);};
  auto send=[](bool fused,double mask,double apply,double total){
    std::vector<Timing> t{{"Other",total-mask-apply}};
    t.push_back({fused ? "SSAO lazy half" : "SSAO original half",fused ? apply : mask+apply});
    AndroidSsaoLazy38::observe(t);
  };
  reset();send(false,6,2,43);assert(AndroidSsaoLazy38::useFused());
  send(true,0,6,40);assert(AndroidSsaoLazy38::useFused());
  send(true,0,6,40);assert(!AndroidSsaoLazy38::useFused());
  send(false,6,2,43);assert(!AndroidSsaoLazy38::useFused());
  reset();for(int i=0;i<8;++i){send(false,6,2,43);send(true,0,6,40);}
  assert(AndroidSsaoLazy38::state().decided && AndroidSsaoLazy38::useFused());
  send(true,0,100,150);assert(AndroidSsaoLazy38::useFused()); // Choice frozen.
  reset();for(int i=0;i<8;++i){send(false,6,2,43);send(true,0,6,43);}
  assert(!AndroidSsaoLazy38::useFused()); // Moving work out of the SSAO marker cannot pass the whole-frame gate.
  reset();for(int i=0;i<8;++i){send(false,6,2,43);send(true,0,7.7,39);}
  assert(!AndroidSsaoLazy38::useFused()); // <5% SSAO gain insufficient.
  reset();for(int i=0;i<8;++i){send(false,6,2,43);send(true,0,i<5?6:9,39);}
  assert(!AndroidSsaoLazy38::useFused()); // SSAO median alone insufficient.
  reset();for(int i=0;i<8;++i){send(false,6,2,43);send(true,0,6,i<5?39:44);}
  assert(!AndroidSsaoLazy38::useFused()); // Frame median alone insufficient.
  reset();AndroidSsaoLazy38::observe(std::vector<Timing>{{"SSAO original half",6},{"SSAO lazy half",6}});
  AndroidSsaoLazy38::observe(std::vector<Timing>{{"SSAO lazy half",6},{"SSAO lazy half",6}});
  AndroidSsaoLazy38::observe(std::vector<Timing>{{"SSAO lazy half",NAN}});
  AndroidSsaoLazy38::observe(std::vector<Timing>{{"SSAO lazy half",-1}});
  AndroidSsaoLazy38::observe(std::vector<Timing>{{"SSAO upsample",1}});
  assert(AndroidSsaoLazy38::state().no==0 && AndroidSsaoLazy38::state().nf==0);
  send(false,6,2,43);AndroidSsaoLazy38::finish();assert(!AndroidSsaoLazy38::useFused());
  reset();AndroidSsaoLazy38::configure(false);send(false,6,2,43);
  assert(AndroidSsaoLazy38::state().no==0 && !AndroidSsaoLazy38::useFused());
  puts("PASS: paired SSAO aggregation, whole-frame gate, ABBA, paired wins, incomplete/mixed/invalid samples and frozen fallback.");
  puts("PASS: frame timing units, summary cadence, skipped count, top GPU passes and 24-sample budget.");
}
''')
    subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Wconversion','-Wsign-conversion','-Werror','-I'+str(p),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True,timeout=10)
