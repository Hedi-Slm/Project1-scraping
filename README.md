# **Books to Scrape Web Scraper**

This is a Python web scraping project that extracts book data from [Books to Scrape](https://books.toscrape.com/), a mock website designed for web scraping practice. The script collects information about books and saves it in CSV files.
It also downloads book cover images and stores them in a separate folder.

## **Features**

- Scrape URLs of all categories from the website's homepage.
- Scrape URLs of all pages from each category (some categories have multiple pages due to pagination).
- Scrape URLs of all products (books) from each category page.
- Scrape detailed data from each product page within a category.
- Download and save book cover images in the images folder, and store book data in CSV files named after each category.

## **Extracted Data**

For each book, the script extracts the following information:

- Title
- Universal Product Code (UPC)
- Category
- Price Excluding Tax
- Price Including Tax
- Number Available
- Review Rating
- Product Description
- Image URL
- Product Page URL
- Book Cover Image

## **Installation**

Clone the repository:
```
git clone https://github.com/Hedi-Slm/Project1-scraping.git
```
Install the required dependencies:
```
pip install -r requirements.txt
```
Run the scraper:
```
python scraping_proj.py
```
## **Requirements**

The project requires the following Python libraries, which are listed in the requirements.txt file:

- requests
- beautifulsoup4
