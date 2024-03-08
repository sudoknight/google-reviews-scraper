import csv
import logging
import math
import os
import pickle
import re
import time
import traceback
from datetime import datetime
from typing import List, Tuple, Union

import beepy
import yaml
from dateutil.relativedelta import relativedelta
from playwright.sync_api import Locator, Page, Playwright, expect

from core.data_models import Input, StopCritera
from core.utils.playwright import is_the_element_visible

DT = str(datetime.now())
LOCAL_OUTPUT_PATH = "{output_dir}/{entity_name}_" + DT


def load_config():
    """Loads config.yml containing output directory and stop_critera (where to stop scrolling)"""
    global LOCAL_OUTPUT_PATH
    try:
        with open("config.yml", "r") as file:
            config = yaml.safe_load(file)
            LOCAL_OUTPUT_PATH = LOCAL_OUTPUT_PATH.format(
                output_dir=config["output_dir"], entity_name="{entity_name}"
            )

            print("config.yml file loaded")
    except Exception as ex:
        tb = traceback.format_exc()
        print(f"Unable to use config.yml. {tb}")


def setup_logging():
    if not os.path.isdir("logs"):
        os.mkdir("logs")

    logging.basicConfig(
        filename=f"logs/{datetime.now()}.log",
        level=logging.DEBUG,
        format="%(asctime)s [%(filename)s] %(levelname)s: %(message)s",
    )


##########################################################
# ******** Utility and Parsing Methods ********
##########################################################


def _validate(text: str):
    """
    Removes multitples spaces and strips \n

    Args:
        element: Beautiful Soap element

    Returns:
        string text extracted from element
    """
    if text:
        text = re.sub(r"\s+", " ", text).strip(" \n")
        if len(text):
            return text

    return None


def transform_date(str_date: str) -> str:
    """Transforms the humanized date to datetime (str)

    for example:
    If datetime right now is 10-20-2023 15:27:33

        - just now   -->  10-20-2023 15:27:33

        - a minute ago  -->   10-20-2023 15:26:33
        - an hour ago
        - a day ago
        - a week ago
        - a month ago
        - a year ago

        - 2 minutes ago
        - 2 hours ago   -->   10-20-2023 13:27:38
        - 2 Days ago
        - 2 Weeks ago
        - 2 Months ago
        - 2 Years ago

    Args:
        str_date: string  containing humanize date

    Returns:
        datetime string
    """

    if "now" in str_date:
        return str(datetime.now().strftime("%m-%d-%Y %H:%M:%S"))

    re_plural = r"(\d+).*(minutes\b|hours\b|days\b|weeks\b|months\b|years\b)"
    re_singular = r"minute\b|hour\b|day\b|week\b|month\b|year\b"

    try:
        if re.search(re_plural, str_date):
            for match in re.findall(re_plural, str_date):
                # e.g ('2', 'minutes') 2 will be 'unit_value' and 'minutes' will be unit
                unit_value = int(match[0])
                unit = match[1]
                dt = datetime.now() - relativedelta(**{unit: unit_value})
                return dt.strftime("%m-%d-%Y %H:%M:%S")

        if re.search(re_singular, str_date):
            for unit in re.findall(re_singular, str_date):
                # relativedelta does not support singular to we append 's' with the unit here
                dt = datetime.now() - relativedelta(**{f"{unit}s": 1})
                return dt.strftime("%m-%d-%Y %H:%M:%S")

    except Exception as ex:
        logging.error(ex)

    return None


def save_local_files(
    entity_name: str,
    sort_by: str,
    entitiy_metadata: dict = None,
    ls_reviews: List[dict] = None,
):
    """save local csv files. It creates a direcotry based on "entity_name" and stores
    two csv files in it.

    - metadata.csv: containing metadata and rating and entity
    - reviews.csv: contains reviews

    Args:
        entity_name: Name of the entity/hotel/place currently being searched (used to name the directory)
        entitiy_metadata: dict containing overall rating info and name of entity
        sort_by: option by which data is sorted. Each sort_by option will have different file of reviews
        ls_reviews: scraped review objects

    """

    dir_path = LOCAL_OUTPUT_PATH.format(entity_name=entity_name)

    if not os.path.exists(dir_path) and (entitiy_metadata or ls_reviews):
        os.makedirs(dir_path)

    fname1 = f"{dir_path}/metadata.csv"
    fname2 = f"{dir_path}/reviews_{sort_by}.csv"

    if entitiy_metadata:
        with open(fname1, "w", newline="") as file:
            try:
                writer = csv.writer(file)
                writer.writerow(entitiy_metadata.keys())
                writer.writerow(entitiy_metadata.values())
                print(f"Saved File: {fname1}")

            except Exception as ex:
                logging.error(ex)
                pickle.dump(entitiy_metadata)

    if ls_reviews:
        write_header = True
        if os.path.exists(fname2):
            write_header = False

        with open(fname2, "a", newline="") as file:
            try:
                writer = csv.writer(file)
                if write_header:
                    writer.writerow(ls_reviews[0].keys())
                for row in ls_reviews:
                    writer.writerow(row.values())

            except Exception as ex:
                logging.error(ex)
                pickle.dump(entitiy_metadata)


def save_html(html: str, name: str = "", dir: str = None):
    """Save html file for debugging purpose"""
    try:
        path = None
        if dir:
            path = f"{dir}/{DT}_{name}.html"
        else:
            path = f"{DT}_{name}.html"

        with open(path, "w") as f:
            f.write(html)
    except Exception as ex:
        print("Saving html failed: ", ex)


##########################################################
# ******** Parsing Methods ********
##########################################################


def full_scrn_extract_overall_rating(page: Page) -> dict:
    """
    Extracts the overall rating (eg. 4.1 out of 5 star, 574 number of reviews)

    Args:
        page: Page object containing reviews broswer tab

    Returns:
        Overall ratting and number of reviews
    """

    rating = n_reviews = None
    xpath_rating = (
        "//div[contains(@aria-label, 'out of 5 stars from ') and @role='text']"
    )

    expect(page.locator(xpath_rating).first).to_be_attached(timeout=100000)
    if is_the_element_visible(
        page,
        xpath_rating,
        state="attached",
    ):
        # It will extract text like this: '3.6 out of 5 stars from 206 reviews'
        rating_locator = page.locator(f"xpath={xpath_rating}").first
        txt = rating_locator.get_attribute("aria-label")
        rating = float(txt.split(" out of ")[0])
        n_reviews = int(txt.split(" from ")[1].replace(" reviews", ""))

    get_star_rating = (
        lambda star: page.locator(
            f"//div[contains(@aria-label, '{star}-star reviews') and @role='text']"
        )
        .first.get_attribute("aria-label", timeout=50000)
        .split("-star reviews ")[1]
        .replace(" percent.", "")
    )

    return {
        "rating": rating,
        "no_of_reviews": n_reviews,
        "5-star": get_star_rating("5"),
        "4-star": get_star_rating("4"),
        "3-star": get_star_rating("3"),
        "2-star": get_star_rating("2"),
        "1-star": get_star_rating("1"),
    }


def dialog_box_extract_overall_rating(page: Page) -> dict:
    """Extracts the overall rating and number of reviews

    Args:
        page: Page object containing reviews broswer tab

    Returns:
        Overall ratting and number of reviews
    """

    xpath_rating = "xpath=//div[@class='review-dialog-top']//span[contains(@aria-label, ' out of 5')]"
    xpath_nreviews = "xpath=//div[@class='review-dialog-top']//span[contains(., 'reviews on Google')][not(.//span)]"
    expect(page.locator(xpath_rating).first).to_be_attached(timeout=100000)

    expect(page.locator(xpath_nreviews).first).to_be_attached(timeout=100000)

    rating = n_reviews = None
    locator_rating = page.locator(xpath_rating).first
    if locator_rating.is_visible():
        # It will extract text like this: "Rated 4.1 out of 5,"
        txt = locator_rating.get_attribute("aria-label")
        rating = float(txt.split(" out of ")[0].split(" ")[-1].strip())

    locator_nreviews = page.locator(xpath_nreviews).first
    if locator_nreviews.is_visible():
        # It will extract text like this: "50 reviews on Google"
        n_reviews = float(locator_nreviews.inner_text().split(" ")[0].strip())

    return {
        "rating": rating,
        "no_of_reviews": n_reviews,
    }


def full_scrn_parse_review_rating_tags(
    ls_text: list,
) -> dict:
    """Parses the review and extracts text and rating tags and manager/entity response.

    Args:
        text: review text that can contain both user feedback and rating tags

    Returns:
        dict containing review text, english and original version, rating tags
        owner response text and owner response time

    Example:
    =========
    "The hotel offers a rich and tasty breakfast buffet. The staff is extremely courteous
    and friendly. At the reception Samia was very helpful and super professional.
    Rooms
    4.0
    Service
    5.0
    Location
    3.0
    Hotel highlights
    Quiet · Kid-friendly · Great value
    +8
    Response from the owner
    10 hours ago
    Dear Nabil Q,
    Thank you for taking the time to share your positive feedback.
    We are delighted to learn that you had a wonderful stay and were pleased with the services provided by our team members.
    Your kind words serve as a great source of motivation for all of us as we strive to consistently deliver exceptional experiences.
    I wish to welcome you again soon.

    Kind Regards
    Ismail Tepe

    Front Office Manager
    "

    - The above example contains both user review text and rating tags.
    - There can be cases where there is only review text or only rating tags
    """

    full_review = rating_tags = en_lang_text = other_lang_text = owner_resp_time = (
        owner_resp_text
    ) = None

    ls_text = [item for item in ls_text if len(item) > 0]

    if ls_text:
        # Check for manager/entity response
        idx_owner = [
            idx
            for idx, ele in enumerate(ls_text)
            if "Response from the owner".lower() in ele.lower()
        ]
        # if "Response from the owner".lower() in text.lower():
        if idx_owner:
            idx_owner = idx_owner[
                0
            ]  # get the idx of the list, where the manager response starts
            ls_r = "\n".join(ls_text[idx_owner + 1 :]).strip("\n")
            ls_text = ls_text[:idx_owner]

            ls_r_text = ls_r.split("\n")
            owner_resp_time = transform_date(ls_r_text[0])
            owner_resp_text = " ".join(ls_r_text[1:])

    # There can be cases where the ls_text contains only response and no review text or rating tags
    # So at this stage the ls_text could be empty because the manager response has already been
    # extracted So therefore is necessary to check the length of the ls_text again
    if ls_text:
        ls_text[0] = ls_text[0].replace("\n", " ")

        # it contains both review text and rating tags
        if len(ls_text) > 1:
            if ls_text[0] not in [
                "Rooms",
                "Service",
                "Location",
                "Hotel highlights",
                "Nearby activities",
                "Safety",
                "Walkability",
                "Food & drinks",
                "Noteworthy details",
            ]:
                # It means the first item in the list is the review text

                full_review = ls_text[0]
                rating_tags = (
                    " ".join(ls_text[1:])
                    .replace(
                        ".0",
                        ".0,",
                    )
                    .strip()
                )

            # it only contains rating tags
            else:
                full_review = None
                rating_tags = (
                    " ".join(ls_text)
                    .replace(
                        ".0",
                        ".0,",
                    )
                    .strip()
                )

        # It only contains review text
        else:
            full_review = ls_text[0]
            rating_tags = None

    if full_review is not None:
        if "(Original)" in full_review:
            full_review_p2 = full_review.split("(Original)")
            en_lang_text = (
                full_review_p2[0].replace("(Translated by Google)", "").strip()
            )
            other_lang_text = full_review_p2[1]
        else:
            en_lang_text = full_review
            other_lang_text = None
            full_review = None

    return {
        "full_review": full_review,
        "rating_tags": rating_tags,
        "en_lang_text": en_lang_text,
        "other_lang_text": other_lang_text,
        "owner_resp_text": owner_resp_text,
        "owner_resp_time": owner_resp_time,
    }


def dialog_box_parse_review_rating_tags(text: str) -> Tuple[str, Union[str, None]]:
    """Seperates review text from the rating tags. If no rating tags are found
    original string is returned back

    Args:
        text: review text to process
    """

    # There can be cases when the last of word of text and the rating tag have no space b/w them
    # e.g. "Nice place you can rent for night or by monthRooms: 4/5  |  Service: 5/5  |  Location: 5/5"
    # So add one space before each rating tag

    text = text.replace("Rooms:", " Rooms:")
    text = text.replace("Service:", " Service:")
    text = text.replace("Location:", " Location:")
    text = text.replace("Hotel highlights:", " Hotel highlights:")
    text = text.replace("Nearby activities:", " Nearby activities:")
    text = text.replace("Safety:", " Safety:")
    text = text.replace("Walkability:", " Walkability:")
    text = text.replace("Food & drinks:", " Food & drinks:")
    text = text.replace("Noteworthy details:", " Noteworthy details:")

    pattern = re.compile(r"(\w+:\s[\d]/5)")
    match = pattern.search(text)  # Find the first match in the text

    # If it contains rating tags
    if match:
        # Get the matched substring
        split_substring = match.group(1)
        split_by = re.escape(split_substring)
        # Split the text based on the matched substring
        split_text = re.split(split_by, text, maxsplit=1)
        review, rating_tags = split_text[0], split_substring + split_text[1]
        return review, rating_tags

    return text, None


def full_scrn_parse_review_objs(
    stop_criteria: StopCritera,
    review_objs: Locator,
    scroll_iter_idx: int,
) -> Tuple[List[dict], bool, int]:
    """Parse the reviews objects in the current scroll window. Each scroll window has 10
    review objects unless we are in the last scroll window.

    Args:
        review_objs: Locator containing review objects
        scroll_iter_idx: current scroll window

    Returns:
        list of reviews in the current scroll window, True or False whether stop criteria is met or not
        count of google review (that are posted on google.com)
    """

    ls_reviews = []
    count_google_reviews = 0

    current_scroll_window: Locator = review_objs.locator(
        f"xpath=div[{scroll_iter_idx}]"
    ).first

    # Iterate and parse all the review objects in the current scroll window
    n_reviews = current_scroll_window.inner_text().count(
        "/5"
    ) + current_scroll_window.inner_text().count("/10")

    for idx_review in range(1, n_reviews + 1):
        try:
            current_review_obj: Locator = current_scroll_window.locator(
                f"xpath=div[{idx_review}]"
            ).first

            name = user_profile = rating = None

            # *************START: Review Posted on Google*************

            if current_review_obj.locator(
                "xpath=" + "div[1]/div/span/a"
            ).first.is_visible():
                # If the review is posted on google

                # name of review poster
                name = current_review_obj.locator(
                    "xpath=" + "div[1]/div/span/a"
                ).first.inner_text()

                # google profile of the reviewer
                user_profile = current_review_obj.locator(
                    "xpath=" + "div[1]/div/span/a"
                ).first.get_attribute("href")

                # overall rating out of 5
                rating = current_review_obj.locator(
                    "xpath="
                    + '//div[contains(., "/5")][not(.//div[contains(., "/5")])]'
                ).first.inner_text()

                # ************* --------END-------- *************

            else:
                # *************START: Review Posted on any other site*************

                # If the review is fetch from other website e.g priceline
                name = current_review_obj.locator(
                    "xpath=" + "div[1]/div/span/span[1]"
                ).first.inner_text()

                user_profile = None
                usre_profile_locator = current_review_obj.locator(
                    "xpath=" + "div[1]/div/span/span[2]/a"
                ).first
                if usre_profile_locator.is_visible():
                    user_profile = current_review_obj.locator(
                        "xpath=" + "div[1]/div/span/span[2]/a"
                    ).first.get_attribute("href")

                # overall rating out of 10
                rating = current_review_obj.locator(
                    "xpath="
                    + '//div[contains(., "/10")][not(.//div[contains(., "/10")])]'
                ).first.inner_text()

                # ************* --------END-------- *************

            # review text
            review_text: list = current_review_obj.locator(
                "xpath="
                + 'div[2]//span[normalize-space() != "Business" and normalize-space() != "Vacation" and normalize-space() != "Family" and normalize-space() != "Friends" and normalize-space() != "Couple" and normalize-space() != "Solo" and not(contains(., " ❘ ")) and not(contains(., "Read more")) and not(contains(., "Report review")) and not(.//svg) ][not(.//span/span)] | div[2]//p[not(contains(., " ❘ ")) and not(contains(., "Read more")) and not(contains(., "Report review")) and not(.//svg)][not(.//p/span)]'
            ).all_inner_texts()

            # parse the current review text which also contains room/service/location tags
            parsed_review_text: dict = full_scrn_parse_review_rating_tags(review_text)

            if stop_criteria is not None:
                target = current_review_obj.inner_text().lower()
                if (
                    stop_criteria.username.lower() in target
                    and stop_criteria.review_text.lower() in target
                ):
                    logging.info(f"Stopping critera met")
                    return ls_reviews, True, count_google_reviews

            # date when review was posted
            date = review_site = None
            dt_locator = current_review_obj.locator(
                "xpath="
                + "//span[contains(., 'ago on')][not(.//span[contains(., 'ago on')])]"
            ).first
            if dt_locator.is_visible(timeout=100):
                dt = dt_locator.inner_text()
                dt = dt.split("ago on")
                date = dt[0].strip()
                review_site = dt[1].strip()  # eg google agoda priceline
            else:
                dt_locator = current_review_obj.locator(
                    "xpath="
                    + "//span[contains(., ' ago')][not(.//span[contains(., ' ago')])]"
                ).first
                date = dt_locator.inner_text()

            if review_site:
                if review_site.lower().strip() == "google":
                    count_google_reviews += 1

            date1 = transform_date(date)

            # type of stay eg "Holiday ❘ Family"
            stay_type = None
            stay_type_locator = current_review_obj.locator(
                "xpath=" + "div[2]/div/span"
            ).first
            if stay_type_locator.is_visible(timeout=100):
                stay_type = stay_type_locator.inner_text(timeout=100)

            review_images = None
            path_review_imgs = "div[2]//img[contains(@alt, 'Photo')]"

            if current_review_obj.locator("xpath=" + path_review_imgs).first.is_visible(
                timeout=100
            ):
                ls_review_imgs = [
                    (
                        img.get_attribute("src")
                        if img.get_attribute("src")
                        else img.get_attribute("data-src")
                    )
                    for img in current_review_obj.locator(
                        "xpath=" + path_review_imgs
                    ).all()
                ]
                review_images = ", ".join(ls_review_imgs)

                # Setting the resolution of images to 800x800
                subst = "w800-h800"
                regex = r"w[\d]+-h[\d]+-k-no-p"
                res = re.sub(regex, subst, review_images, 0, re.MULTILINE)
                if res:
                    review_images = res

            rating, total_rating = rating.split("/")
            parsed_review_text.update(
                {
                    "username": name,
                    "user_profile": user_profile,
                    "date": date,
                    "review_post_date": date1,
                    "review_site": review_site,
                    "rating_score": rating,
                    "total_rating_score": total_rating,
                    "stay_type": stay_type,
                    "review_images": review_images,
                }
            )
            ls_reviews.append(parsed_review_text)
        except Exception as ex:
            tb = traceback.format_exc()
            logging.error(
                f"Unable to scrape review. Scroll window: {scroll_iter_idx}  Review_idx: {idx_review}\n{tb}"
            )

    return ls_reviews, False, count_google_reviews


def dialog_box_parse_review_objs(
    stop_criteria: StopCritera,
    review_objs: Locator,
    scroll_iter_idx: int,
) -> Tuple[List[dict], bool]:
    """Parse the reviews objects in the current scroll window. Each scroll window has 10
    review objects unless we are in the last scroll window.

    Args:
        review_objs: Locator containing review objects
        scroll_iter_idx: current scroll window

    Returns:
        list of reviews in the current scroll window, True or False whether stop criteria is met or not
        count of google review (that are posted on google.com)
    """

    # ***********************************************
    # *************START: Nested Method *************
    # ***********************************************

    def review_rating_stay_type(
        xpath_review_div: str, current_review_locator: Locator
    ) -> Tuple[str, str, str]:
        """Extracts the following from the review div
            - Stay type
            - Review text
            - rating tags

        Args:
            xpath_review_div: div containing the above three things

        Returns:
            stay_type, review, rating_tags
        """

        xpath_stay_type = xpath_review = None
        stay_type = review_text = rating_tags = None
        review_sections = current_review_locator.locator(
            f"{xpath_review_div}/div"
        ).all()

        try:
            # If it has three child divs
            # It means stay_type is present along with the review text

            if len(review_sections) > 2:
                if len(
                    current_review_locator.locator(
                        f"{xpath_review_div}/div[2]/span/span/span"
                    ).all()
                ):
                    xpath_review = f"{xpath_review_div}/div[2]/span/span/span"
                elif len(
                    current_review_locator.locator(
                        f"{xpath_review_div}/div[2]/span/span"
                    ).all()
                ):
                    xpath_review = f"{xpath_review_div}/div[2]/span/span"

                xpath_stay_type = f"{xpath_review_div}/div[1]"

            elif len(review_sections) > 1:
                # If div[1]/div[3]/div/div/ has two child divs
                # Either it only has review text and not stay_type
                # Or it has stay_type and not review text
                if len(
                    current_review_locator.locator(
                        f"{xpath_review_div}/div[1]/span/span/span"
                    ).all()
                ):
                    xpath_review = f"{xpath_review_div}/div[1]/span/span/span"

                elif len(
                    current_review_locator.locator(
                        f"{xpath_review_div}/div[1]/span/span"
                    ).all()
                ):
                    xpath_review = (
                        f"{xpath_review_div}/div[1]/span/span"  # to get review text
                    )
                else:
                    xpath_stay_type = f"{xpath_review_div}/div[1]"  # to get Stay type because review text is not found
                    xpath_review = None

            else:
                # There is no text in the review
                logging.info(
                    f"No review text found window: {scroll_iter_idx}  Idx: {idx_review}"
                )

            if xpath_stay_type:
                # type of stay eg "Holiday ❘ Family"
                stay_type = _validate(
                    current_review_locator.locator(xpath_stay_type).first.text_content()
                )

            if xpath_review:
                raw_review = current_review_locator.locator(
                    xpath_review
                ).first.text_content()

                # seperate review text from the rating tags
                review_text, rating_tags = dialog_box_parse_review_rating_tags(
                    raw_review
                )

                review_text = _validate(review_text)
                rating_tags = _validate(rating_tags)

        except Exception as ex:
            save_html(
                html=f"<!-- {ex} -->\n\n" + current_review_locator.inner_html(),
                name="FAILED_REVIEW",
                dir="logs",
            )

        return stay_type, review_text, rating_tags

    # *********************************************
    # *************End: Nested Method *************
    # *********************************************

    ls_reviews = []
    count_google_reviews = 0

    current_scroll_window: Locator = review_objs.locator(
        f"xpath=div[{scroll_iter_idx}]"
    ).first

    # Iterate and parse all the review objects in the current scroll window
    n_reviews = current_scroll_window.inner_text().count(
        "/5"
    ) + current_scroll_window.inner_text().count("/10")

    for idx_review in range(1, n_reviews + 1):
        try:
            # div with attribute @data-google-review-count
            current_review_obj: Locator = current_scroll_window.locator(
                f"xpath=div[@data-google-review-count]/div[{idx_review}]"
            ).first

            name = user_profile = rating = stay_type = en_lang_text = rating_tags = (
                other_lang_text
            ) = date = review_site = full_review = review_images = owner_resp_text = (
                owner_resp_time
            ) = None

            # *************START: Review Posted on Google*************

            if current_review_obj.locator("xpath=" + "div[1]").first.is_visible():
                # If the review is posted on google

                # name of review poster
                name = current_review_obj.locator(
                    "xpath=" + "div[1]/div/div/a"
                ).first.inner_text()

                # google profile of the reviewer
                user_profile = current_review_obj.locator(
                    "xpath=" + "div[1]/div/div/a"
                ).first.get_attribute("href")

                # overall rating out of 5
                rating = current_review_obj.locator(
                    "xpath=" + "div[1]/span"
                ).first.inner_text()

                # If div[1]/div[3]/div/div/ has three child divs
                # It means stay_type is present along with the review

                xpath_review_secs = "xpath=div[1]/div[3]/div/div[1]"
                stay_type, en_lang_text, rating_tags = review_rating_stay_type(
                    xpath_review_secs, current_review_obj
                )

                # Get the review in original language,
                xpath_review_secs2 = "xpath=div[1]/div[3]/div/div[2]"
                _, other_lang_text, _ = review_rating_stay_type(
                    xpath_review_secs2, current_review_obj
                )

                # date when review was posted
                dt_locator = current_review_obj.locator(
                    "xpath="
                    + "//span[contains(., 'ago on')][not(.//span[contains(., 'ago on')])]"
                ).first
                if dt_locator.is_visible(timeout=100):
                    dt = _validate(dt_locator.inner_text())
                    dt = dt.split("ago on")
                    date = dt[0].strip()
                    review_site = dt[1].strip()  # eg google agoda priceline
                else:
                    dt_locator = current_review_obj.locator(
                        "xpath="
                        + "//span[contains(., ' ago')][not(.//span[contains(., ' ago')])]"
                    ).first
                    date = _validate(dt_locator.inner_text())

                if review_site:
                    if review_site.lower().strip() == "google":
                        count_google_reviews += 1

                # When there are attached picture, The owner response is the
                # div[4] otherise its div[3]
                xpath_owner_response = None

                if current_review_obj.locator(
                    "xpath=div[2]/g-scrolling-carousel"
                ).first.is_visible():
                    ls_review_imgs = [
                        img.get_attribute("style")
                        .replace("background-image:url(", "")
                        .replace(")", "")
                        for img in current_review_obj.locator(
                            "xpath=div[2]/g-scrolling-carousel//div[@aria-label = 'Photos']"
                        ).all()
                        if img.get_attribute("style")
                    ]
                    review_images = ", ".join(ls_review_imgs)

                    # Setting the resolution of images to 800x800
                    subst = "w800-h800"
                    regex = r"w[\d]+-h[\d]+-p-n-k-no"
                    res = re.sub(regex, subst, review_images, 0, re.MULTILINE)
                    if res:
                        review_images = res

                    xpath_owner_response = "xpath=div[4]"

                else:
                    xpath_owner_response = "xpath=div[3]"

                # check if owner response is available
                xpath_owner_response = f"{xpath_owner_response}/div/div/div[1]"
                if current_review_obj.locator(xpath_owner_response).first.is_visible():
                    owner_resp_time = _validate(
                        current_review_obj.locator(
                            f"{xpath_owner_response}/div[1]"
                        ).first.text_content()
                    )
                    owner_resp_time = owner_resp_time.split("Response from the owner")[
                        -1
                    ].strip()

                    # Check response is expandable with "More"
                    if len(
                        current_review_obj.locator(
                            f"{xpath_owner_response}/div[2]/span[2]"
                        ).all()
                    ):
                        owner_resp_text = _validate(
                            current_review_obj.locator(
                                f"{xpath_owner_response}/div[2]/span[2]"
                            ).first.text_content()
                        )

                    else:  # Or it simply a short
                        owner_resp_text = _validate(
                            current_review_obj.locator(
                                f"{xpath_owner_response}/div[2]"
                            ).first.text_content()
                        )

                # ************* --------END-------- *************

            else:
                # *************START: Review Posted on any other site*************
                name = current_review_obj.locator(
                    "xpath=" + "a/div[1]/span[1]"
                ).first.inner_text()

                dt_locator = current_review_obj.locator(
                    "xpath=" + "a/div[1]/span[2]"
                ).first

                dt = _validate(dt_locator.inner_text())
                dt = dt.split("ago on")
                date = dt[0].strip()

                rating = current_review_obj.locator("xpath=a/span").first.text_content()
                rating = _validate(rating)

                en_lang_text = current_review_obj.locator(
                    "xpath=a/div[2]"
                ).first.text_content()
                other_lang_text = en_lang_text

                review_site = "other"
                # ************* --------END-------- *************

            date1 = transform_date(date)
            rating, total_rating = rating.split("/")

            if stop_criteria is not None:
                target = current_review_obj.inner_text().lower()
                if (
                    stop_criteria.username.lower() in target
                    and stop_criteria.review_text.lower() in target
                ):
                    logging.info(f"Stopping critera met")
                    return ls_reviews, True, count_google_reviews

            result_obj = {
                "full_review": full_review,
                "rating_tags": rating_tags,
                "en_lang_text": en_lang_text,
                "other_lang_text": other_lang_text,
                "owner_resp_text": owner_resp_text,
                "owner_resp_time": owner_resp_time,
                "username": name,
                "user_profile": user_profile,
                "date": date,
                "review_post_date": date1,
                "review_site": review_site,
                "rating_score": rating,
                "total_rating_score": total_rating,
                "stay_type": stay_type,
                "review_images": review_images,
            }

            ls_reviews.append(result_obj)

        except Exception as ex:
            tb = traceback.format_exc()
            logging.error(
                f"Unable to scrape review. Scroll window: {scroll_iter_idx}  Review_idx: {idx_review}\n{tb}"
            )

    return ls_reviews, False, count_google_reviews


def new_reviews_arrived(review_objs: Locator, scroll_iter_idx: int) -> bool:
    """Check the availability of new review by comparing the hash of the object with
    the previous hash value

    Args:
        review_objs: Locator containing review objects
        previous_hash: hash value of the previous locator objects

    Returns:
        in case of new review:  (True, new hash)  otherwise (False, previous hash value)
    """
    if is_the_element_visible(review_objs, f"div[{scroll_iter_idx}]", state="attached"):
        return True
    else:
        return False


##########################################################
# ******** Main Executable Method ********
##########################################################


def reviews_in_full_screen(
    page: Page, input_params: Input
) -> Tuple[List[dict], int, int, dict]:
    """When number of reviews are enough (e.g. more than 100) and they are opened in a new screen this
    method is used to scroll, scrape, and iterate on the reviews

    Args:
        page: page object containing the reviews
        input_params: input parameters for scraping from google

    Returns:
        list of reviews
    """

    overall_rating: dict = full_scrn_extract_overall_rating(page)

    if not overall_rating:
        logging.error("Hotel metadata not scraped")
        raise Exception("Hotel metadata not scraped")

    overall_rating["entity_name"] = input_params.place_name

    print(overall_rating)

    if input_params.save_metadata_to_disk:
        save_local_files(
            entity_name=input_params.place_name,
            sort_by="",
            entitiy_metadata=overall_rating,
        )

    # _ = input("overall_rating Extracted")

    page.wait_for_timeout(10000)

    # Select filter reviews by 'Google'. Discard reviews from other sources eg Tripadvisor
    xpath_review_src = '//div[@role="listbox" and @aria-expanded="false" and @aria-label="Review Source Options"]'
    if is_the_element_visible(page, xpath_review_src):
        page.locator(xpath_review_src).first.click()

        time.sleep(5)

        page.locator(
            '//div[@data-value="-1" and @aria-label="Google" and @role="option"]'
        ).first.click()

    # Click the "sort by" option

    page.locator(
        '//div[@role="listbox" and @aria-expanded="false" and @aria-label="Review Sort Options"]'
    ).first.click()

    time.sleep(5)

    if input_params.sort_by == "most_helpful":
        page.locator(
            '//div[@data-value="1" and @aria-selected="true" and @aria-label="Most helpful" and @role="option"]'
        ).first.click()

    elif input_params.sort_by == "most_recent":
        page.locator(
            '//div[@data-value="2" and @aria-selected="false" and @aria-label="Most recent" and @role="option"]'
        ).first.click()

    elif input_params.sort_by == "highest_score":
        page.locator(
            '//div[@data-value="3" and @aria-selected="false" and @aria-label="Highest score" and @role="option"]'
        ).first.click()

    elif input_params.sort_by == "lowest_score":
        page.locator(
            '//div[@data-value="4" and @aria-selected="false" and @aria-label="Lowest score" and @role="option"]'
        ).first.click()

    else:
        err = f"Invalid sort by option: {input_params.sort_by}. It must be any of these options: [most_helpful, most_recent, highest_score, lowest_score]"
        logging.error(err)
        raise Exception(err)

    # *** Scrolling reviews ***
    # End scrolling if any one of the two conditions are met
    # 1. It has reached the end of reviews
    # 2. Stoping criteria is met. We are not interested in getting the remaining past reviews are

    # every scroll iteration will add 10 more reviews on the page.
    # basically it adds a new div containing 10 where items each item is a review
    # unless the the end of the screen has been reached and the remaining reviews are less than 10

    count_google_reviews = 0
    count_all_reviews = 0

    # iter_idx_scroll = 1 because XPath typically uses a 1-based index for addressing elements in a node set.
    # That means the first element in a node set is referred to as element 1
    iter_idx_scroll = 1  # scroll iteration index
    ls_reviews = []  # list of scraped reviews
    total_review = overall_rating["no_of_reviews"]
    # divide by then because each div contains 10 review objects
    total_review_divs = math.ceil(total_review / 10)

    locator_review_objs = page.locator(
        '//c-wiz[@data-node-index="0;0" and @c-wiz and @jscontroller and @jsaction and @decode-data-ved="1"]/div/div'
    ).first

    stop_threahold = 5  # If new reviews are not found, then execution will stop
    stop_counter = 0
    while True:
        # Scroll down by a small amount

        page.mouse.wheel(0, 10000)  # scroll to the end
        time.sleep(0.2)
        page.mouse.wheel(0, -200)  # scroll a little up, to load new reviews
        time.sleep(2)

        new_reviews_available = new_reviews_arrived(
            locator_review_objs, iter_idx_scroll
        )

        if new_reviews_available:
            # Pasrse the reviews
            (
                review_data,
                stop_criteria_met,
                c_google_reviews,
            ) = full_scrn_parse_review_objs(
                input_params.stop_critera, locator_review_objs, iter_idx_scroll
            )
            if isinstance(review_data, list):
                ls_reviews += review_data
                count_google_reviews += c_google_reviews
                count_all_reviews += len(review_data)

                if input_params.save_review_to_disk:
                    save_local_files(
                        entity_name=input_params.place_name,
                        sort_by=input_params.sort_by,
                        ls_reviews=review_data,
                    )

                # TODO: remove this
                if len(review_data) < 10:
                    logging.debug(f'********* {review_data[-1]["username"]}*********')

            print(
                f"Scrapped Reviews: {count_all_reviews}   Google-Reviews: {count_google_reviews}   [Scroll_Window: {iter_idx_scroll}/{total_review_divs}]"
            )
            iter_idx_scroll += 1

            if -1 < input_params.n_reviews <= count_all_reviews:
                ls_reviews = ls_reviews[: input_params.n_reviews]
                break

            # if stopping criteria is available, stop the scroll as soon as the target is found
            if stop_criteria_met:
                break
        else:
            stop_counter += 1
            logging.info(f"Cant load new reviews. Stop_counter: {stop_counter}")

        if stop_counter >= stop_threahold:
            logging.info("Reached Bottom end can't load more reivews")
            print("Reached Bottom end can't load more reivews")
            break

    return ls_reviews, iter_idx_scroll, total_review_divs, overall_rating


def reviews_in_dialog_box(
    page: Page, input_params: Input
) -> Tuple[List[dict], int, int, dict]:
    """When number of reviews are not enough (e.g. less than 100) and they are
    opened in a dialog box in the same screen. This method is used to scroll, scrape,
    and iterate on the reviews

    Args:
        page: page object containing the reviews
        input_params: input parameters for scraping from google

    Returns:
        list of reviews
    """
    overall_rating: dict = dialog_box_extract_overall_rating(page)
    if not overall_rating:
        logging.error("Hotel metadata not scraped")
        raise Exception("Hotel metadata not scraped")

    overall_rating["entity_name"] = input_params.place_name

    if input_params.save_metadata_to_disk:
        save_local_files(
            entity_name=input_params.place_name,
            sort_by="",
            entitiy_metadata=overall_rating,
        )

    time.sleep(2)

    page.locator(
        '//g-dropdown-menu//div[@role="button" and @aria-expanded="false"]'
    ).first.click()

    time.sleep(2)

    xpath_sort_item = "//g-menu[@role='menu']/g-menu-item[@role='menuitemradio' and div[text()= '{inner_text}'] ]"

    if input_params.sort_by == "most_helpful":
        page.locator(xpath_sort_item.format(inner_text="Most relevant")).first.click()

    elif input_params.sort_by == "most_recent":
        page.locator(xpath_sort_item.format(inner_text="Newest")).first.click()

    elif input_params.sort_by == "highest_score":
        page.locator(xpath_sort_item.format(inner_text="Highest rating")).first.click()

    elif input_params.sort_by == "lowest_score":
        page.locator(xpath_sort_item.format(inner_text="Lowest rating")).first.click()

    else:
        err = f"Invalid sort by option: {input_params.sort_by}. It must be any of these options: [most_helpful, most_recent, highest_score, lowest_score]"
        logging.error(err)
        raise Exception(err)

    # *** Scrolling reviews ***
    # End scrolling if any one of the two conditions are met
    # 1. It has reached the end of reviews
    # 2. Stoping criteria is met. We are not interested in getting the remaining past reviews are

    # every scroll iteration will add 10 more reviews on the page.
    # basically it adds a new div containing 10 where items each item is a review
    # unless the the end of the screen has been reached and the remaining reviews are less than 10
    count_google_reviews = 0
    count_all_reviews = 0

    # iter_idx_scroll = 1 because XPath typically uses a 1-based index for addressing elements in a node set.
    # That means the first element in a node set is referred to as element 1
    iter_idx_scroll = 1
    ls_reviews = []  # list of scraped reviews
    total_review = overall_rating["no_of_reviews"]
    # divide by then because each div contains 10 review objects
    total_review_divs = math.ceil(total_review / 10)

    time.sleep(5)

    locator_review_objs = page.locator(
        '//div[@id="reviewSort" and @data-async-type="reviewSort"]'
    ).first

    # It will scroll down 10 times. If new reviews (div) don't appear it means
    # It has reached the end of the reviews and there are no new review to appear
    reached_end_thresh = 5

    while True:
        page.mouse.wheel(0, 10000)  # scroll to the end
        time.sleep(0.2)
        page.mouse.wheel(0, -50)  # scroll a little up, to load new reviews
        time.sleep(2)

        # Check if you have reached the bottom of the page

        new_reviews_available = new_reviews_arrived(
            locator_review_objs, iter_idx_scroll
        )

        if new_reviews_available:
            # Pasrse the reviews
            (
                review_data,
                stop_criteria_met,
                c_google_reviews,
            ) = dialog_box_parse_review_objs(
                input_params.stop_critera, locator_review_objs, iter_idx_scroll
            )
            if isinstance(review_data, list):
                ls_reviews += review_data
                count_google_reviews += c_google_reviews
                count_all_reviews += len(review_data)

                if input_params.save_review_to_disk:
                    save_local_files(
                        entity_name=input_params.place_name,
                        sort_by=input_params.sort_by,
                        ls_reviews=review_data,
                    )

            print(
                f"Scrapped {len(ls_reviews)}   [Scroll_Window: {iter_idx_scroll}/{total_review_divs}]"
            )

            if -1 < input_params.n_reviews <= count_all_reviews:
                ls_reviews = ls_reviews[: input_params.n_reviews]
                break

            # if stopping criteria is available, stop the scroll as soon as the target is found
            if stop_criteria_met:
                break

            iter_idx_scroll += 1
            reached_end_thresh = 5

        else:
            # break form the loop, if the max number of retries have reached
            if reached_end_thresh > 0:
                reached_end_thresh -= 1
                logging.info(
                    f"Trying to load new reviews:  Retry Count={reached_end_thresh}"
                )
            else:
                logging.info(
                    f"Reviews End Reached. No more retries:  Retry Count={reached_end_thresh}"
                )
                break

    return ls_reviews, iter_idx_scroll, total_review_divs, overall_rating


def execute_search_term_on_google(
    playwright: Playwright, input_params: Input
) -> Tuple[List[dict], dict]:
    """

    Main function which launches browser instance and performs search on google

    Args:

        playwright: Playwright instance
        sort_by: sort the reviews by this options before starting to scrape
        n_review: number of reviews to scrape. -1 means 'scrape all reviews'
        save_review_to_disk: Whether to save the reviews to a local file
        save_metadata_to_disk: Whether to save the metadata "overall rating etc" to a local file
    """
    load_config()
    setup_logging()

    t1 = time.time()

    browser = playwright.chromium.launch(headless=False, args=["--start-maximized"])

    context = browser.new_context()

    # Open new page
    page = context.new_page()

    page.goto("https://www.google.com/")

    if (
        "This network is blocked due to unaddressed abuse complaints about malicious behavior."
        in page.content()
    ):
        while True:
            beepy.beep(sound=1)
            time.sleep(5)
            if page.locator(
                '//textarea[@aria-label="Search" or @aria-label="بحث"]'
            ).first.is_visible():
                beepy.beep(sound=4)
                break

    time.sleep(2)

    page.locator('//textarea[@aria-label="Search" or @aria-label="بحث"]').first.fill(
        input_params.place_name
    )

    page.keyboard.press("Enter")

    time.sleep(5)

    locator_eng_lan_button = page.locator("//a[contains(., 'Change to English')]").first
    # If the laguage is not English
    print(
        "locator_eng_lan_button.is_visible()",
        locator_eng_lan_button.is_visible(timeout=10000),
    )
    if locator_eng_lan_button.is_visible(timeout=10000):
        locator_eng_lan_button.click()

    # *** Check which review button is present ***

    # *** Option 1: When entity has more than 100 or large number of reviews***
    # If 'View all reviews' is present, It means reviews will reviews will be opened in full screen mode

    # *** Option 2: When the entity has fewer reviews e.g. less than 100***
    # Button like this is present: '50 Google reviews', '10 Google reviews'
    # page.wait_for_load_state("networkidle", timeout=30000)
    time.sleep(5)

    button_type_1 = "xpath=//a[contains(@href, '/travel/search?') and span[text()='View all reviews']]"
    button_type_2 = "xpath=//a[@data-is_owner='false' and @role='button' and span[contains(., ' Google reviews')]]"

    ls_reviews: List[dict] = []
    iter_idx_scroll = 0
    total_review_divs = 0
    overall_rating: dict = {}
    # Click reviews button
    if page.locator(button_type_1).first.is_visible(timeout=10000):
        logging.info("Reviews will be opened in a new screen")
        page.locator(button_type_1).first.click(timeout=50000)
        ls_reviews, iter_idx_scroll, total_review_divs, overall_rating = (
            reviews_in_full_screen(page, input_params)
        )
    elif page.locator(button_type_2).first.is_visible(timeout=10000):
        logging.info("Reviews will be opened in a dialog box in the same screen")
        page.locator(button_type_2).first.click(timeout=50000)
        page.set_viewport_size({"width": 1200, "height": 800})
        ls_reviews, iter_idx_scroll, total_review_divs, overall_rating = (
            reviews_in_dialog_box(page, input_params)
        )

    logging.info(
        f"Scrapping Complete   {len(ls_reviews)}   [Scroll_Window: {iter_idx_scroll}/{total_review_divs}]"
    )

    print(f"Completed in {time.time()-t1}")

    context.close()

    browser.close()

    return ls_reviews, overall_rating


def execute_visit_google_url(
    playwright: Playwright, input_params: Input
) -> Tuple[Union[None, List[dict]], Union[None, dict]]:
    """

    Main function which launches browser instance and visit google page url of the hotel

    Args:

        playwright: Playwright instance
        sort_by: sort the reviews by this options before starting to scrape
        n_review: number of reviews to scrape. -1 means 'scrape all reviews'
        save_review_to_disk: Whether to save the reviews to a local file
        save_metadata_to_disk: Whether to save the metadata "overall rating etc" to a local file
    """
    load_config()
    setup_logging()
    ls_reviews: List[dict] = []
    iter_idx_scroll = 0
    total_review_divs = 0
    overall_rating: dict = {}

    t1 = time.time()

    browser = playwright.chromium.launch(headless=False, args=["--start-maximized"])

    context = browser.new_context()

    # Open new page
    page = context.new_page()

    if len(input_params.google_page_url):
        page.goto(input_params.google_page_url)
    else:
        raise Exception("Please pass a valid value for 'google_page_url'")

    xpath_review_button = (
        '//div[@aria-label="Reviews" and @id="reviews" and @role="tab"]'
    )
    if is_the_element_visible(page, xpath_review_button):
        page.locator(f"xpath={xpath_review_button}").first.click(timeout=90000)
        time.sleep(2)

        ls_reviews, iter_idx_scroll, total_review_divs, overall_rating = (
            reviews_in_full_screen(page, input_params)
        )
    else:
        logging.error("Unable to find/click the Reviews button")

    context.close()
    browser.close()

    logging.info(
        f"Scrapping Complete   {len(ls_reviews)}   [Scroll_Window: {iter_idx_scroll}/{total_review_divs}]"
    )

    print(f"Completed in {time.time()-t1}")
    return ls_reviews, overall_rating
