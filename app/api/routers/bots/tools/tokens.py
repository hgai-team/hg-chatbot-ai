import tiktoken
encoding = tiktoken.get_encoding("cl100k_base")

async def count_text_tokens(text: str):
    """
    Tokenizes the input text using tiktoken and returns the token count.
    """
    token_ids = encoding.encode(text)
    return {"token_count": len(token_ids)}
