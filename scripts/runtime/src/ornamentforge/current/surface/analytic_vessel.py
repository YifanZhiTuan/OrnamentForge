"""NumPy-only analytic vessel host, also usable inside Blender Python."""
import numpy as np

def profile(z):
    xp=np.array([0,.12,.28,.65,1.3,2.2,3.2,4.2,5.1,5.75,6.25,6.7,7.3,7.7,8.0])
    rp=np.array([.85,.93,.93,.88,1.15,1.62,1.91,1.96,1.78,1.39,.88,.65,.64,.71,.88])
    slopes=np.gradient(rp,xp); slopes[[0,-1]]=0
    i=np.clip(np.searchsorted(xp,z)-1,0,len(xp)-2); d=xp[i+1]-xp[i]; t=(z-xp[i])/d
    return (2*t**3-3*t**2+1)*rp[i]+(t**3-2*t**2+t)*d*slopes[i]+(-2*t**3+3*t**2)*rp[i+1]+(t**3-t**2)*d*slopes[i+1]

def mapping(theta,z,h):
    r=profile(z); lo=np.maximum(z-.002,0);hi=np.minimum(z+.002,8)
    dr=(profile(hi)-profile(lo))/(hi-lo);norm=np.sqrt(1+dr*dr)
    p=np.stack([r*np.sin(theta),-r*np.cos(theta),z],-1)
    n=np.stack([np.sin(theta)/norm,-np.cos(theta)/norm,-dr/norm],-1)
    return p+h[...,None]*n,p,n
