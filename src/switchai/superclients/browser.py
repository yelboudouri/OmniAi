from typing import List, Optional, Generator, Union, Type

import httpx
from pydantic import BaseModel

from .. import SwitchAI
from ..base_client import BaseClient
from ..types import ChatResponse, ChatChoice


def fetch_website(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    }
    try:
        with httpx.Client() as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()

            return str(response.content)
    except httpx.RequestError as e:
        return f"An error occurred while requesting {e.request.url!r}: {e}"
    except httpx.HTTPStatusError as e:
        return f"Error response {e.response.status_code} while requesting {e.request.url!r}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"


class Browser(BaseClient):
    """
    A superclient that extends a chat SwitchAI client to support websites fetching and analysis.

    Args:
        client: A SwitchAI client initialized with a chat model.
    """

    def __init__(self, client: SwitchAI):
        if client.model_category != "chat":
            raise ValueError("The browser client only supports chat models.")

        self.client = client

    def chat(
        self,
        messages: List[str | ChatChoice | dict],
        temperature: Optional[float] = 1.0,
        max_tokens: Optional[int] = None,
        n: Optional[int] = 1,
        tools: Optional[List] = None,
        response_format: Optional[Type[BaseModel]] = None,
        stream: Optional[bool] = False,
    ) -> Union[ChatResponse, Generator[ChatResponse, None, None]]:
        if tools is None:
            tools = []
        if len(tools) > 0:
            raise ValueError("The browser client does allow tools to be passed in the chat method.")

        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "get_website",
                    "description": "Get the content of a website.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "The URL of the website to get."},
                        },
                    },
                },
            }
        )

        first_response = self.client.chat(messages, temperature, max_tokens, n, tools)

        tool_calls = first_response.choices[0].tool_calls
        if tool_calls:
            messages.append(first_response.choices[0])
            for tool_call in tool_calls:
                if tool_call.function.name == "get_website":
                    function_args = tool_call.function.arguments
                    web_page = fetch_website(**function_args)
                    messages.append(
                        {
                            "role": "tool",
                            "content": web_page,
                            "tool_call_id": tool_call.id,
                            "tool_name": tool_call.function.name,
                        }
                    )

            return self.client.chat(messages, temperature, max_tokens, n)

        return first_response
