import unittest


class LLMServiceTest(unittest.TestCase):
    def test_extract_dashscope_stream_text_from_message_response(self) -> None:
        from app.services.llm_service import LLMService

        response = {
            "output": {
                "choices": [
                    {
                        "message": {
                            "content": "增量文字",
                        }
                    }
                ]
            }
        }

        self.assertEqual("增量文字", LLMService.extract_dashscope_text(response))

    def test_extract_dashscope_stream_text_from_text_response(self) -> None:
        from app.services.llm_service import LLMService

        response = {
            "output": {
                "text": "另一段增量文字",
            }
        }

        self.assertEqual("另一段增量文字", LLMService.extract_dashscope_text(response))


if __name__ == "__main__":
    unittest.main()
