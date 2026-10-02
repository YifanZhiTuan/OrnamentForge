"""Exact cubic subdivision/concatenation plus bounded sampled diagnostics."""
from copy import deepcopy
import numpy as np


def controls(payload):
    return [np.array([a['co'][:2],a['right'][:2],b['left'][:2],b['co'][:2]],float)
            for a,b in zip(payload['points'],payload['points'][1:])]


def split(c,t):
    a=(1-t)*c[:-1]+t*c[1:];b=(1-t)*a[:-1]+t*a[1:];p=(1-t)*b[0]+t*b[1]
    return np.array([c[0],a[0],b[0],p]),np.array([p,b[1],a[2],c[3]])


def sample(segments,step):
    result=[]
    for c in segments:
        length=float(np.linalg.norm(np.diff(c,axis=0),axis=1).sum())
        t=np.linspace(0,1,max(2,int(np.ceil(length/step))+1));s=1-t
        p=np.array([s**3,3*s*s*t,3*s*t*t,t**3]).T@c
        result.extend(p if not result else p[1:])
    return np.asarray(result)


def length(segments,unit):
    points=sample(segments,unit*.5)
    return float(np.linalg.norm(np.diff(points,axis=0),axis=1).sum())


def reverse(segments):return [c[::-1].copy() for c in segments[::-1]]


def trim_start(segments,distance,unit):
    """Exact de Casteljau fragments; cut parameter chosen by sampled arc length."""
    if distance<=0:return [],[c.copy() for c in segments]
    removed=[]
    for i,c in enumerate(segments):
        n=max(10,int(np.ceil(np.linalg.norm(np.diff(c,axis=0),axis=1).sum()/unit*4)))
        t=np.linspace(0,1,n+1);s=1-t;p=np.array([s**3,3*s*s*t,3*s*t*t,t**3]).T@c
        arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
        if distance>=arc[-1]:
            removed.append(c.copy());distance-=arc[-1];continue
        at=float(np.interp(distance,arc,t));a,b=split(c,at)
        return removed+[a],[b]+[v.copy() for v in segments[i+1:]]
    return removed,[]


def payload(segments):
    def xyz(p):return [float(p[0]),float(p[1]),0.]
    points=[]
    for i,c in enumerate(segments):
        points.append(dict(co=xyz(c[0]),left=xyz(segments[i-1][2] if i else c[0]),right=xyz(c[1]),
            left_type='FREE',right_type='FREE',radius=1.,tilt=0.))
    c=segments[-1];points.append(dict(co=xyz(c[3]),left=xyz(c[2]),right=xyz(c[3]),
        left_type='FREE',right_type='FREE',radius=1.,tilt=0.))
    return dict(curve_version='1.0',representation='bezier_curve',dimensions='3D',
        resolution_u=24,twist_mode='Z_UP',cyclic=False,points=points)


def endpoint_direction(segments,side,unit):
    p=sample(reverse(segments) if side else segments,unit*.5)
    arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
    i=min(len(p)-1,max(1,int(np.searchsorted(arc,min(3*unit,arc[-1])))))
    v=p[i]-p[0];v/=max(np.linalg.norm(v),1e-12)
    j=min(len(p)-1,max(i+1,int(np.searchsorted(arc,min(6*unit,arc[-1])))))
    v2=p[j]-p[i]
    bend=0. if np.linalg.norm(v2)<1e-12 else float(np.arccos(np.clip(v@(v2/np.linalg.norm(v2)),-1,1)))
    return v,bend
