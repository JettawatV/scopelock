"""ADK application package discovered by ``adk web .``, ``adk run app``, and ``adk eval``."""

# ``adk eval`` loads this file as a synthetic module named ``agent``. Import the
# canonical ``app`` package in that case so Agent objects are constructed once.
if __name__ == "app":
    from . import agent as agent
else:
    import app as _canonical_app

    agent = _canonical_app.agent
    app = _canonical_app.agent.app
    root_agent = _canonical_app.agent.root_agent
