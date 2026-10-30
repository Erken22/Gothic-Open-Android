#!/usr/bin/env python3
"""FIX40 conservative-outside mathematical proof against original predicate."""
import math
import random
import sys
from pathlib import Path
r=random.Random(40067)
root=Path(sys.argv[1]) if len(sys.argv)>1 else None
if root:
    text=(root/"shader/sky/fog.frag").read_text()
    assert text.count("FIX40_FOG_TRIVIAL_OUTSIDE") == 1
    assert "0xFFFFFFFFu" in text
    assert "const vec3  ray      = pos1.xyz - pos0.xyz;" in text
    assert "for(uint i=0; i<steps; ++i)" in text

def out(p):
    x,y,w=p
    return abs(x)>=w or abs(y)>=w

def candidate(a,b):
    # GLSL shLast40 = b+(b-a)/64, strictly covers the maximum sample t.
    tail=tuple(y+(y-x)/64.0 for x,y in zip(a,b))
    e=max(abs(a[2]),abs(tail[2]),1.0)*0.001
    for sign,component in ((1,0),(-1,0),(1,1),(-1,1)):
        if (sign*a[component]>a[2]+e and
            sign*tail[component]>tail[2]+e):
            return True
    return False

hits=0
for case in range(150000):
    # Mix small/large offsets, negative homogeneous w, and near boundaries.
    a=tuple(r.uniform(-1e4,1e4) for _ in range(3))
    b=tuple(r.uniform(-1e4,1e4) for _ in range(3))
    if case%3==0:
        w=r.uniform(-5,5)
        a=(r.uniform(-9,9),r.uniform(-9,9),w)
        b=(r.uniform(-9,9),r.uniform(-9,9),r.uniform(-5,5))
    if case%9==0:
        eps=r.uniform(-0.003,0.003)
        a=(a[2]+eps,a[1],a[2])
    if not candidate(a,b):
        continue
    hits+=1
    for i in range(32):
        # exact original i range; actual gradient noise fract is in [0,1)
        for noise in (0.0, 0.5, math.nextafter(1.0,0.0)):
            t=(i+0.5+noise)/32.0
            pt=tuple(x+(y-x)*t for x,y in zip(a,b))
            assert out(pt), (case,i,noise,a,b,pt)
assert hits>1000, hits
print("FIX40 shadow clip proof: PASS; 150000 randomized rays,",
      hits,"candidate skips, 96 original predicate checks each")
