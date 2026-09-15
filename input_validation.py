"""Conservative input checks. DNS checks a domain, never mailbox ownership."""
import json
import re
import threading
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import OrderedDict

_CACHE = OrderedDict()
_LOCK = threading.Lock()
_TTL = 900
_MAX_CACHE = 256
_TYPOS = {'gamil.com':'gmail.com', 'gmial.com':'gmail.com', 'gmai.com':'gmail.com',
          'gmail.con':'gmail.com', 'gmail.co':'gmail.com', 'hotmial.com':'hotmail.com',
          'outlok.com':'outlook.com', 'yahoo.con':'yahoo.com'}

def _dns_query(domain, kind):
    # Only the public domain is sent; the name, address and answers stay local.
    query = urllib.parse.urlencode({'name':domain, 'type':kind})
    request = urllib.request.Request('https://cloudflare-dns.com/dns-query?'+query,
                                    headers={'Accept':'application/dns-json'})
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            result = json.loads(response.read(65536))
        if not isinstance(result, dict) or result.get('Status') not in (0,3):
            raise ValueError()
        return result
    except Exception:
        raise ValueError('We could not check the email domain right now. Please try again shortly.') from None

def domain_accepts_mail(domain):
    """MX, or the RFC implicit-MX address fallback; reject explicit null MX."""
    now = time.monotonic()
    with _LOCK:
        item = _CACHE.get(domain)
        if item and now-item[0] < _TTL:
            _CACHE.move_to_end(domain)
            return item[1]
    result = _dns_query(domain, 'MX')
    records = [a.get('data','').strip() for a in result.get('Answer',[]) if a.get('type')==15]
    if result['Status']==3:
        accepted = False
    elif any(re.fullmatch(r'0\s+\.', r) for r in records):
        accepted = False
    elif records:
        accepted = any(len(r.split())==2 and r.split()[1]!='.' for r in records)
    else:
        # A domain without MX may still accept SMTP at its A/AAAA address.
        a = _dns_query(domain, 'A')
        accepted = any(r.get('type')==1 for r in a.get('Answer',[]))
        if not accepted and a['Status']==0:
            aaaa = _dns_query(domain, 'AAAA')
            accepted = any(r.get('type')==28 for r in aaaa.get('Answer',[]))
    with _LOCK:
        _CACHE[domain]=(now,accepted)
        _CACHE.move_to_end(domain)
        while len(_CACHE)>_MAX_CACHE:
            _CACHE.popitem(last=False)
    return accepted

def validate_contact_email(email, *, resolver=None):
    if not isinstance(email,str):
        raise ValueError('Please enter a valid email address.')
    email=email.strip()
    if len(email)>254 or email.count('@')!=1:
        raise ValueError('Please enter a valid email address, such as name@example.com.')
    local,domain=email.rsplit('@',1)
    try:
        domain=domain.encode('idna').decode('ascii').lower()
    except UnicodeError:
        raise ValueError('Please check the domain after @ in your email address.') from None
    if (not 1<=len(local)<=64 or not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+",local)
            or local.startswith('.') or local.endswith('.') or '..' in local):
        raise ValueError('Please check the part of your email address before @.')
    labels=domain.split('.')
    if (len(domain)>253 or len(labels)<2 or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',label) for label in labels)
            or not re.search('[a-z]',labels[-1])):
        raise ValueError('Please check the domain after @ in your email address.')
    if domain in _TYPOS:
        raise ValueError('Did you mean '+_TYPOS[domain]+'? Please check your email address.')
    if not (resolver or domain_accepts_mail)(domain):
        raise ValueError('This email domain could not receive mail according to its DNS records. Please check the spelling or use another email address.')
    return local.lower()+'@'+domain

def validate_written_answer(text):
    if not isinstance(text,str):
        raise ValueError('Please write your answer as text, or leave this optional field blank.')
    text=unicodedata.normalize('NFC',text)
    if any(unicodedata.category(c)=='Cc' and c not in '\n\r\t' for c in text):
        raise ValueError('Please remove unusual control characters from your answer.')
    text=' '.join(text.split())
    if not text:
        return ''
    words=re.findall(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*",text,re.UNICODE)
    if len(words)<2 or sum(c.isalpha() for c in text)<4:
        raise ValueError('Please write at least two meaningful words, or leave this optional field blank.')
    plain=unicodedata.normalize('NFKD',text).encode('ascii','ignore').decode().lower()
    compact=re.sub('[^a-z]','',plain)
    if len(compact)>=6 and (len(set(compact))<=2 or re.fullmatch(r'(.{1,3})\1{2,}',compact)):
        raise ValueError('Please share a short sentence in your own words, or leave this optional field blank.')
    if len(words)>=3 and len(set(w.lower() for w in words))==1:
        raise ValueError('Please share a short sentence rather than repeating the same word.')
    latin=[w for w in words if re.fullmatch('[A-Za-z]+',w)]
    keyboard=('qwerty','asdfgh','zxcvbn','sdfghj','qazwsx')
    suspicious=lambda w: any(k in w.lower() for k in keyboard) or (len(w)>=7 and w.islower() and not re.search('[aeiouy]',w))
    if latin and sum(suspicious(w) for w in latin)>=max(1,len(latin)//2+1):
        raise ValueError('Please check your answer and write a short sentence we can understand, or leave it blank.')
    return text
