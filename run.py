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


if __name__ == "__main__":
    typer.run(execute)
