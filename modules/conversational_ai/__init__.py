"""
Conversational AI Layer

Provides a chat interface where users can interrogate economic data with
context-aware follow-ups. Leverages the existing AI narrative infrastructure
and data gathering capabilities.
"""

from .chat_engine import ChatEngine

__all__ = ['ChatEngine']
