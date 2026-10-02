"""Semantic skeletons and directional shallow-relief cross-sections."""
from copy import deepcopy

import numpy as np


def smoothmax(a,b,k=.016):
    blend=np.maximum(k-np.abs(a-b),0)/k
    return np.maximum(a,b)+blend*blend*k*.25


def spline(points,samples=12):
    points=np.asarray(points,float);points=np.vstack([points[0],points,points[-1]])
    result=[]
    for index in range(1,len(points)-2):
        a,b,c,d=points[index-1:index+3]
        for t in np.linspace(0,1,samples,endpoint=False):
            result.append(.5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t))
    return np.vstack([result,points[-1]])


def directional_field(x,y,unit):
    """Evaluate an editable semantic path with a kind-specific crown section."""
    path=spline(unit["points"]);path[:,0]=(path[:,0]-800)/160;path[:,1]=(800-path[:,1])/160
    delta=np.diff(path,axis=0);lengths=np.linalg.norm(delta,axis=1);arc=np.r_[0,np.cumsum(lengths)];total=arc[-1]
    closest=np.full(x.shape,np.inf);along=np.zeros_like(x);side=np.zeros_like(x)
    for index,(anchor,direction,length) in enumerate(zip(path[:-1],delta,lengths)):
        if length<1e-8:continue
        u=np.clip(((x-anchor[0])*direction[0]+(y-anchor[1])*direction[1])/length**2,0,1)
        dx=x-anchor[0]-u*direction[0];dy=y-anchor[1]-u*direction[1];distance=dx*dx+dy*dy;take=distance<closest
        closest=np.minimum(closest,distance);along[take]=(arc[index]+u[take]*length)/total
        side[take]=(dx[take]*(-direction[1])+dy[take]*direction[0])/length
    t=along;kind=unit["kind"];width=unit["width"];height=unit["height"]
    if kind in ("SCROLL_BODY","TAPERED_BRANCH"):
        local_width=width*(.88-.62*t+.20*np.sin(np.pi*t))
        if kind=="SCROLL_BODY":local_width=width*(.12+.98*np.sin(np.pi*t)**.6)*(1-.45*t**9)
        q=np.sqrt(closest)/np.maximum(local_width,.001);footprint=np.clip(1-q*q,0,1)
        result=height*(.7+.3*np.sin(np.pi*t))*(1-.65*t**10)*footprint**1.5
        if kind=="SCROLL_BODY":result*=.15+.85*np.sin(np.pi*t)**.4
    else:
        local_width=width*np.maximum(np.sin(np.pi*t),.0001)**.68
        q=np.copysign(np.sqrt(closest),side)/np.maximum(local_width,.001);footprint=np.clip(1-q*q,0,1)
        root=np.clip(t/.28,0,1);root=root*root*(3-2*root)
        if kind=="LEAF_BLADE":
            section=(.42*(1-np.minimum(np.abs(q),1))**1.2+.58*footprint**1.8)
            section*=1+unit.get("twist",.2)*q*np.sin(np.pi*t)
            tip=height*.35*np.exp(-((t-.86)/.12)**2)*footprint
            result=root*(height*(.45+.55*np.sin(np.pi*t))*section+tip)
        else:
            section=footprint**1.5*(.40+1.60*np.minimum(q*q,1))
            section*=1+.22*q*np.sin(np.pi*t);lip=unit.get("lip",.22)*np.exp(-((t-.76)/.19)**2)
            result=root*height*(.60+.25*t+lip)*section*np.sin(np.pi*t)**.65
        result+=unit.get("lift",0)*root*footprint**1.5
    return np.maximum(result,0),path


UNITS=[
 dict(id="S1",kind="SCROLL_BODY",points=[[801,80],[874,160],[927,191],[974,268],[918,339],[853,269],[915,280],[887,290]],width=.101,height=.104),
 dict(id="B1",kind="TAPERED_BRANCH",points=[[967,251],[973,222],[986,197],[981,168]],width=.061,height=.072),
 dict(id="B2",kind="TAPERED_BRANCH",points=[[876,189],[890,144],[925,109],[971,100]],width=.053,height=.062),
 dict(id="L1",kind="LEAF_BLADE",points=[[872,192],[838,183],[844,166],[857,148]],width=.146,height=.081,twist=.30,lift=.008),
 dict(id="L2",kind="LEAF_BLADE",points=[[927,115],[914,103],[897,93],[875,86]],width=.128,height=.071,twist=-.35,lift=.011),
 dict(id="L3",kind="LEAF_BLADE",points=[[979,214],[980,189],[969,174],[956,163],[945,143]],width=.157,height=.100,twist=.45,lift=.014),
 dict(id="L4",kind="LEAF_BLADE",points=[[975,218],[983,189],[1000,174],[1008,157],[1026,145]],width=.153,height=.095,twist=-.35,lift=.011),
 dict(id="P_outer_left",kind="PETAL_LAYER",points=[[981,173],[963,155],[950,140],[952,125],[963,115]],width=.212,height=.076,lift=.011,lip=.14),
 dict(id="P_outer_right",kind="PETAL_LAYER",points=[[987,173],[1000,161],[1006,143],[998,124],[984,116]],width=.218,height=.083,lift=.012,lip=.14),
 dict(id="P_inner",kind="PETAL_LAYER",points=[[980,177],[970,159],[968,142],[978,133],[992,139]],width=.121,height=.119,lift=.024,lip=.24),
 dict(id="P_heart",kind="PETAL_LAYER",points=[[981,174],[979,159],[987,152],[996,158]],width=.090,height=.122,lift=.030,lip=.24),
]

for unit in list(UNITS):
    if unit["id"] in ("S1","B2","L1","L2"):
        mirror=deepcopy(unit);mirror["id"]="left_"+unit["id"]
        mirror["points"]=[[1600-x,y] for x,y in unit["points"]];mirror["twist"]=-unit.get("twist",0)
        UNITS.append(mirror)
