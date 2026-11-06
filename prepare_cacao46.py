#!/usr/bin/env python3
"""Pinned upstream CACAO, FP32 shaders, and narrow Vulkan integration edits."""
import pathlib, re, shutil, subprocess, sys
source=pathlib.Path(sys.argv[1]).resolve()
vendor=pathlib.Path(sys.argv[2]).resolve()
dxc=str(pathlib.Path(sys.argv[3]).resolve())
pin='0ddca95e6714727a252ead345591ca8f2598f261'
assert subprocess.check_output(['git','-C',str(vendor),'rev-parse','HEAD'],text=True).strip()==pin
dest=source/'lib/Tempest/Engine/thirdparty/cacao46'
dest.mkdir(parents=True,exist_ok=True)
for directory in ['inc','src']:
    shutil.copytree(vendor/'ffx-cacao'/directory,dest/directory,dirs_exist_ok=True)
bind=dest/'src/ffx_cacao_bindings.hlsl'
s=bind.read_text()
assert 'g_DepthIn.Load(int3(coord, 0), offset)' in s
bind.write_text(s.replace('.Load(int3(coord, 0), offset)', '.Load(int3(coord + offset, 0))'))
base=[dxc,'-Wno-conversion','-spirv','-T','cs_6_2','-fspv-target-env=vulkan1.1',
      '-fvk-s-shift','0','0','-fvk-b-shift','10','0','-fvk-t-shift','20','0','-fvk-u-shift','30','0']
(dest/'src/PrecompiledShadersSPIRV').mkdir(exist_ok=True)
n=0
for line in (dest/'src/build_shaders_spirv.bat').read_text().splitlines():
    if not line.startswith('%cauldron_dxc_32%'):continue
    args=line.split()[1:]
    # Also emit binary modules for spirv-val/capability inspection.
    h=args[args.index('-Fh')+1]
    subprocess.run(base+args+['-Fo',h+'.spv'],cwd=dest/'src',check=True)
    n+=1
assert n==33,n
impl=dest/'src/ffx_cacao_impl.cpp'
s=impl.read_text(errors='replace')
# Only FP32 modules exist. Both upstream lookup tables reference those modules;
# integration always passes flags=0 and never requests native FP16 features.
s=re.sub(r'^#include "PrecompiledShadersSPIRV/[^"\n]+_16.h"\n','',s,flags=re.M)
s=s.replace('SPIRV16','SPIRV32')
s=s.replace('#include "ffx_cacao_impl.h"', '#include "gapi/vulkan/vulkan_sdk.h"\n#include "ffx_cacao_impl.h"',1)
old='imageInfos[cur].imageView = info->depthView;\n\t\timageInfos[cur].imageLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;'
assert s.count(old)==5
s=s.replace(old,old.replace('VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL','VK_IMAGE_LAYOUT_DEPTH_STENCIL_READ_ONLY_OPTIMAL'))
impl.write_text(s)
licenseFile=next(p for p in vendor.iterdir() if p.name.lower().startswith('license'))
assets=source/'android/launcher/assets';assets.mkdir(exist_ok=True)
shutil.copyfile(licenseFile,assets/'CACAO_LICENSE.txt')
print(f'FIX46 pinned CACAO prepared; {n} real FP32 SPIR-V modules; depth descriptor layouts matched')
