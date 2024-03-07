from typing import List, Tuple

import typer
from playwright.sync_api import sync_playwright
from typing_extensions import Annotated

from core.data_models import Input
from core.scrape import run

app = typer.Typer()


@app.command()
def execute(
    search_term: Annotated[
        str, typer.Argument(default=..., help="Hotel/Place to seach on Google")
    ],
    sort_by: Annotated[
        str,
        typer.Argument(
            help="Sort google review by most_helpful, most_recent, highest_score or lowest_score",
            rich_help_panel="Secondary Arguments",
        ),
    ] = "most_recent",
    n_reviews: Annotated[
        int,
        typer.Argument(
            help="Number of reviews to scrape from the top. -1 means scrape all. The reviews will be scraped according to the 'sort_by' option",
            rich_help_panel="Secondary Arguments",
        ),
    ] = -1,
    stop_criteria_username: Annotated[
        str,
        typer.Option(
            help="username of the review. Stop further scraping when review of this username is found",
            rich_help_panel="Secondary Arguments",
        ),
    ] = None,
    stop_criteria_review: Annotated[
        str,
        typer.Option(
            help="Review text to find. Stop further scraping when given username and review is found",
            rich_help_panel="Secondary Arguments",
        ),
    ] = None,
    save_review_to_disk: Annotated[
        bool,
        typer.Argument(
            help="Whehter to save reviews on the local disk or not",
            rich_help_panel="Secondary Arguments",
        ),
    ] = True,
    save_metadata_to_disk: Annotated[
        bool,
        typer.Argument(
            help="Whehter to overall rating and metadata on the local disk or not",
            rich_help_panel="Secondary Arguments",
        ),
    ] = True,
):
    input_params = {
        "search_term": search_term,
        "sort_by": sort_by,
        "n_reviews": n_reviews,
        "save_review_to_disk": save_review_to_disk,
        "save_metadata_to_disk": save_metadata_to_disk,
    }

    if stop_criteria_username:
        stop = {"username": stop_criteria_username}

        if stop_criteria_review:
            stop["review_text"] = stop_criteria_review

        input_params["stop_critera"] = stop

    input_params = Input(**input_params)
    with sync_playwright() as playwright:
        ls_reviews = run(playwright, input_params)
        print(f"Scrapping Complete: Total Reviews  {len(ls_reviews)}")


def run_as_module(
    search_term: str,
    sort_by: str,
    n_reviews: int,
    save_to_disk: bool,
    stop_cri_user: str = "",
    stop_cri_review: str = "",
) -> Tuple[List[dict], dict]:
    """To run the scrapper as module by third party code

    Args:
        search_term: Term to search on google
        sort_by: sort the reviews by  [most_helpful, most_recent, highest_score or lowest_score]
        n_reviews: Number of reviews to scrape from the top. -1 means scrape all. The reviews will be scraped according to the 'sort_by' option
        save_to_disk: Whether to save both metadata and reviews to disk
    """
    ls_res: List[dict] = []
    overall_rating: dict = {}

    input_params = {
        "search_term": search_term,
        "sort_by": sort_by,
        "n_reviews": n_reviews,
        "save_review_to_disk": True if save_to_disk else False,
        "save_metadata_to_disk": True if save_to_disk else False,
    }

    if stop_cri_user:
        stop = {"username": stop_cri_user}

        if stop_cri_review:
            stop["review_text"] = stop_cri_review

        input_params["stop_critera"] = stop

    input_params = Input(**input_params)
    with sync_playwright() as playwright:
        ls_res, overall_rating = run(playwright, input_params)
        print(f"Scrapping Complete: Total Reviews  {len(ls_res)}")

    return ls_res, overall_rating


if __name__ == "__main__":
    typer.run(execute)
