"""
不使用记忆，可以选择此模块
"""

from ..base import MemoryProviderBase, logger
from config.manage_api_client import save_intimacy
TAG = __name__


class MemoryProvider(MemoryProviderBase):
    def __init__(self, config, summary_memory=None):
        self.intimacy = None
        self.intimacyRate = None
        self.intimacyRule = None
        if(config.get("intimacy") is not None and config.get("intimacy") != ""):
            self.intimacy = config.get("intimacy")
        if(config.get("intimacyRate") is not None and config.get("intimacyRate") != ""):
            self.intimacyRate = config.get("intimacyRate")
        if(config.get("intimacyRule") is not None and config.get("intimacyRule") != ""):
            self.intimacyRule = config.get("intimacyRule")
        super().__init__(config)

    async def save_memory(self, msgs):
        logger.bind(tag=TAG).debug("nomem mode: No memory saving is performed.")
        if self.intimacyRule is not None:
            await save_intimacy(self.role_id, self.intimacy,self.intimacyRate)
        return None

    async def query_memory(self, query: str) -> str:
        logger.bind(tag=TAG).debug("nomem mode: No memory query is performed.")
        return ""
