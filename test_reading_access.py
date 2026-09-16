import unittest
from reading_access import reading_view
from documents import reading_pdf
from content import fallback_reading
from test_app import example
from pypdf import PdfReader
from io import BytesIO

class PreviewAccessTests(unittest.TestCase):
    def test_free_reading_is_complete_and_does_not_mutate_saved_content(self):
        reading={'title':'A personal direction','summary':' '.join(['Summary']*40),'insight':' '.join(['Insight']*20),'sections':[{'title':str(i),'text':' '.join([f'SECRET{i}']*100)} for i in range(4)]}
        free,meta=reading_view(reading,'free')
        self.assertEqual(free,reading)
        self.assertEqual(meta,dict(percent=100,locked_sections=[]))
        free['sections'][0]['text']='Changed by caller'
        self.assertNotEqual(free,reading)
        self.assertEqual(reading_view(reading,'reading')[0],reading)

    def test_free_pdf_and_browser_include_all_four_perspectives(self):
        reading=fallback_reading(example());free,_=reading_view(reading,'free')
        data=dict(reading=reading,answers=example(),tier='free')
        text=' '.join(p.extract_text() for p in PdfReader(BytesIO(reading_pdf(data))).pages)
        normalized=' '.join(text.split())
        for chapter in reading['sections']:
            self.assertIn(' '.join(chapter['text'].split()),normalized)
        self.assertNotIn('40%',text)
        self.assertIn(' '.join(free['title'].split()),' '.join(text.split()))

if __name__=='__main__':unittest.main()
