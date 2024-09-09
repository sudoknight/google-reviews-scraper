## 9-September-2024

#### Added
1. logger can be passed.


## 27-Mar-2024

#### Fixed
1. added alternate xpaths for finding rating from the review
2. While iterating on the review objects by idx, check if the review object exists or not


## 8-Mar-2024

#### Added
1. Method added 'run_as_module': Call scrapper from your own code
2. Parameter added 'google_page_url': If you can url of the page you can go directly on that page instead of searching your 'term' on google

#### Fixed
1. Matches first 50 characters of stop_criteria review 


## 24-Nov-2023

#### Added
1. field 'total' rating score
2. Scraping of reviews when the reviews are opened in a dialog box on the same screen
3. data models for input validation

#### Changed
1. 'eng_ver' and 'original_ver' fields renamed to 'en_lang_text' and 'other_lang_text'
2. Stop Critera moved from config file to CLI input parameters



## 04-Sep-2024

#### Changed
1. 'en_lang_text' to 'en_full_review'. So that field names are same as booking scrapper
1. 'rating_score' to 'rating'. So that field names are same as booking scrapper
