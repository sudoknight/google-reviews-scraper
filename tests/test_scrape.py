import pytest
import scrape
from datetime import datetime
from dateutil.relativedelta import relativedelta


@pytest.mark.parametrize(
    "str_date, expected_result",
    [
        ["just now", datetime.now().strftime("%m-%d-%Y %H:%M")],
        [
            "a minute ago",
            (datetime.now() - relativedelta(**{"minutes": 1})).strftime(
                "%m-%d-%Y %H:%M"
            ),
        ],
        [
            "an hour ago",
            (datetime.now() - relativedelta(**{"hours": 1})).strftime("%m-%d-%Y %H:%M"),
        ],
        [
            "a day ago",
            (datetime.now() - relativedelta(**{"days": 1})).strftime("%m-%d-%Y %H:%M"),
        ],
        [
            "a week ago",
            (datetime.now() - relativedelta(**{"weeks": 1})).strftime("%m-%d-%Y %H:%M"),
        ],
        [
            "a month ago",
            (datetime.now() - relativedelta(**{"months": 1})).strftime(
                "%m-%d-%Y %H:%M"
            ),
        ],
        [
            "a year ago",
            (datetime.now() - relativedelta(**{"years": 1})).strftime("%m-%d-%Y %H:%M"),
        ],
        [
            "2 minutes ago",
            (datetime.now() - relativedelta(**{"minutes": 2})).strftime(
                "%m-%d-%Y %H:%M"
            ),
        ],
        [
            "3 hours ago",
            (datetime.now() - relativedelta(**{"hours": 3})).strftime("%m-%d-%Y %H:%M"),
        ],
        [
            "2 days ago",
            (datetime.now() - relativedelta(**{"days": 2})).strftime("%m-%d-%Y %H:%M"),
        ],
        [
            "2 weeks ago",
            (datetime.now() - relativedelta(**{"weeks": 2})).strftime("%m-%d-%Y %H:%M"),
        ],
        [
            "5 months ago",
            (datetime.now() - relativedelta(**{"months": 5})).strftime(
                "%m-%d-%Y %H:%M"
            ),
        ],
        [
            "6 years ago",
            (datetime.now() - relativedelta(**{"years": 6})).strftime("%m-%d-%Y %H:%M"),
        ],
    ],
)
def test_transform_date(str_date: str, expected_result: str):
    """Comapre the timestamps without the "Seconds" so that execution time does not make the tests fail."""
    dt = datetime.strptime(
        scrape.transform_date(str_date), "%m-%d-%Y %H:%M:%S"
    )  # convert string to datetime object
    dt = dt.strftime("%m-%d-%Y %H:%M")  # convert datetime object to requried format
    assert dt == expected_result
