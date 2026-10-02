"""Directional folded-petal surface primitive."""
import numpy as np


def petal(x,y,cx,cy,rx,ry,start,end,height,width):
    """Open folded sheet with a shallow back and narrow rolled shoulder."""
    dx=(x-cx)/rx;dy=(y-cy)/ry;radius=np.hypot(dx,dy)
    angle=np.mod(np.arctan2(dy,dx)-start,2*np.pi);t=np.clip(angle/(end-start),0,1)
    endfade=np.clip(np.minimum(t,1-t)/.15,0,1);endfade=endfade*endfade*(3-2*endfade)
    q=(radius-(1+.075*np.sin(2*angle+.5)))/width
    outer=np.clip(1-q/1.8,0,1);inner=np.clip(1+q/.9,0,1)
    shape=np.where(q>=0,outer*outer*(3-2*outer),inner*inner*(3-2*inner))
    result=height*shape*endfade*(.85+.15*np.sin(np.pi*t))
    return np.where(angle<=end-start,result,0)
