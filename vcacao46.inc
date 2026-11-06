// Tempest bridge for the complete upstream CACAO Vulkan backend.
// One context per fenced command buffer: no shared scratch images or UBO races.
#if defined(TEMPEST_CACAO46)
#include "thirdparty/cacao46/inc/ffx_cacao_impl.h"
#include <cstdlib>
#include <cstring>
#include <cmath>

struct VCommandBuffer::Cacao46 {
  FFX_CACAO_VkContext* context=nullptr;
  bool core=false,screen=false,failed=false,downsampled=false;
  VkImageView depth=VK_NULL_HANDLE,output=VK_NULL_HANDLE;
  uint32_t width=0,height=0;
  ~Cacao46() {
    if(screen) FFX_CACAO_VkDestroyScreenSizeDependentResources(context);
    if(core) FFX_CACAO_VkDestroyContext(context);
    std::free(context);
    }
  };
#endif

bool VCommandBuffer::renderCacao46(AbstractGraphicsApi::Texture& depthTex,
                                 AbstractGraphicsApi::Texture& outputTex,
                                 uint32_t width,uint32_t height,const float* projection,bool half) {
#if defined(TEMPEST_CACAO46)
  if(!device.cacao46Enabled || device.props.hasDescriptorHeap || width<16 || height<16 ||
     state==RenderPass || state==NoRecording) return false;
  if(!cacao46) cacao46=std::make_unique<Cacao46>();
  auto& c=*cacao46;
  if(c.failed) return false;
  // Tempest's columns have the same memory arrangement as CACAO's row-vector matrix.
  // Scale only depth-unpack numerator: Gothic centimetres -> metres, avoiding
  // R16F working-depth overflow at the game's 100000-unit far plane.
  FFX_CACAO_Matrix4x4 proj{};
  for(unsigned i=0;i<16;++i) {
    if(!std::isfinite(projection[i])) return false;
    proj.elements[i/4][i%4]=projection[i];
    }
  if(projection[0]<=0 || projection[5]<=0 || projection[11]!=1.f ||
     projection[14]>=0 || projection[15]!=0.f) return false;
  for(unsigned i: {1u,2u,3u,4u,6u,7u,8u,9u,12u,13u})
    if(projection[i]!=0.f) return false; // nonstandard/morphed/off-axis projection: original fallback
  proj.elements[3][2]*=0.01f;
  auto& depth=static_cast<VTexture&>(depthTex);
  auto& output=static_cast<VTexture&>(outputTex);
  if(!nativeIsDepthFormat(depth.format) || output.format!=VK_FORMAT_R8_UNORM || !output.isStorageImage)
    return false;
  if(!c.core) {
    VkPhysicalDeviceProperties properties{};
    vkGetPhysicalDeviceProperties(device.physicalDevice,&properties);
    if(properties.limits.maxComputeWorkGroupInvocations<256 ||
       properties.limits.maxComputeWorkGroupSize[0]<16 || properties.limits.maxComputeWorkGroupSize[1]<16) {
      Log::i("FIX46 CACAO unavailable: compute workgroup limits");c.failed=true;return false;
      }
    for(auto format: {VK_FORMAT_R16_SFLOAT,VK_FORMAT_R8G8B8A8_SNORM,VK_FORMAT_R8G8_UNORM,VK_FORMAT_R8_UNORM}) {
      VkFormatProperties p{};
      vkGetPhysicalDeviceFormatProperties(device.physicalDevice,format,&p);
      constexpr auto required=VK_FORMAT_FEATURE_SAMPLED_IMAGE_BIT|VK_FORMAT_FEATURE_STORAGE_IMAGE_BIT|
                              VK_FORMAT_FEATURE_SAMPLED_IMAGE_FILTER_LINEAR_BIT;
      if((p.optimalTilingFeatures&required)!=required) {
        Log::i("FIX46 CACAO unavailable: working texture format=",int(format));c.failed=true;return false;
        }
      }
    c.context=static_cast<FFX_CACAO_VkContext*>(std::calloc(1,FFX_CACAO_VkGetContextSize()));
    if(!c.context) {c.failed=true;return false;}
    FFX_CACAO_VkCreateInfo info{};
    info.device=device.device.impl;info.physicalDevice=device.physicalDevice;info.flags=0; // FP32 only
    const auto status=FFX_CACAO_VkInitContext(c.context,&info);
    if(status!=FFX_CACAO_STATUS_OK) {
      Log::i("FIX46 CACAO init failed status=",int(status),"; original fallback");c.failed=true;return false;
      }
    c.core=true;
    Log::i("FIX46 CACAO context: upstream FP32; private Vulkan; fenced command-buffer resources");
    }
  const auto depthView=depth.view(ComponentMapping(),uint32_t(-1),false,false);
  const auto outputView=output.view(ComponentMapping(),0,false,true);
  if(!c.screen || c.depth!=depthView || c.output!=outputView || c.width!=width || c.height!=height || c.downsampled!=half) {
    if(c.screen) FFX_CACAO_VkDestroyScreenSizeDependentResources(c.context);
    c.screen=false;
    FFX_CACAO_VkScreenSizeInfo info{};
    info.width=width;info.height=height;info.depthView=depthView;
    info.output=output.impl;info.outputView=outputView;
    info.normalsView=VK_NULL_HANDLE;info.useDownsampledSsao=half ? FFX_CACAO_TRUE : FFX_CACAO_FALSE;
    const auto status=FFX_CACAO_VkInitScreenSizeDependentResources(c.context,&info);
    if(status!=FFX_CACAO_STATUS_OK) {
      Log::i("FIX46 CACAO resources failed status=",int(status),"; original fallback");c.failed=true;return false;
      }
    c.screen=true;c.depth=depthView;c.output=outputView;c.width=width;c.height=height;c.downsampled=half;
    Log::i("FIX46 CACAO size: ",width,"x",height," downsampled=",int(half)," radius-metres=1 quality=HIGH");
    }
  auto settings=FFX_CACAO_DEFAULT_SETTINGS;
  settings.radius=1.f;settings.fadeOutFrom=500.f;settings.fadeOutTo=1000.f;
  settings.qualityLevel=FFX_CACAO_QUALITY_HIGH;
  settings.generateNormals=FFX_CACAO_TRUE;
  settings.temporalSupersamplingAngleOffset=0.f;
  settings.temporalSupersamplingRadiusOffset=0.f;
  FFX_CACAO_VkUpdateSettings(c.context,&settings);

  resState.setLayout(depth,ResourceLayout::Default,ResourceState::AllMips);
  resState.setLayout(output,ResourceLayout::Default,ResourceState::AllMips);
  resState.onUavUsage(depth.nonUniqId,output.nonUniqId,PipelineStage::S_Compute);
  resState.flush(*this);
  // Upstream discards/reinitializes its output. Prior readers/writers have been
  // synchronized above; the five depth descriptors use the engine's depth-read layout.
  const auto status=FFX_CACAO_VkDraw(c.context,impl,&proj,nullptr);
  if(status!=FFX_CACAO_STATUS_OK)
    throw std::runtime_error("FIX46 CACAO recording failed: "+std::to_string(int(status)));
  // CACAO finishes output in SHADER_READ_ONLY. Restore the storage image's
  // engine default GENERAL layout and expose writes to subsequent lighting.
  VkImageMemoryBarrier barrier{};
  barrier.sType=VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
  barrier.srcAccessMask=VK_ACCESS_SHADER_WRITE_BIT|VK_ACCESS_SHADER_READ_BIT;
  barrier.dstAccessMask=VK_ACCESS_SHADER_READ_BIT|VK_ACCESS_SHADER_WRITE_BIT;
  barrier.oldLayout=VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
  barrier.newLayout=VK_IMAGE_LAYOUT_GENERAL;
  barrier.srcQueueFamilyIndex=barrier.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED;
  barrier.image=output.impl;
  barrier.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};
  vkCmdPipelineBarrier(impl,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,
                       0,0,nullptr,0,nullptr,1,&barrier);
  resState.forceLayout(output,ResourceLayout::Default);
  pipelineLayout=VK_NULL_HANDLE;bindings.durty=true;pushData.durty=true;
  curCompPipeline=nullptr;curDrawPipeline=nullptr;state=Compute;
  return true;
#else
  (void)depthTex;(void)outputTex;(void)width;(void)height;(void)projection;(void)half;
  return false;
#endif
  }
