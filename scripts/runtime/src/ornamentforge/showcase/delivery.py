"""Artifact verification and optional video assembly for the specialized showcase."""
from pathlib import Path
import struct
import subprocess

VIEWS=("hero","front","side","top","detail_01","detail_02")
STAGES=("01_base","02_openings","03_borders","04_primary_vines","05_secondary_motifs",
        "06_dense_pattern","07_cutout","08_final")


def verify_artifacts(root,preview=False):
    root=Path(root);images=[root/"stages"/(name+".png") for name in STAGES]
    if not preview:images.extend(root/"renders"/(name+".png") for name in VIEWS)
    dimensions={}
    for path in images:
        with path.open("rb") as stream:header=stream.read(24)
        if header[:8]!=b"\x89PNG\r\n\x1a\n" or len(header)!=24:raise ValueError(f"Invalid PNG: {path}")
        size=struct.unpack(">II",header[16:24])
        if min(size)<600:raise ValueError(f"Undersized render: {path}")
        dimensions[str(path.relative_to(root))]=list(size)
    for name in ("editable_showcase.blend","final_showcase.blend"):
        path=root/name
        with path.open("rb") as stream:header=stream.read(7)
        # Blender can save uncompressed, gzip or Zstandard .blend streams.
        recognized=header==b"BLENDER" or header.startswith((b"\x1f\x8b",b"\x28\xb5\x2f\xfd"))
        if not recognized or path.stat().st_size<10000:raise ValueError(f"Invalid blend signature: {path}")
    return {"blend_files_valid":True,"stage_images":8,"final_views":0 if preview else 6,"image_dimensions":dimensions}


def encode_process(root,ffmpeg):
    root=Path(root)
    manifest=root/"stages/process_frames.txt"
    text="".join(f"file '{name}.png'\nduration 1.25\n" for name in STAGES)
    manifest.write_text(text+f"file '{STAGES[-1]}.png'\n",encoding="utf-8")
    target=root/"process.mp4"
    subprocess.run([str(ffmpeg),"-y","-f","concat","-safe","0","-i",str(manifest),
                    "-vf","scale=1080:1080,setsar=1,fps=24","-c:v","libx264","-crf","18",
                    "-pix_fmt","yuv420p",str(target)],check=True,capture_output=True,
                   creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    return target


def publish(workspace,root,report):
    """Collect the reference-aligned visual deliverables under the requested names."""
    import json
    import shutil
    workspace=Path(workspace);root=Path(root);target=workspace/'runs/current/showcase/final'
    target.mkdir(exist_ok=True);(target/'renders').mkdir(exist_ok=True)
    for name in ('editable','final'):
        shutil.copy2(root/f'{name}_showcase.blend',target/f'{name}_showcase_v1.blend')
    for name in VIEWS:
        new=name+'_v1' if not name.startswith('detail_') else 'detail_v1_'+name[-2:]
        shutil.copy2(root/'renders'/f'{name}.png',target/'renders'/f'{new}.png')
    shutil.copytree(root/'stages',target/'stages',dirs_exist_ok=True)
    for name in ('turntable','process'):
        if (root/f'{name}.mp4').exists():shutil.copy2(root/f'{name}.mp4',target/f'{name}_v1.mp4')
    for name in ('build_plan.json','qa_report.json','motif_usage.json','showcase_report.json',
                 'blender_determinism.json','spec.normalized.json'):
        shutil.copy2(root/name,target/name)
    receipt=workspace/'runs/current/showcase/delivery.json';receipt.parent.mkdir(parents=True,exist_ok=True)
    receipt.write_text(json.dumps({'run':str(root),'delivery':str(target)},indent=2),encoding='utf-8')
    return target
