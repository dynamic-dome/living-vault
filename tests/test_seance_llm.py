from living_vault.apps.seance_ui.llm import respond, FakeLLM


def test_fake_llm_echo():
    llm = FakeLLM()
    out = llm.respond(system="be a page", history=[("user", "hi")])
    assert "echo" in out.lower() or "be a page" in out


def test_respond_uses_supplied_llm():
    llm = FakeLLM()
    text = respond(llm, system="sys", history=[("user", "hello")])
    assert isinstance(text, str)
