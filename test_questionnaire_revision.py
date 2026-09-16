"""Saved-answer compatibility and provider grounding for the revised questionnaire."""
import unittest

from content import BRANCHES, LEGACY_MONEY_FOCUS, route
from providers import _answer_record


class QuestionnaireRevisionTests(unittest.TestCase):
    def test_saved_money_answers_keep_their_original_meaning(self):
        for option in LEGACY_MONEY_FOCUS['options']:
            with self.subTest(value=option['value']):
                answers = {'goal': 'calm', 'focus': option['value']}
                question = next(q for q in route(answers) if q['id'] == 'focus')
                record = next(q for q in _answer_record(answers) if q['id'] == 'focus')
                self.assertEqual(question['title'], LEGACY_MONEY_FOCUS['title'])
                self.assertEqual(record['answer'], option['label'])

    def test_new_concerns_reach_the_provider_as_meaningful_labels(self):
        for option in BRANCHES['calm'][0]['options']:
            with self.subTest(value=option['value']):
                answers = {'goal': 'calm', 'focus': option['value']}
                record = next(q for q in _answer_record(answers) if q['id'] == 'focus')
                self.assertEqual(record['question'], BRANCHES['calm'][0]['title'])
                self.assertEqual(record['answer'], option['label'])

    def test_all_paths_keep_unique_questions_and_conditional_no_cost_choice(self):
        for goal in BRANCHES:
            for obstacle in ('none', 'cost'):
                with self.subTest(goal=goal, obstacle=obstacle):
                    questions = route({'goal': goal, 'obstacle': obstacle})
                    ids = [q['id'] for q in questions]
                    self.assertEqual(len(ids), len(set(ids)))
                    self.assertEqual(len(ids), 12 if obstacle == 'cost' else 11)
                    self.assertEqual('no_cost' in ids, obstacle == 'cost')
                    self.assertEqual(ids[-1], 'note')
                    for q in questions:
                        values = [o['value'] for o in q.get('options', [])]
                        self.assertEqual(len(values), len(set(values)))

    def test_uncertain_experience_is_not_relabelled_as_a_past_success(self):
        record = next(q for q in _answer_record({'experience': 'unsure'}) if q['id'] == 'experience')
        self.assertEqual(record['answer'], 'I am not sure what helps yet')


if __name__ == '__main__':
    unittest.main()
