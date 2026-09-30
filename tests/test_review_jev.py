import unittest
from scripts.review_jev import MODEL, QUESTIONS, CRITERIA, cache_key, validate_response


def response():
    return {"model": MODEL, "answers": {q: {"type": "choice", "choice": "unclear", "confidence": 0.5,
            "probabilities": {c: 1.0 if c == "unclear" else 0.0 for c in CRITERIA}} for q in QUESTIONS},
            "usage": {"input_tokens": 100, "output_tokens": 20}}


class JevReviewTests(unittest.TestCase):
    def test_valid_response(self):
        validate_response(response())

    def test_rejects_invalid_probability(self):
        result = response()
        result['answers']['authors']['probabilities']['unclear'] = float('nan')
        with self.assertRaises(ValueError):
            validate_response(result)

    def test_rejects_missing_comparator_and_model(self):
        for field in ('model', 'answers'):
            result = response()
            del result[field]
            with self.assertRaises(ValueError):
                validate_response(result)

    def test_cache_changes_with_source_and_question(self):
        key = cache_key({'pdf_sha256': 'one'}, {'question': 'v1'})
        self.assertEqual(key, cache_key({'pdf_sha256': 'one'}, {'question': 'v1'}))
        self.assertNotEqual(key, cache_key({'pdf_sha256': 'two'}, {'question': 'v1'}))
        self.assertNotEqual(key, cache_key({'pdf_sha256': 'one'}, {'question': 'v2'}))


if __name__ == '__main__':
    unittest.main()
