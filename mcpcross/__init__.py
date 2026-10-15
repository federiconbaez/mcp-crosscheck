"""mcp-crosscheck: black-box cross-validation of the four mcp-family servers (stdlib only).

It launches every server as a real subprocess (stdio and HTTP), runs one shared conformance battery against all of them,
compares their answers to identical malformed inputs, and exercises tokens minted by one server against the others in three
layers. Nothing in here imports the servers' code: the only coupling is their command lines and their documented behaviour.
"""

__version__ = "1.0.0"
