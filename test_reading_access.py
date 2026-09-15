import unittest
from reading_access import reading_view
from documents import reading_pdf
from content import fallback_reading
from test_app import example
from pypdf import PdfReader
from io import BytesIO

class PreviewAccessTests(unittest.TestCase):
    def test_free_excerpt_has_word_budget_and_no_locked_text(self):
        reading={'title':'A personal direction','summary':' '.join(['Summary']*40),'insight':' '.join(['Insight']*20),'sections':[{'title':str(i),'text':' '.join([f'SECRET{i}']*100)} for i in range(4)]}
        free,meta=reading_view(reading,'free')
        words=lambda r:len((' '.join([r['summary'],r['insight']]+[s['text'] for s in r['sections']])).split())
        self.assertLessEqual(words(free),int(words(reading)*.4))
        self.assertNotIn('SECRET2',str(free));self.assertNotIn('SECRET3',str(meta))
        self.assertEqual(meta['percent'],40)
        self.assertEqual(reading_view(reading,'reading')[0],reading)

    def test_pdf_and_browser_use_same_excerpt(self):
        reading=fallback_reading(example());free,_=reading_view(reading,'free')
        data=dict(reading=reading,answers=example(),tier='free')
        text=' '.join(p.extract_text() for p in PdfReader(BytesIO(reading_pdf(data))).pages)
        self.assertNotIn(reading['sections'][-1]['text'],text)
        self.assertIn(' '.join(free['title'].split()),' '.join(text.split()))

if __name__=='__main__':unittest.main()
