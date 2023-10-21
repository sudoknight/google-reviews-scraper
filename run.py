import typer
from scrape import run
from typing_extensions import Annotated
from playwright.sync_api import sync_playwright

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
    with sync_playwright() as playwright:
        ls_reviews = run(
            playwright,
            search_term=search_term,
            sort_by=sort_by,
            n_reviews=n_reviews,
            save_review_to_disk=save_review_to_disk,
            save_metadata_to_disk=save_metadata_to_disk,
        )
        print(f"Scrapping Complete: Total Reviews  {len(ls_reviews)}")


if __name__ == "__main__":
    typer.run(execute)
