#!/usr/bin/env python3
"""Complete upstream CACAO bridge, bounded whole-chain comparison and fallback."""
from pathlib import Path
import sys,re
root=Path(sys.argv[1]).resolve()
here=Path(__file__).resolve().parent
def swap(path,old,new,count=1):
    p=root/path;s=p.read_text()
    if s.count(old)!=count:raise SystemExit(f'FIX46 anchor mismatch {path}: {s.count(old)}: {old[:70]}')
    p.write_text(s.replace(old,new,1))

engine='lib/Tempest/Engine/'
method='bool renderCacao46(Texture& depth, Texture& output, uint32_t width, uint32_t height, const float* projection, bool half)'
swap(engine+'gapi/abstractgraphicsapi.h','        virtual void setGpuProfilingEnabled(bool enabled);',
     '        virtual void setGpuProfilingEnabled(bool enabled);\n        virtual '+method+' {return false;}')
args='bool renderCacao46(AbstractGraphicsApi::Texture& depth, AbstractGraphicsApi::Texture& output, uint32_t width, uint32_t height, const float* projection, bool half)'
swap(engine+'gapi/vulkan/vcommandbuffer.h','    void setGpuProfilingEnabled(bool enabled) override;',
     '    void setGpuProfilingEnabled(bool enabled) override;\n    '+args+' override;')
swap(engine+'gapi/vulkan/vcommandbuffer.h','#include "vulkan_sdk.h"', '#include "vulkan_sdk.h"\n#include <memory>')
swap(engine+'gapi/vulkan/vcommandbuffer.h','    VDevice&                                device;',
     '''#if defined(TEMPEST_CACAO46)
    struct Cacao46;
    std::unique_ptr<Cacao46> cacao46;
#endif
    VDevice&                                device;''')
(root/(engine+'gapi/vulkan/vcacao46.inc')).write_text((here/'vcacao46.inc').read_text())
swap(engine+'gapi/vulkan/vcommandbuffer.cpp','using namespace Tempest::Detail;',
     'using namespace Tempest::Detail;\n#include "vcacao46.inc"')
swap(engine+'gapi/vulkan/vdevice.h','    VkPhysicalDevice        physicalDevice     = nullptr;',
     '    bool                    cacao46Enabled     = false;\n    VkPhysicalDevice        physicalDevice     = nullptr;')
swap(engine+'gapi/vulkan/vdevice.cpp',
     '  VkPhysicalDeviceFeatures deviceFeatures = {};',
     '''  VkPhysicalDeviceFeatures deviceFeatures = {};
#if defined(TEMPEST_CACAO46)
  cacao46Enabled=supportedFeatures.shaderStorageImageExtendedFormats && supportedFeatures.shaderImageGatherExtended;
  if(cacao46Enabled) {
    deviceFeatures.shaderStorageImageExtendedFormats=VK_TRUE;
    deviceFeatures.shaderImageGatherExtended=VK_TRUE;
    }
#endif''',count=2)
swap(engine+'graphics/encoder.h','    void setDebugMarker(std::string_view tag);',
     '''    void setDebugMarker(std::string_view tag);
    bool renderCacao46(const ZBuffer& depth, const StorageImage& output, const float* projection, bool half);''')
swap(engine+'graphics/encoder.cpp','void Encoder<Tempest::CommandBuffer>::setDebugMarker(std::string_view tag) {',
     '''bool Encoder<CommandBuffer>::renderCacao46(const ZBuffer& depth,const StorageImage& output,const float* projection,bool half) {
  setFramebuffer({});
  if(depth.isEmpty() || output.isEmpty() || depth.size()!=output.size()) return false;
  const bool used=impl->renderCacao46(*depth.tImpl.impl.handler,*output.tImpl.impl.handler,
                                    uint32_t(depth.w()),uint32_t(depth.h()),projection,half);
  // External pipeline/descriptor bindings invalidate both encoder and backend caches.
  if(used) {state.curCompute=nullptr;state.curPipeline=nullptr;state.stage=None;}
  return used;
  }

void Encoder<Tempest::CommandBuffer>::setDebugMarker(std::string_view tag) {''')
cmake=root/(engine+'CMakeLists.txt')
cmake.write_text(cmake.read_text()+'''
# FIX46 official CACAO Vulkan backend, built into the same private Vulkan namespace.
if(ANDROID)
  target_sources(${PROJECT_NAME} PRIVATE
    thirdparty/cacao46/src/ffx_cacao.cpp
    thirdparty/cacao46/src/ffx_cacao_impl.cpp)
  target_include_directories(${PROJECT_NAME} PRIVATE thirdparty/cacao46/inc)
  target_compile_definitions(${PROJECT_NAME} PRIVATE TEMPEST_CACAO46 FFX_CACAO_ENABLE_VULKAN)
endif()
''')
swap('android/CMakeLists.txt','    JAVA_DIRS launcher/java app/src/main/java',
     '    JAVA_DIRS launcher/java app/src/main/java\n    ASSET_DIRS launcher/assets')
swap('common/graphics/renderer.h','      int            aoMethod39         = 0;',
     '      int            aoMethod39         = 0;\n      int            aoMethod46         = 0;')
swap('common/graphics/renderer.cpp',
     '  settings.aoMethod39 = (Gothic::settingsGetI("ENGINE","aoMethod39")==1) ? 1 : 0;',
     '  settings.aoMethod39 = 0; // Retired slower FIX39 SAO prototype.\n  settings.aoMethod46 = std::clamp(Gothic::settingsGetI("ENGINE","aoMethod46"),0,2);')
swap('common/gothic.cpp','  defaults->set("ENGINE",       "aoMethod39", 0); // FIX40: previous SAO loses on phone, prefer original.',
     '  defaults->set("ENGINE",       "aoMethod39", 0); // Retired.\n  defaults->set("ENGINE",       "aoMethod46", 2); // Bounded comparison; returns original pending visual review.')
swap('common/ui/gamemenu.cpp',
     '    {"ANDROID_AO39","AO method","Original|SAO test","ENGINE","aoMethod39"},',
     '    {"ANDROID_AO46","AO method","Original|CACAO test|Compare","ENGINE","aoMethod46"},')
# Original SSAO integration remains available; native backend accepts only symmetric perspective.
swap('common/graphics/renderer.cpp',
     '  bool useSao39=false;',
     '''  bool compare46=false;
#if defined(__ANDROID__)
  static bool unavailable46=false;
  const bool eligible46=!unavailable46 && !settings.pathTraceEnabled && AndroidSaoCompare39::supported();
  AndroidCacaoCompare46::configure(eligible46);
  compare46=eligible46 && settings.aoMethod46==2;
  const bool candidate46=eligible46 && (settings.aoMethod46==1 || (compare46 && AndroidCacaoCompare46::useFused()));
  cmd.setDebugMarker(compare46 ? (candidate46 ? "AO46 CACAO" : "AO46 original") : "CACAO46 manual");
  if(candidate46) {
    float projection46[16];
    for(int c=0;c<4;++c) for(int r=0;r<4;++r) projection46[c*4+r]=proj.at(c,r);
    if(cmd.renderCacao46(zbuffer,ssao.ssaoBlur,projection46,halfResolution)) return;
    unavailable46=true;
    AndroidCacaoCompare46::configure(false);
    compare46=false;
    static bool warned46=false;
    if(!warned46) {Log::i("FIX46 CACAO unsupported/initialization failure; original AO fallback");warned46=true;}
    }
#endif
  bool useSao39=false;''')
# Preserve one marker over original producer + resolve during comparison.
swap('common/graphics/renderer.cpp',
     '  cmd.setDebugMarker(compare39 ? (useSao39 ? "AO compare SAO" : "AO compare original") : (useSao39 ? "SAO manual half" : "SSAO"));',
     '  if(!compare46) cmd.setDebugMarker("SSAO");')
swap('common/graphics/renderer.cpp','  cmd.setDebugMarker(halfResolution ? "SSAO upsample" : "SSAO blur");',
     '  if(!compare46) cmd.setDebugMarker(halfResolution ? "SSAO upsample" : "SSAO blur");')
# Reuse the established bounded ABBA controller with independent state and full-chain labels.
p=root/'common/utils/androidframeprofile.h';s=p.read_text()
controller=s[s.index('struct AndroidSaoCompare39 {'):s.index('template<size_t Slots>')]
controller=controller.replace('AndroidSaoCompare39','AndroidCacaoCompare46').replace('FIX39','FIX46').replace('SAO','CACAO')
controller=controller.replace('AO compare original','AO46 original').replace('AO compare CACAO','AO46 CACAO')
s=s.replace('template<size_t Slots>',controller+'template<size_t Slots>',1)
s=s.replace('if(samples>=24){AndroidSaoCompare39::finish();return false;}',
            'if(samples>=24){AndroidSaoCompare39::finish();AndroidCacaoCompare46::finish();return false;}')
s=s.replace('    AndroidSaoCompare39::observe(timings);','    AndroidSaoCompare39::observe(timings);\n    AndroidCacaoCompare46::observe(timings);')
p.write_text(s)
print('FIX46 complete CACAO bridge/settings/whole-chain ABBA controller applied')
