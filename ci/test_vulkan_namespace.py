#!/usr/bin/env python3
"""Host-side regression for FIX19's system Vulkan SONAME/symbol collision.
Usage: python3 ci/test_vulkan_namespace.py /path/to/Vulkan-Headers
This validates ELF loading and binding, not Android driver rendering.
"""
import ctypes
import pathlib
import subprocess
import sys
import tempfile

headers = pathlib.Path(sys.argv[1]).resolve()
repo = pathlib.Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory(prefix="opengothic-vulkan-test-") as tmp:
    p = pathlib.Path(tmp)
    def write(name, body):
        f = p / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(body)
    def run(*args):
        subprocess.run(args, check=True)
    write("include/android/log.h", "#pragma once\n#define ANDROID_LOG_INFO 4\n#define ANDROID_LOG_WARN 5\n#define ANDROID_LOG_ERROR 6\nstatic inline int __android_log_print(int,const char*,const char*,...) { return 0; }\n")
    write("include/android/native_window.h", "#pragma once\ntypedef struct ANativeWindow ANativeWindow;\n")
    write("engine.cpp", '#include "vulkan_redirect.h"\n#include <vulkan/vulkan.h>\n#include <cstdint>\nextern "C" int opengothic_vulkan_is_turnip();\nextern "C" int probe(){ return opengothic_vulkan_is_turnip(); }\nextern "C" uintptr_t core_address(){ return reinterpret_cast<uintptr_t>(&vkCreateInstance); }\n')
    write("poison.cpp", 'extern "C" int vkCreateInstance(){ return -99; }\n')
    write("oldproxy.cpp", 'extern "C" int opengothic_vulkan_is_turnip(){ return 0; }\n')
    write("oldengine.cpp", 'extern "C" int opengothic_vulkan_is_turnip();\nextern "C" int probe_old(){ return opengothic_vulkan_is_turnip(); }\n')
    run(sys.executable, str(repo / "overlay/gen_vulkan_proxy.py"), str(headers / "registry/vk.xml"), str(p / "vulkan_proxy.cpp"))
    run("g++", "-std=c++20", "-shared", "-fPIC", "-fvisibility=hidden", "-I"+str(p/"include"), "-I"+str(headers/"include"), str(p/"vulkan_proxy.cpp"), "-ldl", "-Wl,-soname,libopengothic_vulkan.so", "-o", str(p/"libopengothic_vulkan.so"))
    run("g++", "-shared", "-fPIC", "-I"+str(p), "-I"+str(headers/"include"), str(p/"engine.cpp"), "-L"+str(p), "-l:libopengothic_vulkan.so", "-Wl,-rpath,$ORIGIN", "-o", str(p/"libengine.so"))
    run("g++", "-shared", "-fPIC", str(p/"poison.cpp"), "-Wl,-soname,libvulkan.so", "-o", str(p/"poison.so"))
    run("g++", "-shared", "-fPIC", str(p/"oldproxy.cpp"), "-Wl,-soname,libvulkan.so", "-o", str(p/"libvulkan.so"))
    run("g++", "-shared", "-fPIC", str(p/"oldengine.cpp"), "-L"+str(p), "-l:libvulkan.so", "-Wl,-rpath,$ORIGIN", "-o", str(p/"liboldengine.so"))
    poison = ctypes.CDLL(str(p/"poison.so"), mode=ctypes.RTLD_GLOBAL)
    try:
        ctypes.CDLL(str(p/"liboldengine.so"))
    except OSError as error:
        assert "opengothic_vulkan_is_turnip" in str(error), str(error)
    else:
        raise AssertionError("Expected original SONAME collision was not reproduced")
    engine = ctypes.CDLL(str(p/"libengine.so"))
    engine.core_address.restype = ctypes.c_size_t
    assert engine.probe() == 0
    assert engine.core_address() != ctypes.cast(poison.vkCreateInstance, ctypes.c_void_p).value
    exports = subprocess.check_output(["nm", "-D", "--defined-only", str(p/"libopengothic_vulkan.so")], text=True)
    assert " opengothic_vulkan_is_turnip" in exports
    assert " opengothic_vkCreateInstance" in exports
    assert not any(line.split()[-1].startswith("vk") for line in exports.splitlines())
    print("PASS: original missing-symbol failure reproduced; private proxy loads and binds correctly with system Vulkan preloaded.")
