#!/usr/bin/env python3
"""Guard the AO-fusion boundary; shader compilation and SPIR-V validation run separately."""
import hashlib,pathlib,sys
root=pathlib.Path(sys.argv[1])
def read(p):return (root/p).read_text()
# The producer, common edge-aware filter and original fallback must remain exact.
for path,digest in {
 'shader/ssao/half_resolution.glsl':'29570325da3dc936d3bcf97f31a13cb86bea2f0c87cfbdd175c9b12248b97fd1',
 'shader/ssao/ssao.comp':'a3fb0c36ceed39f0f0d8747418d2715e57d8f594b0d997217db28bcf80a23317',
 'shader/ssao/ssao_upsample.comp':'4314b6d21ef95a8201b78cd0922e85758ff7954bf4f825d4307cfd691374af92',
 'shader/lighting/ambient_light.frag':'21ba8442ee8001a1d9563c751164326a26be91d18edafcb768e946d5e348f8bb',
}.items():assert hashlib.sha256((root/path).read_bytes()).hexdigest()==digest,path
original=read('shader/lighting/ambient_light.frag')
fused=read('shader/lighting/ambient_resolve37.frag')
a=fused.index('float textureSsao() {');b=fused.index('\n#else',a)
body=fused[a:b]
assert 'texelFetch(depthBuf37,pixel,0).r' in body
assert 'z>=1.0 ? 1.0 : ssaoResolveHalf(ssao,pixel,linearDepth(z,scene.clipInfo))' in body
assert 'unpackUnorm4x8(packUnorm4x8(vec4(ao,0.0,0.0,0.0))).r' in body
normalized=fused[:a]+'float textureSsao() { return textureLod(ssao, uv, 0).r; }'+fused[b:]
normalized=normalized.replace('\n#include "ssao/half_resolution.glsl"','').replace('layout(binding = 5) uniform sampler2D depthBuf37;\n\n','')
assert normalized==original,'Ambient color, normals, exposure or outputs changed outside AO accessor'
r=read('common/graphics/renderer.cpp')
a=r.index('void Renderer::prepareSSAO(');b=r.index('void Renderer::prepareFog(',a);prepare=r[a:b]
assert prepare.index('aoResolveEligible37=false;aoResolveFused37=false;')<prepare.index('if(!settings.zCloudShadowScale)')
assert 'AndroidAoResolve37::supported() && halfResolution &&\n      settings.giMethod==GiMethod::None && !settings.pathTraceEnabled' in prepare
assert prepare.index('cmd.dispatchThreads(ssao.ssaoBuf.size());')<prepare.index('if(aoResolveFused37)return;')<prepare.index('cmd.dispatchThreads(ssao.ssaoBlur.size());')
a=r.index('void Renderer::drawAmbient(');b=r.index('Tempest::Attachment Renderer::screenshoot',a);ambient=r[a:b]
assert 'AndroidAoResolve37::useFused()' not in ambient,'Must use one per-frame snapshot'
assert 'cmd.setBinding(4, ssao.ssaoBuf, Sampler::nearest(ClampMode::ClampToEdge));' in ambient
assert 'cmd.setBinding(5, zbuffer, Sampler::nearest(ClampMode::ClampToEdge));' in ambient
assert 'cmd.setPipeline(shaders.ambientResolve37);' in ambient
for p in ['ambientLightSurf','probeAmbient','ambientLightSsao','ambientLight']:assert 'cmd.setPipeline(shaders.'+p+');' in ambient
sh=read('common/graphics/shaders.cpp')
assert 'ambientResolve37=ambientLightShader("ambient_resolve37");' in sh
assert 'AndroidAoResolve37::configure(isTurnipAdreno650() && gpu.hasStorageFormat(TextureFormat::RG32F));' in sh
assert 'AndroidIndexedShadow36' not in r+sh
print('PASS: unchanged SSAO/filter/fallback and ambient lighting; fused depth/R8 contract; half-AO GI-None gate; one frame snapshot; other paths preserved.')
