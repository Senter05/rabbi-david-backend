"""One server-side excerpt policy for browser, PDF and delivery previews."""
import copy
import re

def reading_view(reading, tier):
    result=copy.deepcopy(reading)
    if tier!='free':
        return result,dict(percent=100,locked_sections=[])
    fields=[('summary',reading.get('summary','')),('insight',reading.get('insight',''))]
    total=sum(len(text.split()) for _,text in fields)+sum(len(s['text'].split()) for s in reading.get('sections',[]))
    budget=max(1,int(total*.40)); remaining=budget
    def take(text):
        nonlocal remaining
        words=text.split()
        if len(words)<=remaining:
            remaining-=len(words); return text
        excerpt=' '.join(words[:remaining])
        ends=list(re.finditer(r'[.!?](?:["”])?(?=\s|$)',excerpt))
        if ends and ends[-1].end()>len(excerpt)*.55: excerpt=excerpt[:ends[-1].end()]
        elif excerpt: excerpt+='…'
        remaining=0
        return excerpt
    for key,text in fields:result[key]=take(text)
    result['sections']=[];locked=[]
    for section in reading.get('sections',[]):
        text=take(section['text']) if remaining else ''
        if text:
            visible={**section,'text':text}
            if text!=section['text']:visible.pop('presentation',None)
            result['sections'].append(visible)
        if text!=section['text']:locked.append(dict(title=section['title']))
    return result,dict(percent=40,locked_sections=locked)
