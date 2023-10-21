import traceback
import time
import pickle
from typing import Tuple, Union, List
from playwright.sync_api import Playwright, Page, Locator, expect
import logging
from pprint import pprint
import re
import csv
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta
import re
import math
import yaml

LOCAL_OUTPUT_PATH = "{output_dir}/{entity_name}_" + str(datetime.now())
stop_criteria = None  # it will be a dict with keys "name", "review"


def load_config():
    """Loads config.yml containing output directory and stop_critera (where to stop scrolling)"""
    global LOCAL_OUTPUT_PATH
    global stop_criteria
    try:
        with open("config.yml", "r") as file:
            config = yaml.safe_load(file)
            LOCAL_OUTPUT_PATH = LOCAL_OUTPUT_PATH.format(
                output_dir=config["output_dir"], entity_name="{entity_name}"
            )
            if "stop_criteria" in config:
                if (
                    "name" in config["stop_criteria"]
                    and "review" in config["stop_criteria"]
                ):
                    if len(config["stop_criteria"]["name"]):
                        stop_criteria = {}
                        stop_criteria["name"] = config["stop_criteria"]["name"]
                        stop_criteria["review"] = config["stop_criteria"]["review"]

                        pprint(f"Stop criteria loaded: {stop_criteria}")
                else:
                    raise Exception(
                        "Stop criteria missing any of the two keys [name, review]"
                    )

            print("config.yml file loaded")
    except Exception as ex:
        tb = traceback.format_exc()
        print(f"Unable to use config.yml. {tb}")


##########################################################
# ******** Utility and Parsing Methods ********
##########################################################


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


def save_html(html: str, scroll_iter_idx: int):
    """Save html file for debugging purpose"""
    try:
        with open(f"scroll_iter_idx_{scroll_iter_idx}.html", "w") as f:
            f.write(html)
    except Exception as ex:
        print("Saving html failed: ", ex)


##########################################################
# ******** Parsing Methods ********
##########################################################


def extract_overall_rating(page: Page) -> dict:
    """
    Extracts the overall rating (eg. 4.1 out of 5 star, 574 number of reviews)

    Args:
        page: Page object containing reviews broswer tab

    Returns:
        Overall ratting and number of reviews
    """
    expect(
        page.locator(
            "//div[contains(@aria-label, 'out of 5 stars') and @role='text']"
        ).first
    ).to_be_attached(timeout=100000)
    expect(
        page.locator(
            "//div[contains(@aria-label, '5-star reviews') and @role='text']"
        ).first
    ).to_be_attached(timeout=100000)

    rating = n_reviews = None
    rating_locator = page.locator(
        "//div[contains(@aria-label, 'out of 5 stars') and @role='text']"
    ).first
    if rating_locator.is_visible():
        # It will extract text like this: '3.6 out of 5 stars from 206 reviews'
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


def parse_review_rating_tags(
    ls_text: list,
) -> Tuple[Union[str, None], Union[str, None], Union[str, None], Union[str, None]]:
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

    full_review = (
        rating_tags
    ) = eng_ver = original_ver = owner_resp_time = owner_resp_text = None

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
            eng_ver = full_review_p2[0].replace("(Translated by Google)", "").strip()
            original_ver = full_review_p2[1]
        else:
            eng_ver = None
            original_ver = full_review

    return {
        "full_review": full_review,
        "rating_tags": rating_tags,
        "eng_ver": eng_ver,
        "original_ver": original_ver,
        "owner_resp_text": owner_resp_text,
        "owner_resp_time": owner_resp_time,
    }


def parse_review_objs(
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

    global stop_criteria

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

            if name == "Anton":
                print("Here")

            # review text

            review_text: list = current_review_obj.locator(
                "xpath="
                + 'div[2]//span[normalize-space() != "Business" and normalize-space() != "Vacation" and normalize-space() != "Family" and normalize-space() != "Friends" and normalize-space() != "Couple" and normalize-space() != "Solo" and not(contains(., " ❘ ")) and not(contains(., "Read more")) and not(contains(., "Report review")) and not(.//svg) ][not(.//span/span)] | div[2]//p[not(contains(., " ❘ ")) and not(contains(., "Read more")) and not(contains(., "Report review")) and not(.//svg)][not(.//p/span)]'
            ).all_inner_texts()

            # parse the current review text which also contains room/service/location tags
            parsed_review_text: dict = parse_review_rating_tags(review_text)

            if stop_criteria is not None:
                target = current_review_obj.inner_text().lower()
                if (
                    stop_criteria["name"].lower() in target
                    and stop_criteria["review"].lower() in target
                ):
                    logging.info(
                        f"Stopping critera met. Returning {len(ls_reviews)} reviews"
                    )
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
                    img.get_attribute("src")
                    if img.get_attribute("src")
                    else img.get_attribute("data-src")
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

            parsed_review_text.update(
                {
                    "username": name,
                    "user_profile": user_profile,
                    "date": date,
                    "date1": date1,
                    "review_site": review_site,
                    "rating": rating,
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


def new_reviews_arrived(review_objs: Locator, scroll_iter_idx: int) -> Tuple[bool, int]:
    """Check the availability of new review by comparing the hash of the object with
    the previous hash value

    Args:
        review_objs: Locator containing review objects
        previous_hash: hash value of the previous locator objects

    Returns:
        in case of new review:  (True, new hash)  otherwise (False, previous hash value)
    """
    if review_objs.locator("xpath=" + f"div[{scroll_iter_idx}]").first.is_visible(
        timeout=100
    ):
        return True
    else:
        return False


##########################################################
# ******** Main Executable Method ********
##########################################################


def run(
    playwright: Playwright,
    search_term: str,
    sort_by: str = "most_recent",
    n_reviews: int = -1,
    save_review_to_disk: bool = True,
    save_metadata_to_disk: bool = True,
) -> List[dict]:
    """

    Main function which launches browser instance and performs browser

    Args:

        playwright: Playwright instance
        sort_by: sort the reviews by this options before starting to scrape
        n_review: number of reviews to scrape. -1 means 'scrape all reviews'
        save_review_to_disk: Whether to save the reviews to a local file
        save_metadata_to_disk: Whether to save the metadata "overall rating etc" to a local file
    """
    load_config()

    global stop_criteria
    t1 = time.time()

    logging.basicConfig(
        filename=f"logs/{datetime.now()}.log",
        level=logging.DEBUG,
        format="%(asctime)s [%(filename)s] %(levelname)s: %(message)s",
    )

    browser = playwright.chromium.launch(
        headless=False,
        # proxy={'server': 'proxy url'}
    )

    context = browser.new_context()

    # Open new page
    page = context.new_page()

    page.goto("https://www.google.com/")

    page.locator('[aria-label="Search"]').fill(search_term)

    page.keyboard.press("Enter")

    # wait for review button

    page.locator('//span[text()="View all reviews"]').first.wait_for(timeout=100000)

    # Click reviews button

    page.locator(
        "//a[contains(@href, '/travel/search?') and span[text()='View all reviews']]"
    ).first.click(timeout=50000)

    overall_rating: dict = extract_overall_rating(page)

    if not overall_rating:
        logging.error("Hotel metadata not scraped")
        raise Exception("Hotel metadata not scraped")

    overall_rating["entity_name"] = search_term

    print(overall_rating)

    if save_metadata_to_disk:
        save_local_files(
            entity_name=search_term, sort_by="", entitiy_metadata=overall_rating
        )

    # _ = input("overall_rating Extracted")

    page.wait_for_timeout(10000)

    # Click the "sort by" option

    page.locator(
        '//div[@role="listbox" and @aria-expanded="false" and @aria-label="Review Sort Options"]'
    ).first.click()

    page.wait_for_timeout(30000)

    if sort_by == "most_helpful":
        page.locator(
            '//div[@data-value="1" and @aria-selected="true" and @aria-label="Most helpful" and @role="option"]'
        ).first.click()

    elif sort_by == "most_recent":
        page.locator(
            '//div[@data-value="2" and @aria-selected="false" and @aria-label="Most recent" and @role="option"]'
        ).first.click()

    elif sort_by == "highest_score":
        page.locator(
            '//div[@data-value="3" and @aria-selected="false" and @aria-label="Highest score" and @role="option"]'
        ).first.click()

    elif sort_by == "lowest_score":
        page.locator(
            '//div[@data-value="4" and @aria-selected="false" and @aria-label="Lowest score" and @role="option"]'
        ).first.click()

    else:
        err = f"Invalid sort by option: {sort_by}. It must be any of these options: [most_helpful, most_recent, highest_score, lowest_score]"
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
    iter_idx_scroll = 1  # scroll iteration index
    # review_hash = None  # to check whether new reviews arrived or not
    ls_reviews = []  # list of scraped reviews
    total_review = overall_rating["no_of_reviews"]
    # divide by then because each div contains 10 review objects
    total_review_divs = math.ceil(total_review / 10)

    locator_review_objs = page.locator(
        '//c-wiz[@data-node-index="0;0" and @c-wiz="" and @decode-data-ved="1"]/div/div'
    ).first

    while True:
        # Scroll down by a small amount
        # page.evaluate("window.scrollBy(0, 300)")

        page.mouse.wheel(0, 10000)  # scroll to the end
        time.sleep(0.2)
        page.mouse.wheel(0, -100)  # scroll a little up, to load new reviews
        time.sleep(2)

        # Check if you have reached the bottom of the page
        at_bottom = page.evaluate(
            "window.innerHeight + window.scrollY >= document.body.scrollHeight"
        )
        if at_bottom:
            page.mouse.wheel(0, -100)
            time.sleep(1)
            page.mouse.wheel(0, 100)
            time.sleep(4)
            at_bottom = page.evaluate(
                "window.innerHeight + window.scrollY >= document.body.scrollHeight"
            )

        new_reviews_available = new_reviews_arrived(
            locator_review_objs, iter_idx_scroll
        )

        if new_reviews_available:
            # Pasrse the reviews
            review_data, stop_criteria_met, c_google_reviews = parse_review_objs(
                locator_review_objs, iter_idx_scroll
            )
            if isinstance(review_data, list):
                ls_reviews += review_data
                count_google_reviews += c_google_reviews
                count_all_reviews += len(review_data)

                if save_review_to_disk:
                    save_local_files(
                        entity_name=search_term, sort_by=sort_by, ls_reviews=review_data
                    )

                # TODO: remove this
                if len(review_data) < 10:
                    logging.debug(f'********* {review_data[-1]["username"]}*********')

            print(
                f"Scrapped Reviews: {count_all_reviews}   Google-Reviews: {count_google_reviews}   [Scroll_Window: {iter_idx_scroll}/{total_review_divs}]"
            )
            iter_idx_scroll += 1

            if -1 < n_reviews <= count_all_reviews:
                ls_reviews = ls_reviews[:n_reviews]
                break

            # if stopping criteria is available, stop the scroll as soon as the target is found
            if stop_criteria_met:
                break

        if at_bottom:
            logging.info("Reached Bottom end can't load more reivews")
            print("Reached Bottom end can't load more reivews")
            break

    logging.info(
        f"Scrapping Complete   {len(ls_reviews)}   [Scroll_Window: {iter_idx_scroll}/{total_review_divs}]"
    )

    print(f"Completed in {time.time()-t1}")

    context.close()

    browser.close()

    return ls_reviews
