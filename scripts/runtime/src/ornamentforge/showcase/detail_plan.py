"""Reference-directed ivory carving composition; reuses canonical leaf/petal library."""
import math
import random
from .plan import unit,mul,add,dot,frame,mapped,sample,AXES

def upgrade(plan,definitions,spec):
    rng=random.Random(spec.seed+902);r=plan['radius'];hole=plan['opening_ratio']
    plan['detail_upgrade']='reference-aligned-v1'
    plan['shell']={'sectors':192,'rings':48,'cutout_rows':[10,17,24,31,38],
                   'cutout_period':12,'cutout_width':4,'cutout_height':4,'staggered':True}
    # Reduce flower diameter, remove outline loops, and remove isolated tertiary squiggles.
    plan['curves']=[c for c in plan['curves'] if
                    not c['name'].startswith(('Peony_','Leaf_','Scallop_'))]
    plan['surfaces']=[s for s in plan['surfaces'] if s['category']!='filler']
    for s in plan['surfaces']:
        if s['name'].startswith('Peony_'):
            ix=int(s['name'].split('_')[1]);n=unit(list(((a,b,c) for a in (-1,1) for b in (-1,1) for c in (-1,1)))[ix])
            s['boundary']=[mul(unit(add(n,mul(add(unit(p),mul(n,-1)),.56))),r+.003*r) for p in s['boundary']]
            s['height']*=.70;s['base_offset']=s.get('base_offset',0)*.65
    for c in plan['curves']:
        c['material']='ivory'
        if c['category']!='border':c['width']=max(.005*r,c['width']*.62)
        else:c['width']*=1.2
    plan['beads']=[]
    cache={role:sample(definitions[role],3) for role in ('Leaf_A','Leaf_B','Flower_A')}
    stats={'fern_fronds':0,'small_flowers':0,'leaflets':0,'leaf_variants':6,'rim_teeth':0}
    limit=math.sqrt(1-(hole+.031)**2)
    def safe(points):return all(max(abs(x) for x in unit(p))<limit for p in points)
    def stroke(name,pts,width,category='filler',role='Fern_A'):
        if not safe(pts):return
        plan['curves'].append(dict(name=name,points=pts,width=max(width,plan['minimum_feature_width']),
                                   category=category,material='ivory',closed=False,role=role))
    def leaf(n,u,v,x,y,length,angle,width,height,name,role='Leaf_A',category='filler',variant=0):
        co,si=math.cos(angle),math.sin(angle);pts=[]
        for a,b,_ in cache[role]:
            # Six articulated variants use the same stored canonical leaf geometry.
            bend=(variant%3-1)*.16*math.sin(math.pi*a)
            lateral=b*width+(bend if role!='Flower_A' else 0)
            xx=x+length*(a*co-lateral*si);yy=y+length*(a*si+lateral*co)
            pts.append(mapped(n,u,v,xx,yy,r+.003*r))
        if not safe(pts):return
        plan['surfaces'].append(dict(name=name,boundary=pts,category=category,role=role,
             height=height*r,base_offset=.001*r,material='ivory'))
        stats['leaflets']+=1
        # Raised midrib: visibly carved surface at close range.
        if length>.036:
            points=[mapped(n,u,v,x+length*t*co,y+length*t*si,r+height*r*math.sin(math.pi*t)+.004*r)
                    for t in [i/10 for i in range(11)]]
            stroke(name+'_vein',points,.0035*r,category,role)
    def fern(n,u,v,x,y,length,angle,name,variant):
        bend=rng.uniform(-.7,.7);co,si=math.cos(angle),math.sin(angle)
        def spine(t):
            a=length*t;b=length*bend*t*t
            return x+a*co-b*si,y+a*si+b*co,angle+math.atan(2*bend*t)
        points=[mapped(n,u,v,*spine(i/24)[:2],r+.009*r) for i in range(25)]
        if not safe(points):return
        stroke(name+'_stem',points,.006*r,'filler','Fern_A');stats['fern_fronds']+=1
        pairs=9+variant%4
        for j in range(pairs):
            t=.08+.84*j/pairs;xx,yy,theta=spine(t)
            size=length*(.25*math.sin(math.pi*(.15+.8*t))+.03)*rng.uniform(.90,1.08)
            for side in (-1,1):
                leaf(n,u,v,xx,yy,size,theta+side*(.92+.2*t),1.65 if variant%2 else 2.0,
                     .017+.013*math.sin(math.pi*t),f'{name}_p{j}_{side}',variant=variant)
        xx,yy,theta=spine(.87)
        leaf(n,u,v,xx,yy,length*.15,theta,1,.020,name+'_tip',variant=variant)
    def flower(n,u,v,x,y,size,name,variant):
        count=7+variant%5;stats['small_flowers']+=1
        for j in range(count):
            a=j*math.tau/count+variant*.37
            leaf(n,u,v,x,y,size,a,.8,.026,name+f'_p{j}','Flower_A','secondary')
        center=mapped(n,u,v,x,y,r+.021*r)
        if safe([center]):plan['beads'].append({'position':center,'radius':.008*r,'category':'secondary'})
    # Staggered, face-specific frond clusters: each panel differs in direction and scale.
    for f,n in enumerate(AXES):
        u,v=frame(n)
        for band,(rho,count) in enumerate(((.39,10),(.57,12),(.79,13),(1.02,11))):
            for k in range(count):
                a=math.tau*(k+rng.uniform(-.22,.22))/count+f*.47+band*.29
                rr=rho+rng.uniform(-.028,.028);x,y=rr*math.cos(a),rr*math.sin(a)
                direction=a+(.35 if band%2 else -.50)+rng.uniform(-.35,.35)
                length=rng.uniform(.20,.31) if band<3 else rng.uniform(.18,.29)
                fern(n,u,v,x,y,length,direction,f'FernCluster_{f}_{band}_{k}',(k+f+band)%6)
                if (k+band+f)%4==0:
                    flower(n,u,v,x,y,rng.uniform(.045,.077),f'Floret_{f}_{band}_{k}',k+f)
        # Carved radial teeth replace the detached gold scallop rim.
        for k in range(112):
            a=k*math.tau/112;pts=[]
            for j in range(9):
                t=j/8;rr=hole+.012+.037*t;theta=a+.008*math.sin(math.pi*t)
                pts.append(mul(add(mul(n,math.sqrt(1-rr*rr)),add(mul(u,rr*math.cos(theta)),mul(v,rr*math.sin(theta)))),r+.010*r+.005*r*math.sin(math.pi*t)))
            plan['curves'].append(dict(name=f'RimFlute_{f}_{k}',points=pts,width=.0045*r,category='border',material='ivory',closed=False,role='Border_A'))
            stats['rim_teeth']+=1
        # Short leaves grow radially out of the border reserve, joining it to fern clusters.
        for k in range(40):
            a=k*math.tau/40+f*.10;rho=hole+.064
            x,y=rho*math.cos(a),rho*math.sin(a)
            leaf(n,u,v,x,y,rng.uniform(.065,.09),a+rng.uniform(-.35,.35),1.1,.018,
                 f'RimTransition_{f}_{k}','Leaf_B','secondary',k%6)
    # Fill diagonal panel intersections with larger crossed fronds and small blossoms.
    for hub,(a,b,c) in enumerate(( (a,b,c) for a in (-1,1) for b in (-1,1) for c in (-1,1))):
        n=unit([a,b,c]);u,v=frame(n)
        for k in range(13):
            angle=k*math.tau/13+rng.uniform(-.2,.2)+hub*.57
            rho=rng.uniform(.065,.24)
            fern(n,u,v,rho*math.cos(angle),rho*math.sin(angle),rng.uniform(.20,.32),
                 angle+rng.uniform(.55,1.45),f'HubFern_{hub}_{k}',(hub+k)%6)
            if k%3==0:
                flower(n,u,v,rho*math.cos(angle),rho*math.sin(angle),rng.uniform(.055,.085),
                       f'HubFlower_{hub}_{k}',k+hub)
    # Target uncovered pockets rather than uniformly increasing the whole sphere's density.
    centers=[]
    for item in plan['surfaces']:
        points=item['boundary'];centers.append(unit([sum(p[i] for p in points)/len(points) for i in range(3)]))
    pockets=0
    for k in range(1100):
        z=1-2*(k+.5)/1100;a=k*math.pi*(3-math.sqrt(5));q=math.sqrt(1-z*z)
        n=[q*math.cos(a),q*math.sin(a),z]
        if max(abs(x) for x in n)>math.sqrt(1-(hole+.07)**2):continue
        if any(n[0]*c[0]+n[1]*c[1]+n[2]*c[2]>math.cos(.060) for c in centers):continue
        u,v=frame(n);angle=rng.random()*math.tau
        fern(n,u,v,-.025,0,rng.uniform(.10,.16),angle,f'PocketFern_{k}',k%6)
        if k%3==0:flower(n,u,v,0,0,rng.uniform(.035,.052),f'PocketFloret_{k}',k)
        centers.append(n);pockets+=1
    stats['targeted_pockets']=pockets
    plan['detail_statistics']=stats
    plan['composition']='Ivory carved fern garden; staggered fronds, small rosettes and radially fluted integrated rims'
