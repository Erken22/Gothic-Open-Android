#!/usr/bin/env python3
"""Exercise watchdog reporting with a slow call and a concurrently short call."""
import pathlib
import subprocess
import sys
import tempfile
repo = pathlib.Path(__file__).resolve().parent.parent
headers = pathlib.Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix='gothic-watchdog-') as tmp:
    p = pathlib.Path(tmp)
    inc = p/'include/android'
    inc.mkdir(parents=True)
    (inc/'native_window.h').write_text('#pragma once\ntypedef struct ANativeWindow ANativeWindow;\n')
    (inc/'log.h').write_text(r'''#pragma once
#include <cstdio>
#include <cstdarg>
#define ANDROID_LOG_INFO 4
#define ANDROID_LOG_WARN 5
#define ANDROID_LOG_ERROR 6
static inline int __android_log_print(int,const char*,const char* f,...) {
  va_list args;va_start(args,f);int n=vfprintf(stderr,f,args);va_end(args);
  fputc('\n',stderr);return n;
}
''')
    src = p/'vulkan_proxy.cpp'
    subprocess.run([sys.executable,str(repo/'overlay/gen_vulkan_proxy.py'),
                    str(headers/'registry/vk.xml'),str(src)],check=True)
    with src.open('a') as f:
        f.write(r'''
int main() {
  std::thread worker([] {
    WatchCall fast("TEST_fast",(void*)&nowMs);
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
  });
  {
    WatchCall slow("TEST_slow",(void*)&main,123,456);
    std::this_thread::sleep_for(std::chrono::milliseconds(4200));
  }
  worker.join();
  return 0;
}
''')
    exe=p/'test'
    subprocess.run(['g++','-std=c++20','-pthread','-I'+str(p/'include'),
                    '-I'+str(headers/'include'),str(src),'-ldl','-o',str(exe)],check=True)
    result=subprocess.run([str(exe)],capture_output=True,text=True,check=True,timeout=10)
    assert 'FIX22 Vulkan pending: TEST_slow' in result.stderr,result.stderr
    assert 'FIX22 Vulkan returned: TEST_slow' in result.stderr,result.stderr
    assert 'detail0=0x7b detail1=0x1c8' in result.stderr,result.stderr
    assert 'TEST_fast' not in result.stderr,result.stderr
    print('PASS: slow-call watchdog reports and clears; concurrent short calls stay silent.')
