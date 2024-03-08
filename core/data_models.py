from typing import Literal, Optional

from pydantic import BaseModel, Field


class StopCritera(BaseModel):
    username: str = Field(..., min_length=1)
    review_text: str


class Input(BaseModel):
    place_name: str = Field(..., min_length=2)
    google_page_url: str = Field(min_length=10, default="")

    sort_by: Optional[
        Literal["most_helpful", "most_recent", "highest_score", "lowest_score"]
    ] = "most_helpful"
    n_reviews: int = -1
    stop_critera: Optional[StopCritera] = None

    save_review_to_disk: bool = True
    save_metadata_to_disk: bool = True


# TODO: Add config model
