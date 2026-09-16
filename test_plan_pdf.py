"""Checks the independent, fixed-length plan document and its source boundaries."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import sys
import unittest

import fitz
from documents import plan_pdf
from source_library import SOURCES


def sample_plan():
    teaching = (
        'This teaching invites a moment of attention before deciding what should come next. '
        'It does not tell you that your circumstances are simple or that an outcome is within your control. '
        'Instead, consider the difference between what you already have, what you genuinely need, and what is asking for care today. '
        'You can approach this idea through quiet thought, a few written words, or a conversation with someone you trust. '
        'The exercise below is a modern way to explore that question; it is not a historical ritual. '
        'There is no need to force a positive answer. A clear and honest observation is enough for this first step.'
    )
    why = (
        'You chose a gentle pace and a short period of reflection. This activity gives you one question to consider '
        'without requiring a purchase, a long conversation or a change to your schedule. You can write a sentence '
        'or say it quietly, depending on your energy today.'
    )
    return {
        'tier': 'personal',
        'answers': {'name': 'Alex Morgan', 'goal': 'calm', 'stage': 'retired', 'time': '5', 'style': 'balanced', 'pace': 'gentle', 'obstacle': 'cost'},
        'plan': [dict(day=i, title=f'A Thoughtful Beginning {i}', minutes=5,
                      teaching=teaching, why=why, source_id=SOURCES[(i-1) % len(SOURCES)]['id'],
                      action='Choose a familiar moment in your morning. Pause before starting the next task and name one thing you would like to give your attention to. Write one sentence, or say it quietly. Keep the activity within the time you chose.',
                      reflection='What felt most useful about pausing before the next task?',
                      adaptation='If writing feels tiring, say your answer quietly. One sentence is enough.')
                 for i in range(1, 15)],
    }


def maximum_plan():
    data = sample_plan()
    for day in data['plan']:
        for key, count in [('teaching', 150), ('why', 70), ('action', 90), ('reflection', 25), ('adaptation', 50)]:
            words = day[key].split()
            day[key] = ' '.join((words * 20)[:count]) + '.'
        day['title'] = 'A thoughtful conversation about the responsibilities and relationships that deserve your attention during this particular season of life'
    return data


class PlanPDFTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = sample_plan()
        cls.pdf = plan_pdf(cls.data)

    def test_exact_seventeen_pages_and_day_order(self):
        with fitz.open(stream=self.pdf, filetype='pdf') as pdf:
            self.assertEqual(len(pdf), 17)
            self.assertIn('Alex Morgan', pdf[0].get_text())
            self.assertIn('How to Use These Pages', pdf[1].get_text())
            for day in range(1, 15):
                text = pdf[day+1].get_text()
                self.assertIn(f'DAY {day:02d} OF 14', text)
                self.assertIn(f'A Thoughtful Beginning {day}', text)
            page17 = pdf[16].get_text()
            self.assertIn('A PASTORAL BLESSING FROM RABBI DAVID', page17)
            self.assertIn('Alex Morgan', page17)
            self.assertIn('Rabbi David', page17)
            self.assertIn('Rav David ben-Avraham', page17)
            self.assertIn('Jerusalem', page17)
            self.assertIn('May peace and blessing rest upon the work of your hands', page17)
            full_text = ''.join(p.get_text() for p in pdf)
            self.assertNotIn('Sources & the Modern Exercises', full_text)
            self.assertNotIn('Prepared with AI assistance', full_text)

    def test_text_stays_inside_page_and_readable(self):
        with fitz.open(stream=self.pdf, filetype='pdf') as pdf:
            for page in pdf:
                for block in page.get_text('dict')['blocks']:
                    for line in block.get('lines', []):
                        for span in line['spans']:
                            x0, y0, x1, y1 = span['bbox']
                            self.assertGreaterEqual(x0, 50)
                            self.assertLessEqual(x1, page.rect.width-49)
                            self.assertGreaterEqual(y0, 15)
                            self.assertLessEqual(y1, page.rect.height-20)
                            if 110 < y0 < 720 and len(span['text']) > 80:
                                self.assertGreaterEqual(span['size'], 11)

    def test_sources_are_real_library_entries_not_model_urls(self):
        data = deepcopy(self.data)
        data['plan'][0]['source_id'] = 'made_up_source'
        data['plan'][0]['source_url'] = 'https://invented.example/claim'
        with fitz.open(stream=plan_pdf(data), filetype='pdf') as pdf:
            combined = ''.join(page.get_text() for page in pdf)
            self.assertNotIn('invented.example', combined)
            self.assertNotIn('made_up_source', combined)
            self.assertIn('No verified source reference', pdf[2].get_text())
            self.assertIn(SOURCES[1]['title'], pdf[3].get_text())

    def test_legacy_plan_preserved_and_honestly_labelled(self):
        data = deepcopy(self.data)
        for day in data['plan']:
            for key in ['teaching', 'why', 'source_id']:
                day.pop(key)
        with fitz.open(stream=plan_pdf(data), filetype='pdf') as pdf:
            self.assertEqual(len(pdf), 17)
            self.assertIn('SAVED EARLIER EDITION', pdf[0].get_text())
            self.assertIn(data['plan'][0]['action'][:35], pdf[2].get_text())
            self.assertIn('ABOUT THIS SAVED EDITION', pdf[2].get_text())
            self.assertIn('Rabbi David', pdf[16].get_text())

    def test_new_guided_fallback_is_not_labelled_as_an_older_saved_plan(self):
        data=deepcopy(self.data)
        data['plan_source']='guided'
        for day in data['plan']:
            for key in ['teaching','why','source_id']:day.pop(key)
        with fitz.open(stream=plan_pdf(data),filetype='pdf') as pdf:
            self.assertEqual(len(pdf),17)
            self.assertIn('GUIDED EDITION',pdf[0].get_text())
            self.assertNotIn('SAVED EARLIER EDITION',pdf[0].get_text())
            self.assertIn('A GUIDED PRACTICE',pdf[2].get_text())

    def test_wrong_day_count_and_oversized_content_fail_explicitly(self):
        data = deepcopy(self.data)
        data['plan'].pop()
        with self.assertRaisesRegex(ValueError, 'fourteen ordered days'):
            plan_pdf(data)

    def test_realistic_maximum_provider_word_counts_fit_seventeen_pages(self):
        with fitz.open(stream=plan_pdf(maximum_plan()), filetype='pdf') as pdf:
            self.assertEqual(len(pdf), 17)
            for page in list(pdf)[2:16]:
                text = page.get_text()
                self.assertIn('MAKE IT WORK FOR YOU', text)
                for block in page.get_text('dict')['blocks']:
                    for line in block.get('lines', []):
                        for span in line['spans']:
                            self.assertGreaterEqual(span['bbox'][0], 50)
                            self.assertLessEqual(span['bbox'][2], page.rect.width-49)
                            self.assertLessEqual(span['bbox'][3], page.rect.height-20)
                            if 110 < span['bbox'][1] < 750 and len(span['text']) > 60:
                                self.assertGreaterEqual(span['size'], 11)
        data = deepcopy(self.data)
        data['plan'][0]['teaching'] = 'Very long content. ' * 2000
        with self.assertRaisesRegex(ValueError, 'exceeds its readable page area'):
            plan_pdf(data)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] in ('--fixture', '--max-fixture'):
        destination = Path(sys.argv[2])
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(plan_pdf(maximum_plan() if sys.argv[1] == '--max-fixture' else sample_plan()))
        print(str(destination.resolve()))
    else:
        unittest.main()
