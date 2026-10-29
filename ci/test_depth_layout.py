#!/usr/bin/env python3
"""Check real Vulkan layout mapping against the backend's attachment declarations."""
import pathlib,re,subprocess,sys,tempfile
root=pathlib.Path(sys.argv[1]);headers=pathlib.Path(sys.argv[2]).resolve()
s=(root/'lib/Tempest/Engine/gapi/vulkan/vcommandbuffer.cpp').read_text()
a=s.index('static VkImageLayout toLayout(');b=s.index('\nstatic VkImage toVkResource',a)
fn=s[a:b]
assert 'att.imageLayout = VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL;' in s
assert 'att.imageLayout = VK_IMAGE_LAYOUT_DEPTH_STENCIL_READ_ONLY_OPTIMAL;' in s
stub=r'''
#include <vulkan/vulkan.h>
#include <cassert>
#include <cstdio>
enum class ResourceLayout {None,TransferSrc,TransferDst,Default,ColorAttach,DepthReadOnly,DepthAttach};
struct VTexture {VkFormat format;bool isStorageImage=false;};
bool nativeIsDepthFormat(VkFormat f){return f==VK_FORMAT_D16_UNORM || f==VK_FORMAT_D32_SFLOAT || f==VK_FORMAT_D24_UNORM_S8_UINT;}
'''
main=r'''
int main(){
 for(auto f:{VK_FORMAT_D16_UNORM,VK_FORMAT_D32_SFLOAT,VK_FORMAT_D24_UNORM_S8_UINT}){
  VTexture t{f};assert(toLayout(ResourceLayout::DepthAttach,&t)==VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL);
  assert(toLayout(ResourceLayout::DepthReadOnly,&t)==VK_IMAGE_LAYOUT_DEPTH_STENCIL_READ_ONLY_OPTIMAL);
  assert(toLayout(ResourceLayout::Default,&t)==VK_IMAGE_LAYOUT_DEPTH_STENCIL_READ_ONLY_OPTIMAL);
 }
 VTexture t{VK_FORMAT_R8G8B8A8_UNORM};
 assert(toLayout(ResourceLayout::Default,&t)==VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL);
 t.isStorageImage=true;assert(toLayout(ResourceLayout::Default,&t)==VK_IMAGE_LAYOUT_GENERAL);
 assert(toLayout(ResourceLayout::Default,nullptr)==VK_IMAGE_LAYOUT_PRESENT_SRC_KHR);
 assert(toLayout(ResourceLayout::None,&t)==VK_IMAGE_LAYOUT_UNDEFINED);
 assert(toLayout(ResourceLayout::TransferSrc,&t)==VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL);
 assert(toLayout(ResourceLayout::TransferDst,&t)==VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL);
 assert(toLayout(ResourceLayout::ColorAttach,&t)==VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL);
 puts("PASS: real depth transition layouts match rendering attachments; color, storage, transfer and presentation mappings preserved.");
}
'''
with tempfile.TemporaryDirectory(prefix='depth-layout-') as tmp:
 p=pathlib.Path(tmp);(p/'test.cpp').write_text('#include <initializer_list>\n'+stub+fn+main)
 subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror','-I'+str(headers/'include'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
