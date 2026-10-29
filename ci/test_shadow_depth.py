#!/usr/bin/env python3
"""Execute the real patched vertex pipeline branch with shader/device recorders."""
import ast,pathlib,subprocess,tempfile
repo=pathlib.Path(__file__).resolve().parent.parent
branch=None
for n in ast.walk(ast.parse((repo/'apply_067.py').read_text())):
 if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='replace_once':
  if ast.literal_eval(n.args[0])!='common/graphics/shaders.cpp':continue
  old,new=map(ast.literal_eval,n.args[1:3])
  if old.startswith('  else if(t!=DrawCommands::Pfx) {') and 'vertexOnlyShadow' in new:branch=new
assert branch
stub=r'''
#include <cassert>
#include <cstdio>
#include <string>
#include <vector>
#include <string_view>
struct Shader {bool present=false;};
struct Source {const char* data=nullptr;size_t len=0;};
struct Device {int shaders=0;bool fragment=false;Shader shader(const char*,size_t){++shaders;return {true};}int pipeline(int,int,const Shader& vs,const Shader& fs){assert(vs.present);fragment=fs.present;return 1;}};
struct Log {template<class... T>static void i(const T&...){}};
namespace Material {enum Alpha {Solid,AlphaTest,Transparent};}
namespace DrawCommands {enum Type {Landscape,Static,Movable,Animated,Morph,Pfx};}
enum Pass {T_Shadow,T_Depth,T_Main,T_Vsm};
constexpr int Triangles=0;
bool target=false;
bool isTurnipAdreno650(){return target;}
std::vector<std::string> sources;
std::string string_frm(const char* a,const char* b,const char* c,const char* d,const char* e){return std::string(a)+b+c+d+e;}
Source shaderSource(const std::string& s){sources.push_back(s);return {};}
bool run(bool qualified,Material::Alpha alpha,Pass pt,DrawCommands::Type t){
 target=qualified;Device device;int state=7;struct {int pipeline=0;} b;
 const char* vsTok="obj";const char* typeVs="_d";const char* fsTok="obj";const char* typeFs="_d";const char* shaderSuffix="_bindless";
 if(false){}
'''
end=r'''
 assert(b.pipeline==1);
 assert(device.shaders==(device.fragment?2:1));
 return device.fragment;
}
int main(){
 for(bool targetMode:{false,true})for(auto alpha:{Material::Solid,Material::AlphaTest,Material::Transparent})
 for(auto pt:{T_Shadow,T_Depth,T_Main,T_Vsm})for(auto type:{DrawCommands::Landscape,DrawCommands::Static,DrawCommands::Movable,DrawCommands::Animated,DrawCommands::Morph}){
   sources.clear();bool fragment=run(targetMode,alpha,pt,type);
   const bool omit=targetMode && alpha==Material::Solid && pt==T_Shadow;
   assert(fragment==!omit);assert(sources.size()==(omit?1u:2u));
   assert(sources[0]=="main_obj_d_bindless.vert.sprv");
   if(!omit)assert(sources[1]=="main_obj_d_bindless.frag.sprv");
 }
 puts("PASS: real vertex pipeline branch omits only qualified opaque shadow fragments; same vertex source/state and all other fragment paths retained.");
}
'''
with tempfile.TemporaryDirectory(prefix='shadow-depth-test-') as tmp:
 p=pathlib.Path(tmp);(p/'test.cpp').write_text(stub+branch+end)
 subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Wconversion','-Wsign-conversion','-Werror',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
