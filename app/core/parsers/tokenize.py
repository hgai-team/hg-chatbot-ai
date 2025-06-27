import re

async def tiktokenize(text: str) -> list[str]:
    import tiktoken

    encoding = tiktoken.get_encoding("cl100k_base")

    token_ids = encoding.encode(text)

    tokens: list[str] = []
    for tid in token_ids:
        try:
            token_str = encoding.decode_single_token_str(tid)
        except AttributeError:
            token_str = encoding.decode([tid])
        tokens.append(token_str)

    return tokens

def simple_tokenize(text: str) -> list[str]:
    pattern = re.compile(r'\s+|\w+|[^\w\s]', flags=re.UNICODE)
    return pattern.findall(text)
