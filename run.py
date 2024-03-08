from typing import List, Tuple

import typer
from playwright.sync_api import sync_playwright
from typing_extensions import Annotated

from core.data_models import Input
from core.scrape import execute_search_term_on_google, execute_visit_google_url

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

    input_obj = Input(**input_params)
    ls_reviews = [] 
    overall_rating = {}
    with sync_playwright() as playwright:
        ls_reviews, overall_rating = execute_search_term_on_google(playwright, input_obj)
        print(f"Scrapping Complete: Total Reviews  {len(ls_reviews)}")


def run_as_module(
    google_page_url: str = "",
    search_term: str = "",
    sort_by: str = "most_recent",
    n_reviews: int = -1,
    save_to_disk: bool = True,
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
    if not len(google_page_url) and not len(search_term):
        raise Exception(
            "Pass atleast one argument from 'google_page_url' and 'search_term' "
        )

    input_params = {
        "sort_by": sort_by,
        "n_reviews": n_reviews,
        "save_review_to_disk": True if save_to_disk else False,
        "save_metadata_to_disk": True if save_to_disk else False,
    }
    if len(search_term):
        print("Google Search Term Received")
        input_params["search_term"] = search_term
    else:
        print("Google Page Url Received")
        input_params["google_page_url"] = google_page_url

    if stop_cri_user:
        stop = {"username": stop_cri_user}

        if stop_cri_review:
            stop["review_text"] = stop_cri_review

        input_params["stop_critera"] = stop

    input_obj = Input(**input_params)
    with sync_playwright() as playwright:
        if len(search_term):
            print("Calling execute_search_term_on_google")
            ls_res, overall_rating = execute_search_term_on_google(
                playwright, input_obj
            )
        else:
            print("Calling execute_visit_google_url")
            ls_res, overall_rating = execute_visit_google_url(playwright, input_obj)

        print(f"Scrapping Complete: Total Reviews  {len(ls_res)}")

    return ls_res, overall_rating


if __name__ == "__main__":
    typer.run(execute)
    # run_as_module(
    #     google_page_url="https://www.google.com/travel/search?q=all%20hotels%20in%20doha%2C%20qatar&g2lb=2502548%2C2503771%2C2503781%2C2504375%2C4258168%2C4284970%2C4291517%2C4597339%2C4814050%2C4874190%2C4893075%2C4924070%2C4965990%2C4969802%2C10207535%2C10208620%2C72277293%2C72298667%2C72302247%2C72313836%2C72317059%2C72406588%2C72412680%2C72414906%2C72421566%2C72430562%2C72440516%2C72442338%2C72458707%2C72466827%2C72470899%2C72471395&hl=en-PK&gl=pk&ssta=1&ts=CAESCgoCCAMKAggDEAAaTQovEi0yJTB4M2U0NWM1MzRmZmRjZTg3ZjoweDQ0ZDkzMTlmNzhjZmQ0YjE6BERvaGESGhIUCgcI6A8QARgOEgcI6A8QARgPGAEyAhAAKgcKBToDUEtS&qs=CAESBENEWT0yJkNoZ0k0cGF4MlBlQm9mYThBUm9MTDJjdk1YUm9jemQwZW1NUUFROAZCCQkJr3mcvWa-gEIJCc1CagK22cKNQgkJgGr6UZAGJfNIAA&ap=MAFoAQ&ictx=1&sa=X&ved=0CMcBEMr3BGoXChMIqMjUmsrTgwMVAAAAAB0AAAAAEEw",
    # )
