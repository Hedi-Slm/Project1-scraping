import asyncio
import csv
import re
import aiofiles
import httpx
from bs4 import BeautifulSoup as bs
import os
import time


# Base URLs for the website to scrape
BASE_URL = "https://books.toscrape.com/"
BASE_PRODUCT_URL = "https://books.toscrape.com/catalogue/"

# CSV header defining column names for csv file
HEADER = ["title", "universal_product_code", "category", "price_excluding_tax",
          "price_including_tax", "number_available", "review_rating",
          "product_description", "image_url", "product_page_url"]

# Convert str book rating to rating out of 5
RATING_CONVERTOR = {"One": "1/5", "Two": "2/5", "Three": "3/5", "Four": "4/5", "Five": "5/5"}

# CSS selectors for scraping specific elements from the pages
ALL_CATEGORY_SELECTOR = ".side_categories > ul > li > ul > li"
ALL_BOOKS_SELECTOR = ".product_pod > h3 > a"
DESCRIPTION_SELECTOR = "#content_inner > article > p"

# Semaphore to control the maximum number of concurrent requests
MAX_CONCURRENT_REQUESTS = 50
SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)


def create_data_folders():
    """Creates folders for storing CSV files and images, if they do not already exist."""
    if not os.path.exists("csv"):
        os.mkdir("csv")

    if not os.path.exists("images"):
        os.mkdir("images")


def sanitize_name(name):
    """Removes invalid characters from a filename to prevent error during file creation."""
    name = re.sub(r"[’“”<>:\"/\\|?*'#]", ' ', name)
    return name


async def get_html(session, url):
    """
    Fetches the HTML content from a given URL using an asynchronous HTTP request.
    Uses a semaphore to limit the number of concurrent requests.
    """
    async with SEMAPHORE:
        # Sleep could be used for not overloading the server / Changing semaphores values is also possible
        # await asyncio.sleep(0.1)
        try:
            response = await session.get(url)
            response.raise_for_status()  # Raises an error for any non-2xx status
            return bs(response.text, "html.parser")
        except httpx.HTTPError as e:
            print(f"Error fetching {url}: {e}")
    return None


def get_every_category(soup):
    """Extracts category URLs and names from the homepage soup.

        Returns:
        category_links (list): List of URLs for each book category.
        category_names (list): List of category names.
    """
    all_category = soup.select(ALL_CATEGORY_SELECTOR)
    category_links, category_names = [], []

    for category in all_category:
        category_links.append(BASE_URL + category.find("a")["href"])
        category_names.append(category.find("a").text.strip())

    return category_links, category_names


async def process_category(session, category_link, category_name):
    """
    Processes a category page by gathering all book URLs in the category, scraping each book’s details,
    and saving the data into a CSV file.
    """

    # Fetch all the book URLs in the category
    books_urls = await get_book_urls(session, category_link)

    # Create a list to store all the book processing tasks
    tasks = []
    for book_url in books_urls:
        tasks.append(process_book(session, book_url, category_name))

    # Gather all book details concurrently
    books_info_list = await asyncio.gather(*tasks)

    # Filter out any None values for books that failed to process
    information_rows = [book_info for book_info in books_info_list if book_info is not None]

    # Write all the book information to a CSV file for the category
    await write_csv(category_name, information_rows)


async def get_book_urls(session, category_link):
    """
    Fetches all book URLs from all pages in a given category.

    Returns:
        books_urls (list): List of URLs for each book in the category.
    """

    books_urls = []
    current_page_url = category_link
    page_number = 1

    while True:
        soup = await get_html(session, current_page_url)
        if not soup:
            break

        # Extract all book URLs from the current page
        books = soup.select(ALL_BOOKS_SELECTOR)
        books_urls.extend([BASE_PRODUCT_URL + book["href"][9::] for book in books])

        # Check for pagination by using the "pager"
        pager = soup.find("ul", class_="pager")
        if pager and "next" in pager.text:
            page_number += 1
            current_page_url = category_link.replace("index.html", f"page-{page_number}.html")
        else:
            break

    return books_urls


async def process_book(session, book_url, category_name):
    """
    Scrapes data for a single book, including image download and relevant information.

    Returns:
        current_row (list): List of data fields for the book.
    """

    soup = await get_html(session, book_url)
    if not soup:
        return None

    # Extract book information
    title, information_list = get_information(soup)
    information_table = get_information_table(soup, category_name)

    # Fetch the book cover image asynchronously
    image_task = fetch_image(session, information_list[-1], title)

    # Compile all the book data into a list
    current_row = [title]
    prepare_row(information_list, information_table, current_row)
    current_row.append(book_url)

    await image_task

    return current_row


def get_information(soup):
    """
    Extracts basic information for a book, such as title, rating, description, and image URL.

    Returns:
        title (str): Title of the book.
        information_list (list): List of rating, description, and image URL.
    """

    title = soup.find("title").text.split("|")[0].strip()
    rating = RATING_CONVERTOR.get(soup.find("p", class_="star-rating").get("class")[1])
    description_tag = soup.select_one(DESCRIPTION_SELECTOR)
    description = description_tag.text if description_tag else "No description available"
    img_url = BASE_URL + soup.find("img").get("src")[5::]
    return title, [rating, description, img_url]


def get_information_table(soup, category_name):
    """
    Extracts tabular information from a book page, such as the UPC and price details.

    Returns:
        info_table (list): List of specific book details.
    """

    table = soup.find("table").find_all("td")
    info_table = [
        table[0].text,  # Universal product code
        category_name,  # Category
        table[2].text,  # Price (excl. tax)
        table[3].text,  # Price (incl. tax)
        re.search(r"\d+", table[5].text).group()  # Availability
    ]
    return info_table


async def fetch_image(session, img_url, title):
    """ Downloads and saves an image for a given book. """
    image_name = sanitize_name(title) + ".jpg"
    image_path = os.path.join("images", image_name)

    try:
        response = await session.get(img_url)
        response.raise_for_status()  # Raises an error for any non-2xx status

        try:
            async with aiofiles.open(image_path, "wb") as file:
                await file.write(response.content)
        except OSError as e:
            print(f"Error saving image: {image_name} - {e}")

    except httpx.HTTPError as e:
        print(f"Error fetching image: {img_url} - {e}")


def prepare_row(info_list, info_table, current_row):
    """ Compiles all information for a book into a single row for CSV output. """
    current_row.extend(info_table)
    current_row.extend(info_list)


async def write_csv(category_name, information_rows):
    """ Writes all book information for a category into a CSV file. """

    # Prepare the CSV file name / path
    csv_name = sanitize_name(category_name) + ".csv"
    csv_path = os.path.join("csv", csv_name)

    async with aiofiles.open(csv_path, "w", encoding="utf-8", newline='') as csv_file:
        writer = csv.writer(csv_file)
        try:
            await writer.writerow(HEADER)
            for row in information_rows:
                await writer.writerow(row)
        except OSError as e:
            print(f"Error writing CSV {csv_name}: {e}")


async def main():
    """
    Main asynchronous function that initializes scraping of all book categories,
    downloads images, and saves book data into CSV files.
    """

    # Create an async session and get the homepage soup
    async with httpx.AsyncClient() as session:
        soup = await get_html(session, BASE_URL)
        create_data_folders()

        # Get all the URLs and names of the different categories
        category_links, category_names = get_every_category(soup)

        # Launch tasks for each category concurrently
        tasks = []
        for category_link, category_name in zip(category_links, category_names):
            tasks.append(process_category(session, category_link, category_name))

        await asyncio.gather(*tasks)


if __name__ == "__main__":
    start_time = time.perf_counter()
    asyncio.run(main())
    end_time = time.perf_counter()
    print(f"Finished in {end_time - start_time:.2f} seconds")