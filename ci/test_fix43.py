#!/usr/bin/env python3
import math, random
# 32 original Hammersley directions, rotated with random pixel noise, compared
# to FIX43 quarter-circle LUT + quadrant and one pixel-wide rotation.
r=random.Random(43)
v=[(math.cos(i*math.pi/16),math.sin(i*math.pi/16)) for i in range(8)]
maxdiff=0.0
for it in range(2000):
    f0=(r.random()*math.pi*2)
    c,s=math.cos(f0),math.sin(f0)
    for i in range(32):
        x=i/32
        bits=int(f'{i:05b}'[::-1],2)
        angle=bits*2*math.pi/32+f0
        originalR=math.sqrt(1-math.sqrt(1-x)**2)
        original=(originalR*math.cos(angle),originalR*math.sin(angle),x)
        k=i>>2
        a=((k&1)<<2)|(k&2)|((k&4)>>2)
        bx,by=v[a]
        if i&2: bx,by=-by,bx
        if i&1: bx,by=-bx,-by
        radius=math.sqrt(x)
        x0,y0=bx*radius,by*radius
        fast=(x0*c-y0*s,x0*s+y0*c,x)
        err=max(abs(a-b) for a,b in zip(original,fast))
        maxdiff=max(maxdiff,err)
        if err>3e-12: raise SystemExit(f"disagreement i={i} error={err}")
print(f"FIX43 Hammersley rotation 64k directions: PASS maxdiff={maxdiff:.2e}")
