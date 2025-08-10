import os
from dotenv import load_dotenv
from openai import OpenAI

class GPT5Client:
    def __init__(self):
        # Load .env variables
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise ValueError("Missing OPENAI_API_KEY in .env file")

        # Initialize OpenAI client
        self.client = OpenAI(api_key=api_key)


        self.systemPrompt="""


        """
     

    def chat(self, messages):
        pass

    