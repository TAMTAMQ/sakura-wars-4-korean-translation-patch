import json, subprocess, hashlib, concurrent.futures
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BIN=ROOT.parents[1]/'vendor/ffmpeg/ffmpeg-9.0.1-essentials_build/bin'
OUT=ROOT/'assets/extracted/videos'
def run(args):
    r=subprocess.run([str(a) for a in args],capture_output=True)
    if r.returncode: raise RuntimeError(r.stderr.decode('utf-8',errors='replace')[-2500:])
    return r.stdout
def export(path):
    rel=path.relative_to(ROOT/'originals/v05'); dest=OUT/rel.with_suffix(''); dest.mkdir(parents=True,exist_ok=True)
    streams=json.loads(run([BIN/'ffprobe.exe','-v','error','-show_streams','-show_format','-of','json',path]))
    movie=dest/(path.stem+'.mp4'); contact=dest/'contact-sheet.jpg'
    run([BIN/'ffmpeg.exe','-y','-v','error','-i',path,'-map','0:v:0','-map','0:a:0?',
         '-c:v','libx264','-threads','2','-preset','fast','-crf','18','-vf','setsar=1',
         '-c:a','aac','-b:a','192k','-movflags','+faststart',movie])
    v=next(s for s in streams['streams'] if s['codec_type']=='video')
    duration=float(v.get('duration',streams.get('format',{}).get('duration',0)))
    # 전체 영상을 12장으로 요약하고 모든 프레임은 MP4에 보존한다.
    run([BIN/'ffmpeg.exe','-y','-v','error','-i',movie,'-vf',f'fps=12/{max(duration,1)},scale=320:-1,tile=4x3',
         '-frames:v','1','-q:v','3',contact])
    check=json.loads(run([BIN/'ffprobe.exe','-v','error','-show_streams','-of','json',movie]))
    # 실제로 모든 스트림을 끝까지 디코딩해 확인한다.
    run([BIN/'ffmpeg.exe','-v','error','-i',movie,'-f','null','-'])
    original=ROOT/'originals/disc'/rel
    row={'source':rel.as_posix(),'mp4':movie.relative_to(ROOT).as_posix(),'contact_sheet':contact.relative_to(ROOT).as_posix(),
         'duration':duration,'width':v['width'],'height':v['height'],
         'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
         'original_exists':original.exists(),'binary_changed':path.read_bytes()!=original.read_bytes() if original.exists() else None,
         'audio_verified':any(s['codec_type']=='audio' for s in check['streams']), 'full_decode_verified':True,
         'source_streams':streams['streams'],'output_streams':check['streams']}
    (dest/'metadata.json').write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf-8')
    print(path.name+' 완료',flush=True); return row
def main():
    paths=sorted((ROOT/'originals/v05').rglob('*.SFD'))
    rows=[]; errors=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        fs={pool.submit(export,p):p for p in paths}
        for f in concurrent.futures.as_completed(fs):
            try: rows.append(f.result())
            except Exception as e: errors.append({'source':str(fs[f]),'error':str(e)}); print(str(e),flush=True)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'index.json').write_text(json.dumps({'videos':sorted(rows,key=lambda r:r['source']),'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
    print('videos',len(rows),'errors',len(errors),flush=True)
if __name__=='__main__': main()
