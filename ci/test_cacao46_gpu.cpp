// Headless correctness smoke test. Software Vulkan timings are NOT phone benchmarks.
#include "gapi/vulkan/vulkan_sdk.h"
#include "ffx_cacao_impl.h"
#include <algorithm>
#include <cassert>
#include <cstdlib>
#include <cstdio>
#include <cstring>
#include <vector>
static void ok(VkResult r){if(r!=VK_SUCCESS){std::fprintf(stderr,"VkResult=%d\n",int(r));std::abort();}}
static unsigned validationErrors=0;
static VKAPI_ATTR VkBool32 VKAPI_CALL validation(VkDebugUtilsMessageSeverityFlagBitsEXT severity,VkDebugUtilsMessageTypeFlagsEXT,const VkDebugUtilsMessengerCallbackDataEXT* data,void*) {
 if(severity&VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT){++validationErrors;std::fprintf(stderr,"VALIDATION ERROR: %s\n",data->pMessage);}
 return VK_FALSE;
}
int main(int argc,char** argv){
 VkApplicationInfo app{VK_STRUCTURE_TYPE_APPLICATION_INFO};app.apiVersion=VK_API_VERSION_1_1;
 VkInstanceCreateInfo ii{VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};ii.pApplicationInfo=&app;
 const char* layer="VK_LAYER_KHRONOS_validation";const char* extension=VK_EXT_DEBUG_UTILS_EXTENSION_NAME;
 ii.enabledLayerCount=1;ii.ppEnabledLayerNames=&layer;ii.enabledExtensionCount=1;ii.ppEnabledExtensionNames=&extension;
 VkDebugUtilsMessengerCreateInfoEXT debug{VK_STRUCTURE_TYPE_DEBUG_UTILS_MESSENGER_CREATE_INFO_EXT};
 debug.messageSeverity=VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT;
 debug.messageType=VK_DEBUG_UTILS_MESSAGE_TYPE_GENERAL_BIT_EXT|VK_DEBUG_UTILS_MESSAGE_TYPE_VALIDATION_BIT_EXT|VK_DEBUG_UTILS_MESSAGE_TYPE_PERFORMANCE_BIT_EXT;debug.pfnUserCallback=validation;ii.pNext=&debug;
 VkInstance instance{};ok(vkCreateInstance(&ii,nullptr,&instance));
 auto createDebug=reinterpret_cast<PFN_vkCreateDebugUtilsMessengerEXT>(vkGetInstanceProcAddr(instance,"vkCreateDebugUtilsMessengerEXT"));
 auto destroyDebug=reinterpret_cast<PFN_vkDestroyDebugUtilsMessengerEXT>(vkGetInstanceProcAddr(instance,"vkDestroyDebugUtilsMessengerEXT"));assert(createDebug && destroyDebug);
 VkDebugUtilsMessengerEXT messenger{};ok(createDebug(instance,&debug,nullptr,&messenger));
 uint32_t count=0;ok(vkEnumeratePhysicalDevices(instance,&count,nullptr));assert(count);
 std::vector<VkPhysicalDevice> devices(count);ok(vkEnumeratePhysicalDevices(instance,&count,devices.data()));auto physical=devices[0];
 VkPhysicalDeviceProperties props{};vkGetPhysicalDeviceProperties(physical,&props);std::printf("Device: %s (correctness only)\n",props.deviceName);std::fflush(stdout);
 VkPhysicalDeviceFeatures supported{};vkGetPhysicalDeviceFeatures(physical,&supported);
 std::printf("storageExtended=%u gatherExtended=%u\n",supported.shaderStorageImageExtendedFormats,supported.shaderImageGatherExtended);std::fflush(stdout);
 if(!supported.shaderStorageImageExtendedFormats || !supported.shaderImageGatherExtended) return 77;
 VkPhysicalDeviceFeatures features{};features.shaderStorageImageExtendedFormats=VK_TRUE;features.shaderImageGatherExtended=VK_TRUE;
 vkGetPhysicalDeviceQueueFamilyProperties(physical,&count,nullptr);std::vector<VkQueueFamilyProperties> families(count);vkGetPhysicalDeviceQueueFamilyProperties(physical,&count,families.data());
 uint32_t family=0;while(family<count && !(families[family].queueFlags&VK_QUEUE_COMPUTE_BIT))++family;assert(family<count);
 float priority=1;VkDeviceQueueCreateInfo qi{VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO};qi.queueFamilyIndex=family;qi.queueCount=1;qi.pQueuePriorities=&priority;
 VkDeviceCreateInfo di{VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO};di.queueCreateInfoCount=1;di.pQueueCreateInfos=&qi;di.pEnabledFeatures=&features;
 VkDevice device{};ok(vkCreateDevice(physical,&di,nullptr,&device));VkQueue queue{};vkGetDeviceQueue(device,family,0,&queue);
 VkPhysicalDeviceMemoryProperties mem{};vkGetPhysicalDeviceMemoryProperties(physical,&mem);
 auto allocate=[&](VkMemoryRequirements req,VkMemoryPropertyFlags flags){
  uint32_t index=0;while(index<mem.memoryTypeCount && (!(req.memoryTypeBits&(1u<<index)) || (mem.memoryTypes[index].propertyFlags&flags)!=flags))++index;assert(index<mem.memoryTypeCount);
  VkMemoryAllocateInfo ai{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};ai.allocationSize=req.size;ai.memoryTypeIndex=index;VkDeviceMemory out{};ok(vkAllocateMemory(device,&ai,nullptr,&out));return out;
 };
 const uint32_t W=argc>1 ? 129 : 128,H=argc>1 ? 131 : 128;
 struct Image {VkImage image;VkImageView view;VkDeviceMemory memory;};
 auto image=[&](VkFormat format,VkImageUsageFlags usage,VkImageAspectFlags aspect){
  Image out{};VkImageCreateInfo ci{VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO};ci.imageType=VK_IMAGE_TYPE_2D;ci.format=format;ci.extent={W,H,1};ci.mipLevels=1;ci.arrayLayers=1;ci.samples=VK_SAMPLE_COUNT_1_BIT;ci.tiling=VK_IMAGE_TILING_OPTIMAL;ci.usage=usage;ci.sharingMode=VK_SHARING_MODE_EXCLUSIVE;ok(vkCreateImage(device,&ci,nullptr,&out.image));
  VkMemoryRequirements req{};vkGetImageMemoryRequirements(device,out.image,&req);out.memory=allocate(req,VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);ok(vkBindImageMemory(device,out.image,out.memory,0));
  VkImageViewCreateInfo vi{VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO};vi.image=out.image;vi.viewType=VK_IMAGE_VIEW_TYPE_2D;vi.format=format;vi.subresourceRange={aspect,0,1,0,1};ok(vkCreateImageView(device,&vi,nullptr,&out.view));return out;
 };
 auto depth=image(VK_FORMAT_D32_SFLOAT,VK_IMAGE_USAGE_SAMPLED_BIT|VK_IMAGE_USAGE_TRANSFER_DST_BIT|VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT,VK_IMAGE_ASPECT_DEPTH_BIT);
 auto output=image(VK_FORMAT_R8_UNORM,VK_IMAGE_USAGE_STORAGE_BIT|VK_IMAGE_USAGE_SAMPLED_BIT|VK_IMAGE_USAGE_TRANSFER_SRC_BIT,VK_IMAGE_ASPECT_COLOR_BIT);
 struct Buffer{VkBuffer buffer;VkDeviceMemory memory;};
 auto buffer=[&](size_t size,VkBufferUsageFlags usage){Buffer out{};VkBufferCreateInfo ci{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};ci.size=size;ci.usage=usage;ci.sharingMode=VK_SHARING_MODE_EXCLUSIVE;ok(vkCreateBuffer(device,&ci,nullptr,&out.buffer));VkMemoryRequirements req{};vkGetBufferMemoryRequirements(device,out.buffer,&req);out.memory=allocate(req,VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);ok(vkBindBufferMemory(device,out.buffer,out.memory,0));return out;};
 auto upload=buffer(W*H*sizeof(float),VK_BUFFER_USAGE_TRANSFER_SRC_BIT),download=buffer(W*H,VK_BUFFER_USAGE_TRANSFER_DST_BIT);
 VkCommandPoolCreateInfo pi{VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO};pi.queueFamilyIndex=family;pi.flags=VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;VkCommandPool pool{};ok(vkCreateCommandPool(device,&pi,nullptr,&pool));
 VkCommandBufferAllocateInfo ca{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};ca.commandPool=pool;ca.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY;ca.commandBufferCount=1;VkCommandBuffer cmd{};ok(vkAllocateCommandBuffers(device,&ca,&cmd));
 auto* context=static_cast<FFX_CACAO_VkContext*>(std::calloc(1,FFX_CACAO_VkGetContextSize()));assert(context);
 FFX_CACAO_VkCreateInfo create{};create.physicalDevice=physical;create.device=device;assert(FFX_CACAO_VkInitContext(context,&create)==FFX_CACAO_STATUS_OK);
 FFX_CACAO_VkScreenSizeInfo screen{};screen.width=W;screen.height=H;screen.depthView=depth.view;screen.output=output.image;screen.outputView=output.view;screen.useDownsampledSsao=argc>2 ? FFX_CACAO_FALSE : FFX_CACAO_TRUE;
 assert(FFX_CACAO_VkInitScreenSizeDependentResources(context,&screen)==FFX_CACAO_STATUS_OK);
 auto settings=FFX_CACAO_DEFAULT_SETTINGS;settings.radius=1.f;settings.qualityLevel=FFX_CACAO_QUALITY_HIGH;settings.generateNormals=FFX_CACAO_TRUE;settings.fadeOutFrom=500.f;settings.fadeOutTo=1000.f;assert(FFX_CACAO_VkUpdateSettings(context,&settings)==FFX_CACAO_STATUS_OK);
 FFX_CACAO_Matrix4x4 projection{};float near=10.f,far=100000.f,k=far/(far-near);projection.elements[0][0]=projection.elements[1][1]=1.5f;projection.elements[2][2]=k;projection.elements[2][3]=1;projection.elements[3][2]=-near*k*0.01f;
 int minima[3]{};
 for(int test=0;test<3;++test){
  std::vector<float> data(W*H, test==0 ? 1.f : k-near*k/500.f);
  if(test==2)for(unsigned y=32;y<96;++y)for(unsigned x=32;x<96;++x)data[y*W+x]=k-near*k/450.f;
  void* map{};ok(vkMapMemory(device,upload.memory,0,data.size()*4,0,&map));std::memcpy(map,data.data(),data.size()*4);vkUnmapMemory(device,upload.memory);
  ok(vkResetCommandBuffer(cmd,0));VkCommandBufferBeginInfo bi{VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};ok(vkBeginCommandBuffer(cmd,&bi));
  VkImageMemoryBarrier b{VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER};b.image=depth.image;b.srcQueueFamilyIndex=b.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED;b.subresourceRange={VK_IMAGE_ASPECT_DEPTH_BIT,0,1,0,1};b.oldLayout=test ? VK_IMAGE_LAYOUT_DEPTH_STENCIL_READ_ONLY_OPTIMAL : VK_IMAGE_LAYOUT_UNDEFINED;b.newLayout=VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;b.srcAccessMask=test ? VK_ACCESS_SHADER_READ_BIT : 0;b.dstAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;
  vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,nullptr,0,nullptr,1,&b);
  VkBufferImageCopy copy{};copy.imageSubresource={VK_IMAGE_ASPECT_DEPTH_BIT,0,0,1};copy.imageExtent={W,H,1};vkCmdCopyBufferToImage(cmd,upload.buffer,depth.image,VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,1,&copy);
  b.oldLayout=b.newLayout;b.newLayout=VK_IMAGE_LAYOUT_DEPTH_STENCIL_READ_ONLY_OPTIMAL;b.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;b.dstAccessMask=VK_ACCESS_SHADER_READ_BIT;vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,0,0,nullptr,0,nullptr,1,&b);
  assert(FFX_CACAO_VkDraw(context,cmd,&projection,nullptr)==FFX_CACAO_STATUS_OK);
  b.image=output.image;b.subresourceRange.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT;b.oldLayout=VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;b.newLayout=VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;b.srcAccessMask=VK_ACCESS_SHADER_WRITE_BIT;b.dstAccessMask=VK_ACCESS_TRANSFER_READ_BIT;vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,nullptr,0,nullptr,1,&b);
  copy.imageSubresource.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT;vkCmdCopyImageToBuffer(cmd,output.image,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,download.buffer,1,&copy);
  VkMemoryBarrier host{VK_STRUCTURE_TYPE_MEMORY_BARRIER};host.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;host.dstAccessMask=VK_ACCESS_HOST_READ_BIT;vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_HOST_BIT,0,1,&host,0,nullptr,0,nullptr);
  ok(vkEndCommandBuffer(cmd));VkSubmitInfo submit{VK_STRUCTURE_TYPE_SUBMIT_INFO};submit.commandBufferCount=1;submit.pCommandBuffers=&cmd;ok(vkQueueSubmit(queue,1,&submit,VK_NULL_HANDLE));ok(vkQueueWaitIdle(queue));
  ok(vkMapMemory(device,download.memory,0,W*H,0,&map));auto* pixels=static_cast<unsigned char*>(map);auto [low,high]=std::minmax_element(pixels,pixels+W*H);unsigned long sum=0;for(unsigned i=0;i<W*H;++i)sum+=pixels[i];minima[test]=*low;
  unsigned innerMin=255;for(unsigned y=8;y<H-8;++y)for(unsigned x=8;x<W-8;++x)innerMin=std::min(innerMin,unsigned(pixels[y*W+x]));
  std::printf("interior-min=%u min-xy=(%u,%u) ",innerMin,unsigned(low-pixels)%W,unsigned(low-pixels)/W);
  char filename[80];std::snprintf(filename,sizeof(filename),"/tmp/cacao46-case%d.pgm",test);FILE* file=std::fopen(filename,"wb");std::fprintf(file,"P5\n%u %u\n255\n",W,H);std::fwrite(pixels,1,W*H,file);std::fclose(file);std::printf("case=%d AO min=%u max=%u mean=%.3f\n",test,unsigned(*low),unsigned(*high),double(sum)/(W*H));vkUnmapMemory(device,download.memory);
 }
 assert(minima[0]>=250 && minima[1]>=250 && minima[2]<240);
 FFX_CACAO_VkDestroyScreenSizeDependentResources(context);FFX_CACAO_VkDestroyContext(context);std::free(context);
 for(auto b:{upload,download}){vkDestroyBuffer(device,b.buffer,nullptr);vkFreeMemory(device,b.memory,nullptr);}
 for(auto i:{depth,output}){vkDestroyImageView(device,i.view,nullptr);vkDestroyImage(device,i.image,nullptr);vkFreeMemory(device,i.memory,nullptr);}
 vkDestroyCommandPool(device,pool,nullptr);vkDestroyDevice(device,nullptr);destroyDebug(instance,messenger,nullptr);vkDestroyInstance(instance,nullptr);
 assert(validationErrors==0);
 std::puts("PASS: complete upstream Vulkan FP32 chain, sky/flat neutral AO and nontrivial contact response");
}
