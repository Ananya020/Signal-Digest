from pydantic import BaseModel


class WatchlistCreate(BaseModel):
    name: str


class WatchlistItemCreate(BaseModel):
    ticker: str


class AckRequest(BaseModel):
    flag_ids: list[int]
