"""
Command handler'ları için modül.
"""

from .coffee_handler import setup_coffee_handlers
from .poll_handler import setup_poll_handlers
from .feedback_handler import setup_feedback_handlers
from .knowledge_handler import setup_knowledge_handlers
from .profile_handler import setup_profile_handlers
from .health_handler import setup_health_handlers

__all__ = [
    'setup_coffee_handlers',
    'setup_poll_handlers',
    'setup_feedback_handlers',
    'setup_knowledge_handlers',
    'setup_profile_handlers',
    'setup_health_handlers',
]
