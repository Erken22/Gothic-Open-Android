#!/usr/bin/env python3
"""Execute the real material-selection patch with deterministic device properties."""
import ast,pathlib,subprocess,tempfile
repo=pathlib.Path(__file__).resolve().parent.parent
function=None;policy=None;rtsm=None
for n in ast.walk(ast.parse((repo/'apply_067.py').read_text())):
    if not isinstance(n,ast.Call) or not isinstance(n.func,ast.Name) or n.func.id!='replace_once':continue
    path=ast.literal_eval(n.args[0])
    if path!='common/graphics/shaders.cpp':continue
    old,new=map(ast.literal_eval,n.args[1:3])
    if old.startswith('static bool hasBindless()'):function=new
    if old.startswith('  opts.doMeshShading '):policy=new.split('\n',1)[1]
    if old.startswith('bool Shaders::isRtsmSupported()'):rtsm=new
assert function and policy and rtsm
stub=r'''
#include <cstdint>
#include <string_view>
#include <cstring>
#include <cassert>
#include <cstdio>
struct Log {template<class... Args> static void i(const Args&...){}};
enum class TextureFormat {RG32U,R11G11B10UF};
struct Props {struct {uint32_t maxInvocations=1024,maxSharedMemory=65536;} compute;bool hasStorageFormat(TextureFormat)const{return true;} char name[64]="Turnip Adreno (TM) 650";struct {bool nonUniformIndexing=true;uint32_t maxTexture=65000,maxStorage=65000;} descriptors;};
struct Device {Props props;const Props& properties()const{return props;}};
namespace Resources {static Device value;Device& device(){return value;}}
static bool turnip=true;
extern "C" int opengothic_vulkan_is_turnip(){return turnip?1:0;}
struct Options {bool doBindless=true,doRtScene=true,doRayQuery=true,doMeshShading=true;};
struct Shaders {inline static Options value;static const Options& options(){return value;} static bool isRtsmSupported();};
'''
main=r'''
int main(){
  auto& p=Resources::value.props;
  assert(hasBindless());
  p.descriptors.maxTexture=64999;assert(!hasBindless());p.descriptors.maxTexture=65000;
  p.descriptors.maxStorage=64999;assert(!hasBindless());p.descriptors.maxStorage=65000;
  p.descriptors.nonUniformIndexing=false;assert(!hasBindless());p.descriptors.nonUniformIndexing=true;
#if defined(__ANDROID__)
  assert(!Shaders::isRtsmSupported());
  Options o;applyPolicy(o);assert(o.doBindless && o.doRtScene && !o.doRayQuery && !o.doMeshShading);
  o=Options{};o.doBindless=false;applyPolicy(o);assert(!o.doBindless && !o.doRayQuery && !o.doMeshShading);
  turnip=false;assert(Shaders::isRtsmSupported());assert(!hasBindless());o=Options{};applyPolicy(o);assert(o.doBindless && o.doRayQuery && o.doMeshShading);
  turnip=true;std::strcpy(p.name,"Adreno 650");assert(!hasBindless());
  std::strcpy(p.name,"Turnip Adreno 740");assert(!hasBindless());
#else
  turnip=false;assert(hasBindless());assert(Shaders::isRtsmSupported());Options o;applyPolicy(o);assert(o.doRayQuery && o.doMeshShading);
#endif
  std::strcpy(p.name,"Mali G78");assert(hasBindless());
  puts("PASS: real bindless capability gates and qualified-driver policy; existing rendering stages preserved.");
}
'''
with tempfile.TemporaryDirectory(prefix='gothic-material-test-') as tmp:
    p=pathlib.Path(tmp);src=p/'test.cpp';src.write_text(stub+function+rtsm+'\nvoid applyPolicy(Options& opts){\n'+policy+'\n(void)opts;\n}\n'+main)
    for platform in ['android','desktop']:
        cmd=['g++','-std=c++20','-Wall','-Wextra','-Wconversion','-Wsign-conversion','-Werror']
        if platform=='android':cmd.append('-D__ANDROID__')
        subprocess.run(cmd+[str(src),'-o',str(p/platform)],check=True)
        subprocess.run([str(p/platform)],check=True,timeout=10)
