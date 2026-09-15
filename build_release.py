"""Build a credential-free release from the current source. Preview by default."""
from pathlib import Path
import argparse,zipfile,hashlib,json,re,urllib.parse
ROOT=Path(__file__).resolve().parent
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--origin');p.add_argument('--publish',action='store_true');a=p.parse_args()
    if a.publish and not a.origin:p.error('An explicit HTTPS origin is required for indexable pages')
    if a.origin:
        u=urllib.parse.urlsplit(a.origin)
        if u.scheme!='https' or not u.netloc or u.path not in ('','/') or u.query or u.fragment:p.error('Use an exact HTTPS origin')
    public=ROOT/'public';references='\n'.join(f.read_text(encoding='utf-8') for f in public.rglob('*') if f.suffix in ['.html','.css','.js','.json'])+(ROOT/'catalog.json').read_text(encoding='utf-8')
    files={};excluded=[]
    for f in public.rglob('*'):
        if not f.is_file():continue
        if f.suffix in ['.png','.jpg','.jpeg','.mp4'] and f.name not in references:
            excluded.append(str(f.relative_to(ROOT)));continue
        content=f.read_bytes()
        if f.suffix=='.html' and a.origin:
            text=content.decode('utf-8');text=text.replace('</head>','<link rel="canonical" href="'+a.origin.rstrip('/')+'/'+f.name+'"></head>')
            if a.publish and f.name not in ['quiz.html','result.html','help.html']:
                text=re.sub(r'<meta[^>]*name=[\"\']robots[\"\'][^>]*>|<meta[^>]*content=[\"\']noindex[^>]*>', '',text,flags=re.I)
            content=text.encode('utf-8')
        files[f.relative_to(ROOT).as_posix()]=content
    for f in ROOT.iterdir():
        if f.is_file() and (f.suffix in ['.py','.md'] or f.name in ['requirements.txt','catalog.json','config.example.json','Procfile','render.yaml','INICIAR.cmd']):files[f.name]=f.read_bytes()
    if a.origin:
        pages=[n for n in files if n.startswith('public/') and n.endswith('.html') and Path(n).name not in ['quiz.html','result.html','help.html']]
        if a.publish:
            files['public/sitemap.xml']=('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+a.origin.rstrip('/')+'/'+Path(n).name+'</loc></url>' for n in pages)+'</urlset>').encode()
        files['public/robots.txt']=(('User-agent: *\nDisallow: /api/\nDisallow: /quiz.html\nDisallow: /result.html\nDisallow: /help.html\nSitemap: '+a.origin.rstrip('/')+'/sitemap.xml\n') if a.publish else 'User-agent: *\nDisallow: /\n').encode()
    manifest={'mode':'publish' if a.publish else 'preview','origin':a.origin,'excluded_unused_assets':excluded,'files':{name:hashlib.sha256(data).hexdigest() for name,data in files.items()}}
    files['RELEASE-MANIFEST.json']=json.dumps(manifest,indent=2).encode()
    output=Path(a.output).resolve();output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,9,15,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,data)
    print(json.dumps({'file':str(output),'bytes':output.stat().st_size,'files':len(files),'excluded_assets':len(excluded)}))
if __name__=='__main__':main()
