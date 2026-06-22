from tool_parsing import parse_tool_calls, strip_tool_calls


def test_parsea_una_llamada():
    txt = '<tool_call>\n{"name": "comparar", "arguments": {"refs": ["intel 125U", "amd 340"]}}\n</tool_call>'
    calls = parse_tool_calls(txt)
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "comparar"
    assert '"refs"' in calls[0]["function"]["arguments"]


def test_sin_llamada_devuelve_none():
    assert parse_tool_calls("El 125U tiene 8 nucleos.") is None


def test_varias_llamadas():
    txt = ('<tool_call>{"name":"a","arguments":{}}</tool_call>'
           '<tool_call>{"name":"b","arguments":{}}</tool_call>')
    assert len(parse_tool_calls(txt)) == 2


def test_strip_deja_solo_texto():
    txt = 'hola <tool_call>{"name":"a","arguments":{}}</tool_call> mundo'
    assert strip_tool_calls(txt) == "hola  mundo".strip()
