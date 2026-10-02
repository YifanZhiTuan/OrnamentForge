"""Deterministic botanical sphere art direction and pre-geometry aperture exclusion."""
import math
import random
from ..canonical_curve import content_hash

AXES=[[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]]

def add(a,b): return [a[i]+b[i] for i in range(3)]
def mul(a,s): return [v*s for v in a]
def dot(a,b): return sum(x*y for x,y in zip(a,b))
def cross(a,b): return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def unit(a): return mul(a,1/math.sqrt(dot(a,a)))
def frame(n):
    u=unit(cross([0,0,1] if abs(n[2])<.9 else [0,1,0],n))
    return u,cross(n,u)
def mapped(n,u,v,x,y,r): return mul(unit(add(n,add(mul(u,x),mul(v,y)))),r)

def sample(payload,count=8):
    pts=payload["points"]; out=[]
    for i in range(len(pts) if payload["cyclic"] else len(pts)-1):
        a,b=pts[i],pts[(i+1)%len(pts)]
        for j in range(count):
            t=j/count; w=(1-t)**3,3*(1-t)**2*t,3*(1-t)*t*t,t**3
            out.append([sum(wt*p[k] for wt,p in zip(w,[a["co"],a["right"],b["left"],b["co"]])) for k in range(3)])
    if not payload["cyclic"]: out.append(pts[-1]["co"])
    return out


def build(spec,definitions,refinement=2):
    data=spec.to_dict(); r=data["base_surface"]["dimensions"][0]/2
    opening=data["openings"][0]; hole=opening["radius_ratio"]
    if data["base_surface"]["type"]!="sphere" or opening["count"]!=6:
        raise ValueError("Showcase hero uses a spherical shell with six axial oculi")
    if not .18<=hole<=.29: raise ValueError("Showcase opening radius ratio must be 0.18–0.29")
    if data["base_surface"].get("shell_thickness",.06*r)<data["geometry"]["minimum_wall_thickness"]:
        raise ValueError("Shell thickness is below the declared minimum wall thickness")
    rng=random.Random(spec.seed)
    curves=[]; surfaces=[]; beads=[]; actions=[]
    cache={role:sample(payload,5) for role,payload in definitions.items()}
    min_width=data["geometry"]["minimum_feature_width"]
    clearance=hole+max(.065,opening.get("clearance",.025)+.04)
    border_scale=opening.get("border",{}).get("width",.023)/.023
    def safe(points,width):
        limit=math.sqrt(1-(clearance+width/r)**2)
        return all(max(abs(x) for x in unit(p))<limit for p in points)
    def path(name,points,width,category,material="gold",closed=False,role=None):
        width=max(width,min_width)
        if not safe(points,width):
            actions.append({"object":name,"repair":"trim_or_skip_exclusion","category":category});return False
        curves.append({"name":name,"points":points,"width":width,"category":category,"material":material,"closed":closed,"role":role})
        return True
    def motif(role,n,u,v,x,y,scale,angle,name,category,width=.010,solid=False,mirror=1):
        co,si=math.cos(angle),math.sin(angle)
        coords=[]
        for a,b,_ in cache[role]:
            b*=mirror
            xx=x+scale*(a*co-b*si); yy=y+scale*(a*si+b*co)
            coords.append(mapped(n,u,v,xx,yy,r+width*.40))
        if not safe(coords,width):
            actions.append({"object":name,"repair":"delete_exclusion","category":category});return
        if solid:
            surfaces.append({"name":name,"boundary":coords,"category":category,"role":role,
                             "height":.018*r if role=="Flower_A" else .013*r,"material":"ivory"})
        path(name+"_edge",coords,width,category,"gold" if category!="filler" else "ivory",definitions[role]["cyclic"],role)
        if solid and role in ("Leaf_A","Leaf_B"):
            vein=[mapped(n,u,v,x+scale*t*co,y+scale*t*si,r+.013*r*math.sin(math.pi*t)+.004*r) for t in [j/12 for j in range(13)]]
            path(name+"_vein",vein,.006*r,category,"gold",False,role)
    # Six pierced botanical panels with directional branching, not random scatter.
    for face,n in enumerate(AXES):
        u,v=frame(n)
        for k in range(8):
            angle=2*math.pi*k/8+.035*math.sin(face+k+spec.seed)
            # Shape deformation uses stored main vine's lateral profile.
            vine=cache["Vine_Main"]
            ymin=min(p[1] for p in vine); ymax=max(p[1] for p in vine)
            coords=[]
            for j in range(65):
                t=j/64; rho=(.38 if refinement>=2 else .34)+.53*t
                lateral=vine[min(len(vine)-1,round(t*(len(vine)-1)))][1]/max(.1,ymax-ymin)
                theta=angle+.12*lateral
                coords.append(mapped(n,u,v,rho*math.cos(theta),rho*math.sin(theta),r+.007*r))
            if not path(f"Main_{face}_{k}",coords,.021*r,"primary","gold",False,"Vine_Main"):
                # Deterministic local reroute: push cap-near points outward in their face chart.
                rerouted=[]
                for j in range(65):
                    t=j/64;rho=.40+.51*t;theta=angle+.04*math.sin(t*math.pi*2)
                    rerouted.append(mapped(n,u,v,rho*math.cos(theta),rho*math.sin(theta),r+.007*r))
                path(f"Main_{face}_{k}",rerouted,.021*r,"primary","gold",False,"Vine_Main")
                actions.append({"object":f"Main_{face}_{k}","repair":"replan_main_vine_outside_cap","category":"primary"})
            for j in range(5 if refinement>0 else 4):
                t=.12+j*.165;rho=.34+.57*t;theta=angle+.025*math.sin(t*math.pi*3)
                x,y=rho*math.cos(theta),rho*math.sin(theta)
                sign=1 if j%2==0 else -1
                leafscale=(.14+.018*rng.random())*(.93 if j==0 else 1)
                motif("Leaf_A" if j%2 else "Leaf_B",n,u,v,x,y,leafscale,theta+sign*1.08,
                      f"Leaf_{face}_{k}_{j}","secondary",.008*r,True)
            # Two opposed curled branches per stem, sized by hierarchy.
            for side in (-1,1):
                rho=.57; theta=angle+side*.13
                x,y=rho*math.cos(theta),rho*math.sin(theta)
                motif("Scroll_A",n,u,v,x,y,.24,angle+side*.8,f"Scroll_{face}_{k}_{side}","secondary",.011*r,False,side)
                motif("Vine_Secondary",n,u,v,x,y,.19,angle+side*1.2,f"Branch_{face}_{k}_{side}","secondary",.010*r,False,side)
            # Dense small, varied flourishes placed in interstitial wedges.
            theta=angle+math.pi/8
            for j,rho in enumerate((.44,.70,.91)):
                x,y=rho*math.cos(theta),rho*math.sin(theta)
                role=("Cloud_A","Fern_A","Filler_A")[j]
                motif(role,n,u,v,x,y,.12 if j==0 else .095,theta+(j%2)*.8,
                      f"Fill_{face}_{k}_{j}","filler",.007*r,False,(-1)**k)
            # Outer leaf buds punctuate the panel's edge without regular full-surface tiling.
            if refinement>=1:
                theta=angle+.25;rho=.82
                motif("Leaf_A",n,u,v,rho*math.cos(theta),rho*math.sin(theta),.085,theta-1.2,
                      f"SmallLeaf_{face}_{k}","filler",.006*r,True)
        # Explicit aperture rims are allowed in the border reserve.
        for ring,rr in enumerate((hole+.010,hole+.046)):
            height=math.sqrt(1-rr*rr)
            pts=[mul(add(mul(n,height),add(mul(u,rr*math.cos(t*2*math.pi/192)),mul(v,rr*math.sin(t*2*math.pi/192)))),r+.007*r) for t in range(192)]
            curves.append({"name":f"DoubleBorder_{face}_{ring}","points":pts,"width":(.020 if ring==0 else .014)*r*border_scale,
                           "category":"border","material":"gold","closed":True,"role":"Border_A"})
        # Milgrain + scalloped outer fillet: 48 beads and 24 miniature petal arches per opening.
        for k in range(48):
            theta=k*2*math.pi/48;rr=hole+.029
            beads.append({"position":mul(add(mul(n,math.sqrt(1-rr*rr)),add(mul(u,rr*math.cos(theta)),mul(v,rr*math.sin(theta)))),r+.014*r),"radius":.009*r,"category":"border"})
        for k in range(24):
            pts=[]
            for j in range(17):
                t=j/16; theta=(k+t)*2*math.pi/24
                border_sample=cache["Border_A"][min(len(cache["Border_A"])-1,int(t*(len(cache["Border_A"])-1)))][1]
                rr=hole+.049+.024*math.sin(math.pi*t)+.009*border_sample
                pts.append(mul(add(mul(n,math.sqrt(1-rr*rr)),add(mul(u,rr*math.cos(theta)),mul(v,rr*math.sin(theta)))),r+.006*r))
            curves.append({"name":f"Scallop_{face}_{k}","points":pts,"width":.006*r,"category":"border","material":"gold","closed":False,"role":"Border_A"})
    # Eight layered peony rosettes on cube-diagonal hubs, crossing panel seams naturally.
    for ix,(a,b,c) in enumerate(( (a,b,c) for a in (-1,1) for b in (-1,1) for c in (-1,1))):
        n=unit([a,b,c]);u,v=frame(n)
        for layer,(count,size,offset) in enumerate(((11,.195,.035),(9,.135,.026),(7,.083,.010))):
            for k in range(count):
                angle=k*2*math.pi/count+layer*.32+ix*.15
                # Individual domed petals create true relief surfaces.
                motif("Flower_A",n,u,v,offset*math.cos(angle),offset*math.sin(angle),size,angle,
                      f"Peony_{ix}_{layer}_{k}","primary",.006*r,True)
                if refinement>=2 and surfaces and surfaces[-1]["name"]==f"Peony_{ix}_{layer}_{k}":
                    surfaces[-1]["height"]=(.021+.014*layer)*r
                    surfaces[-1]["base_offset"]=.004*layer*r
                    curves[-1]["points"]=[mul(unit(p),r+(.004+.004*layer)*r) for p in curves[-1]["points"]]
        beads.append({"position":mul(n,r+.045*r),"radius":.026*r,"category":"primary"})
        for k in range(7):
            theta=k*math.tau/7
            beads.append({"position":mapped(n,u,v,.043*math.cos(theta),.043*math.sin(theta),r+.027*r),"radius":.009*r,"category":"primary"})
    for curve in curves:curve["width"]=max(curve["width"],min_width)
    # A bounded density repair only removes tertiary detail, preserving structural vines and flowers.
    density=data["ornament"].get("density",.88)
    if density<.8:
        removed={c["name"] for i,c in enumerate(curves) if c["category"]=="filler" and i%3==0}
        curves=[c for c in curves if c["name"] not in removed]
        actions.append({"repair":"reduce_filler_density","removed_curves":len(removed),"category":"filler"})
    plan={"showcase_version":"1.0","spec_hash":spec.spec_hash,"seed":spec.seed,"radius":r,
          "wall_thickness":data["base_surface"].get("shell_thickness",.06*r),"opening_ratio":hole,"opening_count":6,
          "minimum_feature_width":min_width,"refinement":refinement,"curves":curves,"surfaces":surfaces,"beads":beads,
          "material_style":data["ornament"].get("style","ivory_gilt_peony_filigree"),"density":data["ornament"].get("density",.88),
          "exclusion_actions":actions,"shell":{"sectors":96,"rings":24,"cutout_rows":[5,12,19] if refinement>=2 else [7,12,17],
                                                 "cutout_period":12,"cutout_width":4,"cutout_height":5 if refinement>=2 else 2},
          "composition":"Six directional acanthus panels and eight layered diagonal peonies",
          "render":{"engine":"CYCLES","samples":48,"resolution":1200},"definitions_hashes":{k:content_hash(v) for k,v in definitions.items()}}
    if data["ornament"].get("style")=="ivory_carved_botanical_v1":
        from .detail_plan import upgrade
        upgrade(plan,definitions,spec)
    plan["plan_hash"]=content_hash(plan)
    return plan
