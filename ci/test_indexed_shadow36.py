#!/usr/bin/env python3
"""Execute the real index codec; check indirect ABI, memory and synchronization contracts."""
from pathlib import Path
import subprocess,sys,tempfile,re
root=Path(sys.argv[1]);b=(root/'shader/materials/shadow_index_build36.comp').read_text();v=(root/'shader/materials/shadow_index36.vert').read_text();init=(root/'shader/materials/shadow_index_init36.comp').read_text()
helper=b[b.index('uint encodeIndex36'):b.index('\nvoid main()')]
assert 'gl_VertexIndex)/64u' in v and 'gl_VertexIndex)%64u' in v
assert 'payload[workIndex + firstMeshlet]' in v
assert 'processPrimitive(meshletId, bucketId, laneID)[gl_VertexIndex%3]' not in v
assert 'nonuniformEXT uint bucketId=task.z;' in b
assert '(last&255u)==((last>>8u)&255u)' in b
assert 'args.firstInstance=0u;' in init and 'args.vertexOffset=0;' in init
# Vertex transforms, VBO addressing, projection and original shaders remain untouched.
a=(root/'shader/materials/main.vert').read_text()
for start,end in [('vec4  processVertex(out Varyings var','\n#if defined(GL_VERTEX_SHADER)\nvoid vertexShader'),('uvec2 processMeshlet','vec4  processVertex(out Varyings var')]:
 assert a[a.index(start):a.index(end)]==v[v.index(start):v.index(end)]
r=(root/'common/graphics/drawcommands.cpp').read_text()
for lit in ['c.type!=Landscape || c.alpha!=Material::Solid || !c.isBindless()', 'scene.vsmEnabled','indexAllocationFailed36','32u*1024u*1024u','64u*1024u*1024u-bytes','dispatchIndirect(c.shadowArgs36,20)','cmd.drawIndexedIndirect(cx.shadowIndices36,cx.shadowArgs36,0)']:
 assert lit in r
api=(root/'lib/Tempest/Engine/gapi/vulkan/vcommandbuffer.cpp').read_text()
fn=api[api.index('void VCommandBuffer::drawIndexedIndirect'):api.index('void VCommandBuffer::drawIndirect')]
for lit in ['idx.nonUniqId,NonUniqResId::I_None,PipelineStage::S_Graphics','ind.nonUniqId,NonUniqResId::I_None,PipelineStage::S_Indirect','VK_INDEX_TYPE_UINT32','VkDeviceSize(offset),1,0']:
 assert lit in fn
# Existing SSBO creation includes INDEX usage; no global allocator policy changed.
d=(root/'lib/Tempest/Engine/graphics/device.h').read_text();assert 'MemUsage::VertexBuffer  | MemUsage::IndexBuffer   | MemUsage::Indirect' in d
enc=(root/'lib/Tempest/Engine/graphics/encoder.cpp').read_text();assert 'indirect.byteSize()-offset<20' in enc
cpp=r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <random>
#include <vector>
#include <vulkan/vulkan.h>
using uint=uint32_t;
struct uvec3{uint x,y,z;explicit uvec3(uint a):x(a),y(a),z(a){}uvec3(uint a,uint b,uint c):x(a),y(b),z(c){}};
struct Record {VkDrawIndexedIndirectCommand draw;VkDispatchIndirectCommand dispatch;};
static_assert(sizeof(Record)==32 && offsetof(Record,dispatch)==20);
'''+helper+r'''
int main(){
 std::mt19937 gen(36067);uint64_t checked=0;
 for(uint test=0;test<12000;++test){
  uint count=test%65,slot=gen()%43690;
  for(uint tri=0;tri<64;++tri){
   uint x=gen()%64,y=gen()%64,z=gen()%64;
   uint packed=x|(y<<8u)|(z<<16u);
   auto out=expandTriangle36(slot,tri,count,packed);
   uint got[]={out.x,out.y,out.z};uint expected[]={x,y,z};
   for(uint k=0;k<3;++k){
    assert(got[k]/64u==slot);
    if(tri<count)assert(got[k]%64u==expected[k]);
    else assert(got[k]==encodeIndex36(slot,0));
    assert(got[k]<43690u*64u);++checked;
   }
  }
 }
 // Shared vertices now get identical input indices within a payload slot.
 auto p=expandTriangle36(17,0,2,0u|(1u<<8)|(2u<<16));
 auto q=expandTriangle36(17,1,2,2u|(1u<<8)|(3u<<16));
 assert(p.y==q.y && p.z==q.x);
 assert(encodeIndex36(18,1)!=p.y); // Never share transforms between instances/meshlets.
 for(uint n:{0u,1u,63u,43690u}){Record rec{{n*192u,1,0,0,0},{n,1,1}};assert(rec.draw.indexCount==n*192u && rec.dispatch.x==n);}
 // Cap arithmetic avoids multiplication overflow and invalid signed gl_VertexIndex.
 assert(32u*1024u*1024u/(192u*4u)==43690u);
 assert(43690u*192u*4u<=32u*1024u*1024u);
 printf("PASS: %llu actual codec index checks; 0..64 triangles, random buckets/local vertices, slot isolation, winding/order, degenerate padding, shared vertices, 20/32-byte ABI and bounded arithmetic. GPU pixels/performance remain unverified.\n",(unsigned long long)checked);
}
'''
headers=Path(sys.argv[2])
with tempfile.TemporaryDirectory() as t:
 p=Path(t);(p/'test.cpp').write_text(cpp)
 subprocess.run(['g++','-std=c++20','-O2','-Wall','-Wextra','-Werror','-I'+str(headers/'include'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
# Compile and run the actual Vulkan forwarding method with recording mocks.
method=fn.replace('void VCommandBuffer::drawIndexedIndirect','void VCommandBuffer::drawIndexedIndirect')
mock=r'''
#define VK_USE_64_BIT_PTR_DEFINES 0
#include <vulkan/vulkan.h>
#include <cassert>
#include <cstddef>
#include <vector>
struct AbstractGraphicsApi {struct Buffer{virtual ~Buffer()=default;};};
enum class NonUniqResId{I_None=0};
enum class PipelineStage{S_Graphics,S_Indirect};
struct VBuffer:AbstractGraphicsApi::Buffer{int nonUniqId;VkBuffer impl;VBuffer(int id,uint64_t b):nonUniqId(id),impl(b){}};
std::vector<int> events;
struct Tracker{void onUavUsage(int id,NonUniqResId,PipelineStage s){events.push_back(s==PipelineStage::S_Graphics?100+id:200+id);}};
struct VCommandBuffer{Tracker resState;VkCommandBuffer impl=nullptr;void implSetUniforms(PipelineStage){events.push_back(1);}void implSetPushData(PipelineStage){events.push_back(2);}void drawIndexedIndirect(const AbstractGraphicsApi::Buffer&,const AbstractGraphicsApi::Buffer&,size_t);};
VKAPI_ATTR void VKAPI_CALL vkCmdBindIndexBuffer(VkCommandBuffer,VkBuffer b,VkDeviceSize o,VkIndexType t){assert(b==7 && o==0 && t==VK_INDEX_TYPE_UINT32);events.push_back(3);}
VKAPI_ATTR void VKAPI_CALL vkCmdDrawIndexedIndirect(VkCommandBuffer,VkBuffer b,VkDeviceSize o,uint32_t n,uint32_t stride){assert(b==8 && o==40 && n==1 && stride==0);events.push_back(4);}
'''+method+r'''
int main(){VBuffer idx(7,7),ind(8,8);VCommandBuffer cb;cb.drawIndexedIndirect(idx,ind,40);assert((events==std::vector<int>{107,208,1,2,3,4}));}
'''
with tempfile.TemporaryDirectory() as t:
 p=Path(t);(p/'test.cpp').write_text(mock)
 subprocess.run(['g++','-std=c++20','-O2','-Wall','-Wextra','-Werror','-I'+str(headers/'include'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('PASS: actual Vulkan indexed forwarding registers index/indirect reads before binding/draw; uint32 indices, offset and one-command ABI preserved.')
