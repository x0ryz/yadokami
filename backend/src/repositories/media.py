from src.models import MediaFile
from src.repositories.base import BaseRepository


class MediaRepository(BaseRepository[MediaFile]):
    def __init__(self, session):
        super().__init__(session, MediaFile)

    async def create(self, auto_flush: bool = False, **kwargs) -> MediaFile:
        media_entry = MediaFile(**kwargs)
        self.session.add(media_entry)

        if auto_flush:
            await self.session.flush()
            await self.session.refresh(media_entry)

        return media_entry
