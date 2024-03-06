import time
from logging import Logger
from typing import Union

from playwright.sync_api import Page


def is_the_element_visible(
    page: Page,
    xpath: str,
    state: str = "visible",
    timeout_ms: int = 30000,
    logger: Union[Logger, None] = None,
) -> bool:
    """Waits for the element to be visible.

    Args:
        page: Current page
        xpath: path of the target element

    Returns:
        True if element is found else False
    """
    if logger is None:
        import logging

        logger = logging.getLogger(__name__)
    try:
        # Hotel address (from the overview on google travels page)
        loc_address = page.locator(f"xpath={xpath}").first
        loc_address.wait_for(
            timeout=timeout_ms, state=state
        )  # default timeout is 30 seconds
        return True
    except TimeoutError as er:
        logger.warning(f"Element not visible: {er}")
    except Exception as ex:
        logger.error(ex)

    return False
