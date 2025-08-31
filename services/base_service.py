from telegram import Update
from telegram.ext import ContextTypes

class BaseService:
    """
    Abstract base class for all download services.
    Each new service must inherit from this class and implement its methods.
    """
    async def can_handle(self, url: str) -> bool:
        """Checks if this service can process the given URL."""
        raise NotImplementedError("This method must be implemented by a subclass.")

    async def process(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        """Processes the user's request and presents download options."""
        raise NotImplementedError("This method must be implemented by a subclass.")