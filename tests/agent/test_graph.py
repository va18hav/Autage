from services.agent.graph import runbooks_router

def test_runbooks_router_branching():
    assert runbooks_router({"runbooks_needed": True}) == "refer_runbooks"
    assert runbooks_router({"runbooks_needed": False}) == "recommended_steps"
    assert runbooks_router({}) == "recommended_steps"
