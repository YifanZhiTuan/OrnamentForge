"""Semantic relief primitives in analytic vessel coordinates."""
import numpy as np

from .relief import spline


def ribbon(x,y,points,width,height,kind="branch"):
    """Directional crown/leaf section with bounded support and embedded roots."""
    points=np.asarray(spline(points,samples=10));pad=width*1.6
    mask=(x>points[:,0].min()-pad)&(x<points[:,0].max()+pad)&(y>points[:,1].min()-pad)&(y<points[:,1].max()+pad)
    out=np.zeros_like(x)
    if not np.any(mask):return out
    xx,yy=x[mask],y[mask];distance=np.full(xx.shape,1e6);position=np.zeros_like(xx);side=np.zeros_like(xx)
    lengths=np.linalg.norm(np.diff(points,axis=0),axis=1);cumulative=np.r_[0,np.cumsum(lengths)]
    for index,(a,b) in enumerate(zip(points[:-1],points[1:])):
        dx,dy=b-a;length_squared=max(dx*dx+dy*dy,1e-10)
        t=np.clip(((xx-a[0])*dx+(yy-a[1])*dy)/length_squared,0,1)
        ex=xx-a[0]-dx*t;ey=yy-a[1]-dy*t;candidate=ex*ex+ey*ey;winner=candidate<distance
        distance=np.where(winner,candidate,distance)
        position=np.where(winner,(cumulative[index]+t*lengths[index])/max(cumulative[-1],1e-9),position)
        side=np.where(winner,(dx*ey-dy*ex)/np.sqrt(length_squared),side)
    if kind in ("leaf","feather"):
        local_width=width*(.05+.95*np.sin(np.pi*position)**.72);root=np.clip(position/.18,0,1);tip=np.clip((1-position)/.1,0,1)
    else:
        local_width=width*(.8+.22*np.sin(np.pi*position))*(1-.7*position**4);root=np.clip(position/.08,0,1);tip=np.clip((1-position)/.08,0,1)
    support=np.clip(1-np.sqrt(distance)/np.maximum(local_width,.001),0,1)
    section=support*support*(3-2*support)
    if kind=="leaf":section=(.55*section+.45*support**.8)*(1+.20*side/np.maximum(local_width,.001)*np.sin(np.pi*position))
    out[mask]=height*section*root*tip
    return out


def units(direction,detail,repaired=False):
    """Return semantic phoenix paths rather than one opaque decorative mesh."""
    result=[]
    def add(name,kind,points,width,height,role):result.append({"id":name,"kind":kind,"points":points,"width":width,"height":height,"role":role})
    neck=[[-.7,5.72],[-.78,5.34],[-.42,5.02],[.15,4.58],[.4,4.15]] if direction=="A" else [[-.62,5.82],[-.78,5.56],[-.60,5.18],[-.12,4.91],[.36,4.45]]
    tails=[[[.36,4.5],[.62,4.05],[-.05,3.53],[-.85,3.08],[-.9,2.4],[-.2,1.98],[.7,2.06],[1.2,2.5]],
           [[.45,4.45],[.86,3.95],[.3,3.4],[-.5,2.95],[-.42,2.5],[.32,2.35],[.92,2.68]],
           [[.38,4.4],[.37,3.96],[-.45,3.5],[-1.18,2.97],[-1.14,2.22],[-.4,1.63],[.47,1.55]]]
    add("neck","branch",neck,.16,.10,"hero");add("body_spine","feather",[[.03,4.95],[.35,4.65],[.46,4.18]],.36,.135,"hero")
    add("head_anchor","leaf",[[-.80,5.79],[-.60,5.9],[-.41,5.81]],.155,.112,"hero")
    add("wing_mass","leaf",[[.12,4.68],[.49,5.02],[.77,5.12]],.25,.092,"hero")
    for index,path in enumerate(tails):add(f"primary_tail_{index}","branch",path,.115-index*.016,.10-index*.012,"hero")
    branch=[[-1.6,4.95],[-1.4,4.5],[-1.48,3.96],[-1.35,3.47],[-.96,3.07],[-.3,2.9],[.47,3.14],[1.28,3.17],[1.75,3.5]]
    add("flower_branch","branch",branch,.060,.047,"secondary")
    leaves=[[[-1.4,4.52],[-1.78,4.65],[-1.82,5.06]],[[-1.45,3.90],[-1.83,3.80],[-1.98,3.38]],[[-1.26,3.38],[-.90,3.62],[-.92,3.96]],[[.48,3.12],[.77,3.50],[.58,3.79]]]
    for index,path in enumerate(leaves):add(f"leaf_{index}","leaf",path,.18,.075,"secondary")
    return result
