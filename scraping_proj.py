import re
import requests
import csv
from bs4 import BeautifulSoup as bs
import os
from requests.exceptions import RequestException


BASE_URL = "https://books.toscrape.com/"
BASE_PRODUCT_URL = "https://books.toscrape.com/catalogue/"


HEADER = ["title", "universal_product_code", "category", "price_excluding_tax",
          "price_including_tax", "number_available", "review_rating",
          "product_description", "image_url", "product_page_url"]

RATING_CONVERTOR = {"One": "1/5", "Two": "2/5", "Three": "3/5", "Four": "4/5", "Five": "5/5"}

ALL_CATEGORY_SELECTOR = ".side_categories > ul > li > ul > li"
ALL_BOOKS_SELECTOR = ".product_pod > h3 > a"
DESCRIPTION_SELECTOR = "#content_inner > article > p"


def write_csv_header(file_name):
    """Writes the CSV header to a file."""
    try:
        with open(file_name, "w", encoding="utf-8", newline='') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(HEADER)
    except OSError as e:
        print(f"Error writing CSV header to {file_name}: {e}")


def write_csv_row(file_name, row):
    """Appends a row of data to the CSV file."""
    try:
        with open(file_name, "a", encoding="utf-8", newline='') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(row)
    except OSError as e:
        print(f"Error writing to CSV {file_name}: {e}")


def get_html(session, url):
    """Fetch the HTML content for the given URL."""
    try:
        response = session.get(url)
        response.encoding = 'utf-8'
        return bs(response.text, "html.parser")
    except RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None


def get_information(soup):
    """Extracts book information from the product page."""
    title = soup.find("title").text.split("|")[0].strip()
    rating = RATING_CONVERTOR.get(soup.find("p", class_="star-rating").get("class")[1])
    description_tag = soup.select_one(DESCRIPTION_SELECTOR)
    description = description_tag.text if description_tag else "No description available"
    img_url = BASE_URL + soup.find("img").get("src")[5::]
    return title, [rating, description, img_url]


def get_information_table(soup, category_name):
    """Extracts data from the table at the bottom of the product page."""
    table = soup.find("table").find_all("td")
    info_table = []
    info_table.append(table[0].text)  # Universal product code
    info_table.append(category_name)  # Category
    info_table.append(table[2].text)  # Price (excl. tax)
    info_table.append(table[3].text)  # Price (incl. tax)
    info_table.append(re.search(r"\d+", table[5].text).group())  # Availability

    return info_table


def prepare_row(info_list, info_table, current_row):
    """Prepares a row of data for CSV output."""
    current_row.extend(info_table)
    current_row.extend(info_list)


def get_every_book_url(soup):
    """Extracts URLs of all books from the category page soup."""
    all_books = soup.select(ALL_BOOKS_SELECTOR)
    return [BASE_PRODUCT_URL + book["href"][9::] for book in all_books]


def get_every_category_url(soup):
    """Extracts category URLs and names from the homepage soup."""
    all_category = soup.select(ALL_CATEGORY_SELECTOR)
    category_links, category_names = [], []

    for category in all_category:
        category_links.append(BASE_URL + category.find("a")["href"])
        category_names.append(category.find("a").text.strip())

    return category_links, category_names


def create_images_folder():
    """Creates an 'images' folder if it does not already exist."""
    if not os.path.exists("images"):
        os.mkdir("images")


def save_image(image_url, image_name):
    """Downloads and saves the image to the 'images' folder."""
    image_name = re.sub(r"[’“”<>:\"/\\|?*'#]", ' ', image_name)  # Remove invalid characters for file name
    image_path = os.path.join("images", image_name + ".jpg")

    try:
        response = requests.get(image_url, stream=True)
        if response.status_code == 200:
            response.raw.decode_content = True
            try:
                with open(image_path, "wb") as file:
                    file.write(response.content)
            except OSError as e:
                print(f"Error saving image {image_url}: {e}")
        else:
            print(f"Failed to download image: {image_url}. Status code: {response.status_code}")
    except RequestException as e:
        print(f"Error downloading image {image_url}: {e}")


def main():
    session = requests.Session()
    soup = get_html(session, BASE_URL)

    create_images_folder()

    # Get all the URLs and names of the different categories
    category_links, category_names = get_every_category_url(soup)

    # Iterate over each category
    for category_link, category_name in zip(category_links, category_names):
        # Clean the category name to use it in file names
        csv_file_name = category_name.replace(" ", "_").lower() + ".csv"

        # Write CSV header for the current category
        write_csv_header(csv_file_name)

        pages_category_url = []
        soup = get_html(session, category_link)

        if not soup:
            print(f"Failed to retrieve category pages from {category_name}. Skipping.")
            continue

        # Get the number of pages of the current category
        pager = soup.find("ul", class_="pager")
        number_of_pages = 0  # Default to 0 page if no pager is found

        if pager:
            number_of_pages = int(pager.find("li", class_="current").text.strip()[-1])

        # Get all the URLs of the pages of the current category
        if number_of_pages:
            for i in range(number_of_pages):
                pages_category_url.append(category_link.replace("index.html", f"page-{i+1}.html"))
        else:
            pages_category_url.append(category_link)

        # Get all the URLs of the books in the current category
        books_links = []
        for url in pages_category_url:
            soup = get_html(session, url)
            if soup:
                books_links.extend(get_every_book_url(soup))
            else:
                print(f"Failed to retrieve books page from {url}. Skipping.")
                continue

        # Get all the information of every book in the current category and write it in the CSV
        for book_url in books_links:
            soup = get_html(session, book_url)
            if soup:
                title, information_list = get_information(soup)
                information_table = get_information_table(soup, category_name)
                current_row = [title]  # Prepare a row with the book title
                prepare_row(information_list, information_table, current_row)
                current_row.append(book_url)  # Append the book's URL

                # Save the book's image using img_url and book title
                save_image(information_list[-1], title)

                # Write the row to the CSV of the current category
                write_csv_row(csv_file_name, current_row)
            else:
                print(f"Failed to retrieve book information from {book_url}. Skipping.")

        print(f"All books from category '{category_name}' have been saved in '{csv_file_name}'.")
    print("Done.")


if __name__ == "__main__":
    main()

