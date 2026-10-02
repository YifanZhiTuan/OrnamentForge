"""Current planar-master pipeline. Source manifests are read-only."""
import argparse,csv,hashlib,json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from ornamentforge.spec import normalize_spec
from ..surface.transfer import map_surface

ROOT=Path(__file__).resolve().parents[4]
LIB=ROOT/'art_direction/ArtLibrary'
OUT=ROOT/'runs/current/planar'
THEMES={'团龙':('dragon','SX1_001'),'龙纹':('dragon','SX1_001'),'凤穿牡丹':('phoenix','SX1_018'),'缠枝莲':('lotus|vine_scroll','DH_018'),'敦煌藻井':('lotus|vine_scroll','DH_018'),'莲花团花':('lotus','DH_017'),'苏绣感花叶':('floral|bird_flower','SX1_037'),'民族花纹':('geometric|mixed','MZY_026')}
ROLES=['hero','secondary','border','connector','filler','repeating']
CASES={'dragon':('团龙','SX1_001',.89,0),'phoenix':('凤穿牡丹','SX1_018',.92,0),'dunhuang':('敦煌藻井','DH_018',1,.33)}

def write(p,v):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def source(id):
    paths=list((LIB/'01_CORE_IMAGES'/id.split('_')[0]).glob(id+'.*'))
    if len(paths)!=1:raise ValueError('Expected one source '+id)
    return paths[0]
def retrieve(theme):
    hits=[k for k in THEMES if k in theme]
    if not hits:raise ValueError('Unsupported theme: manual visual search required')
    key=max(hits,key=len);terms,preferred=THEMES[key]
    manifest=LIB/'03_MANIFEST/CORE_LEARNING_SET.csv'
    with manifest.open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    def score(r):
        return (100 if r['id']==preferred else 0)+20*any(t in r['motif_primary'] for t in terms.split('|'))+({'S':3,'A':2,'B':1}.get(r['art_quality'],0))
    candidates=sorted([r for r in rows if score(r)>=20 or (key=='民族花纹' and r['pack']=='MZY')],key=lambda r:(-score(r),r['id']))[:18]
    # Supplement scarce heroes with explicitly marked composition/frame candidates.
    if len(candidates)<12:
        seen={r['id'] for r in candidates}
        support=[r for r in rows if r['pack'] in ['DH','JX'] and r['id'] not in seen]
        candidates+=sorted(support,key=lambda r:(-score(r),r['id']))[:12-len(candidates)]
    result={'theme':theme,'matched_theme':key,'manifest_sha256':sha(manifest),'approved_geometry_reused':False,'rights':'Reference rights unknown; user-authorized local reconstruction only. No public redistribution or approved-library registration.','candidates':[]}
    result.update({r:[] for r in ROLES})
    for row in candidates:
        c={**row,'image_path':str(source(row['id'])),'score':score(row),'match_scope':'theme' if score(row)>=20 else 'frame_composition_support_not_theme_match','inspection':'viewed' if row['id'] in ['SX1_001','SX1_004','SX1_018','DH_018'] else 'metadata_only','module_status':'candidate_not_extracted'}
        result['candidates'].append(c)
        r={'hero_motif':'hero','secondary_motif':'secondary','border':'border','composition_only':'repeating'}.get(row['image_role'],'filler')
        result[r].append({'source_id':row['id'],'status':'candidate','reason':row['image_role']+' / '+row['motif_primary']})
        if row['motif_primary'] in ['vine_scroll','cloud']:result['connector'].append({'source_id':row['id'],'status':'candidate','reason':'Flow-bearing motif; requires localization'})
    result['missing_roles']=[r for r in ROLES if not result[r]]
    return result

def retrieve_reference(path):
    """Exact known-image identity, explicitly not perceptual similarity search."""
    fingerprint=sha(Path(path))
    for case,(theme,id,cut,hole) in CASES.items():
        if fingerprint==sha(source(id)):
            result=retrieve(theme);result['input_reference']={'path':str(Path(path).resolve()),'sha256':fingerprint,'match':'exact_bytes','source_id':id};return result
    raise ValueError('Unrecognized reference: inspect and add a source/module annotation; no silent preset substitution')

def smooth(t):
    t=np.clip(t,0,1);return t*t*(3-2*t)
def crown(mask,width=14):
    d=cv2.distanceTransform(mask.astype('uint8'),cv2.DIST_L2,5)
    return smooth(d/width)
def load_art(id,cut,size=1400):
    im=Image.open(source(id)).convert('RGBA');im=im.crop((0,0,im.width,int(im.height*cut)))
    rgb=Image.new('RGBA',im.size,'white');rgb.alpha_composite(im);im=rgb.convert('RGB')
    a=np.array(im);ink=a.min(2)<170;ys,xs=np.where(ink)
    im=im.crop((max(0,xs.min()-12),max(0,ys.min()-12),min(im.width,xs.max()+13),min(im.height,ys.max()+13)))
    im.thumbnail((int(size*.86),int(size*.86)),Image.Resampling.LANCZOS)
    canvas=Image.new('RGB',(size,size),'white');canvas.paste(im,((size-im.width)//2,(size-im.height)//2))
    return np.array(canvas)

def assemble_field(field,placement):
    """Reposition a module field in normalized 10-unit master coordinates."""
    size=field.shape[0];scale=float(placement.get('scale',1));angle=float(placement.get('rotation_degrees',0));tx,ty=placement.get('translation',[0,0])
    if not (.5<=scale<=1.5) or not np.isfinite([scale,angle,tx,ty]).all():raise ValueError('Invalid module placement')
    matrix=cv2.getRotationMatrix2D(((size-1)/2,(size-1)/2),angle,scale);matrix[:,2]+=[tx*(size-1)/10,-ty*(size-1)/10]
    return cv2.warpAffine(field,matrix,(size,size),flags=cv2.INTER_LINEAR)

def current_planar_spec(theme,id):
    """Derive a valid current spec from the checked-in schema example."""
    spec=json.loads((ROOT/'schemas/example_ornament_spec.json').read_text(encoding='utf8'))
    spec['input']={'mode':'mixed','prompt':theme+' current planar master','reference_images':[str(source(id))]}
    spec['base_surface']={'type':'plane','dimensions':[10,10,.2],'shell_thickness':.19}
    spec['composition'].update({'preset':'NONE','symmetry':'none','symmetry_count':1,'negative_space':.25})
    spec['openings']=[]
    spec['ornament'].update({'subject':theme,'style':'OrnamentForge Current Planar Master','density':.65})
    spec['ornament']['primary_motifs']=[{'id':id+'_local_reconstruction','type':'reference_group','importance':'primary','source':'generated','scale':1,'rotation_degrees':0,'tags':['reference_locked']}]
    spec['ornament']['secondary_motifs']=[]
    spec['layout'].update({'method':'radial','border_clearance':.1,'minimum_spacing':.03,'flow_strength':.8})
    spec['surface_mapping'].update({'method':'planar','normal_offset':0})
    spec['geometry'].update({'ornament_height':.19,'engrave_depth':.04,'minimum_feature_width':.02,'minimum_wall_thickness':.16,'bevel':.01,'boolean_tolerance':.005})
    spec['generation']={'seed':20260929,'quality':'draft','max_repair_attempts':1}
    spec['target']={'mode':'editable','export_formats':['blend']}
    normalize_spec(spec)
    return spec

def build(case,assembly_path=None):
    theme,id,cut,hole=CASES[case];out=OUT/('master_'+case);out.mkdir(parents=True,exist_ok=True)
    refs=retrieve(theme);write(out/'references.json',refs)
    a=load_art(id,cut);sz=a.shape[0];yy,xx=np.mgrid[:sz,:sz];u=(xx/(sz-1)-.5)*10;v=(.5-yy/(sz-1))*10;rho=np.hypot(u,v)/5
    if case!='dunhuang':
        ink=(a.mean(2)<160).astype('uint8');ink=cv2.morphologyEx(ink,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
        count,labels,stats,_=cv2.connectedComponentsWithStats(1-ink)
        # Enclosed paper regions become volumes, not uniformly raised black strokes.
        enclosed=np.zeros_like(ink)
        for j in range(1,count):
            x,y,w,h,area=stats[j]
            if x>0 and y>0 and x+w<sz and y+h<sz and area>9:enclosed[labels==j]=1
        silhouette=cv2.morphologyEx((enclosed|ink),cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
        if case=='dragon':
            primary=(rho<.66);secondary=(rho>=.66)&(rho<.79);connector=~(primary|secondary)
        else:
            secondary=((u+1.55)**2/2.35**2+(v+1.9)**2/1.75**2<1);connector=(v<-2.45)&~secondary;primary=~(secondary|connector)
        masks={'hero':silhouette*primary,'secondary':silhouette*secondary,'connector':silhouette*connector}
        # Broad silhouette crown plus internal region volume; shallow seams retain original drawing.
        broad=crown(silhouette,8);lobes=crown(enclosed,13)
        fields={role:cv2.GaussianBlur((((.165 if role=='hero' else .125)*broad+.055*lobes)*mask).astype('f4'),(0,0),1.6) for role,mask in masks.items()}
        color=np.zeros((*ink.shape,3),np.float32);color[:]=[.14,.25,.26] if case=='dragon' else [.22,.13,.18]
        palette={'hero':[.78,.59,.27],'secondary':[.83,.70,.43],'connector':[.44,.59,.49]}
        for role,mask in masks.items():
            t=cv2.GaussianBlur(mask.astype('f4'),(0,0),1.2)[...,None];color=color*(1-t)+np.array(palette[role])*t
    else:
        # Palette segmentation preserves the selected original; distance sections provide real volume.
        im=Image.fromarray(a).quantize(colors=18);labels=np.array(im);pal=np.array(im.getpalette()).reshape(-1,3)
        masks={'hero':np.zeros((sz,sz),np.uint8),'secondary':np.zeros((sz,sz),np.uint8),'connector':np.zeros((sz,sz),np.uint8)}
        fields={r:np.zeros((sz,sz),np.float32) for r in masks}
        for j,c in enumerate(pal[:18]):
            r,g,b=map(float,c)
            if min(c)>235 or max(c)<75:continue
            role='hero' if b>r*.98 and b>g*.88 else 'secondary' if min(c)>140 else 'connector'
            m=((labels==j)&(rho>.35)&(rho<.88)).astype('uint8');masks[role]|=m
            fields[role]=np.maximum(fields[role],(.19 if role=='hero' else .14 if role=='secondary' else .07)*crown(m,12))
        fields={r:cv2.GaussianBlur(f,(0,0),1.4) for r,f in fields.items()}
        color=cv2.GaussianBlur(a.astype('f4')/255,(0,0),1)
        color[rho>.89]=[.21,.24,.20];color[rho<.35]=[.21,.24,.20]
    border=.10*np.exp(-((rho-.96)/.012)**2)+.055*np.exp(-((rho-.915)/.01)**2)
    if hole:border+=.08*np.exp(-((rho-hole-.019)/.012)**2)
    fields['border']=border.astype('f4')
    placement={'translation':[0,0],'rotation_degrees':0,'scale':1}
    if assembly_path:
        edit=json.loads(Path(assembly_path).read_text(encoding='utf8'))
        if edit['source_id']!=id:raise ValueError('Assembly source does not match extraction recipe')
        placement=edit.get('group_placement',placement)
        for role in masks:
            fields[role]=assemble_field(fields[role],placement)*float(edit.get('role_height_scale',{}).get(role,1))
            masks[role]=(assemble_field(masks[role].astype('f4'),placement)>.5).astype('uint8')
            if np.any((fields[role]>.005)&((rho>.90)|(rho<hole))):raise ValueError('Placement collides with reserved frame/opening')
        # Palette follows the same group transform; outside is the established substrate color.
        moved=assemble_field(color.astype('f4'),placement);covered=assemble_field(np.ones((sz,sz),np.float32),placement)
        color=moved+color*(1-covered[...,None])
    valid=(rho<.995)&(rho>hole)
    for r in fields:fields[r]*=valid
    color[border>.02]=[.73,.57,.30]
    Image.fromarray(a).save(out/'source_layout.png')
    regions=[];modules=[]
    for role,m in masks.items():
        cv2.imwrite(str(out/f'module_{role}.png'),m*255)
        contours,_=cv2.findContours(m,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            if cv2.contourArea(c)<25:continue
            c=cv2.approxPolyDP(c,1.2,True).reshape(-1,2);regions.append({'role':role,'points':[[float((x/(sz-1)-.5)*10),float((.5-y/(sz-1))*10)] for x,y in c]})
        modules.append({'id':id+'_'+role,'source_id':id,'role':role,'mask':f'module_{role}.png','mask_sha256':sha(out/f'module_{role}.png'),'placement':placement,'assembly_group':'reference_locked_layout','localization':'coarse spatial partition intersected with extracted silhouette; not automatic semantic recognition','allow_independent_transform':False})
    plan={'version':'4.0','theme':theme,'source_id':id,'source_sha256':sha(source(id)),'modules':modules,'border':{'type':'generated_continuous_double_rim','reason':'Frame closes existing circular flow without adding unrelated motifs'},'filler':[],'repeating':{'source':'preserved original repeat positions','new_instances':0},'domain':{'radius':5,'inner_radius':hole*5},'color_provenance':'Reference palette' if hole else 'New limited enamel/gilt palette; original is monochrome','editable_contract':'Role shape keys and closed guide curves in blend; mask/placement edits require rebuilding; reference-locked group is deliberate, not arbitrary recomposition.'}
    plan['group_placement']=placement;plan['role_height_scale']=edit.get('role_height_scale',{}) if assembly_path else {}
    write(out/'AssemblyPlan.json',plan);write(out/'editable_regions.json',regions)
    refs['selected_modules']=modules
    for m in modules:refs[m['role']].insert(0,{'source_id':id,'module_id':m['id'],'status':'extracted_coarse_mask','mask':m['mask'],'placement':m['placement']})
    write(out/'references.json',refs)
    nr,na=440,1280;r=np.linspace(max(.004,hole*5),5,nr);theta=np.arange(na)*2*np.pi/na;x=r[:,None]*np.cos(theta);y=r[:,None]*np.sin(theta)
    mx=((x/10+.5)*(sz-1)).astype('f4');my=((.5-y/10)*(sz-1)).astype('f4')
    sample=lambda f:cv2.remap(f,mx,my,cv2.INTER_LINEAR)
    fs=np.array([sample(f) for f in fields.values()]);rgb=sample(color.astype('f4'))
    np.savez_compressed(out/'master.npz',x=x,y=y,fields=fs,rgb=rgb,roles=np.array(list(fields)),inner_radius=hole*5)
    spec=current_planar_spec(theme,id);write(out/'OrnamentSpec.json',spec)
    art={'version':'current','id':out.name,'title':theme+'平面母版','input':{'theme':theme,'mode':'FAST_ART_MODE'},'status':'BUILT_PENDING_VISUAL_REVIEW','references_file':'references.json','visual_studies':[{'id':id,'observation':{'dragon':'蟠龙主体与外侧云蝠形成天然圆形主次。','phoenix':'凤尾绕上左，牡丹压住左下，右侧凤头为焦点。','dunhuang':'蓝色卷草和浅色花叶构成连续放射环带。'}[case],'borrow':'原始整体流线与相对位置','avoid':'不复制页脚文字，不把黑色线稿直接统一挤出'}],'composition':{'form':'annular' if hole else 'round','assembly':'AssemblyPlan.json'},'layers':list(fields),'negative_space':{'policy':'保留源图空域，边框与主体之间留缓冲'},'border_cutout':{'central_hole':bool(hole),'adaptation':'移除敦煌原图中心团花形成环形母版' if hole else 'solid disc'},'macro_validation':{'required':['clay_front.png','clay_3q.png'],'status':'PENDING'},'presentation':['clay_front','clay_3q','color_front'],'risks':['线稿来源内部细线较密，尚非语义雕塑级','模块是人工选区+轮廓提取，不是通用图像理解'],'handoff':{'allow_high_detail':False,'transfer_requires':'render-bound master_review.json'}}
    write(out/'ArtPlan.json',art)
    map_surface(out,'flat_plate' if not hole else 'annular_plate',out,require_review=False)
    return out

def approve(master,observation):
    files=['clay_front.png','clay_3q.png','color_front.png','AssemblyPlan.json','geometry_qa.json']
    write(master/'master_review.json',{'status':'FAST_ART_TRANSFER_READY','reviewer':'assistant_visual_inspection','observation':observation,'master_sha256':sha(master/'master.npz'),'evidence':{f:sha(master/f) for f in files},'not_claimed':['sculpture grade','manufacturing ready','user final acceptance']})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['retrieve','build','approve','transfer']);p.add_argument('name');p.add_argument('--host',default='flat_plate');p.add_argument('--observation');p.add_argument('--assembly');p.add_argument('--reference');a=p.parse_args()
    if a.action=='retrieve':write(OUT/'retrieval'/f'{a.name}.json',retrieve_reference(a.reference) if a.reference else retrieve(a.name))
    elif a.action=='build':print(build(a.name,a.assembly))
    elif a.action=='approve':
        if not a.observation:p.error('Visual observation required')
        approve(OUT/('master_'+a.name),a.observation)
    else:print(map_surface(OUT/('master_'+a.name),a.host,OUT/('transfer_'+a.name)))
