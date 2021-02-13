#############################
### Readwise Access Token ###
#############################

token = "" # ENTER YOUR TOKEN HERE 
# Retrieve from https://readwise.io/access_token
# e.g. "abc123dEf45Gh6"

###########################################################
### Specify target directory for new markdown notes i.e. Obsidian vault ###
########################################################### 

targetDirectory = "" # ENTER VALID DIRECTORY PATH HERE
# e.g. "/Users/johnsmith/Dropbox/Obsidian/Vault" on Mac or "\\Users\\johnsmith\\Dropbox\\Obsidian\\Vault" on Windows

#######################################################
### Specify custom fields and formatting (optional) ###
#######################################################

dateFrom = "" # "%Y-%m-%d" a.k.a "YYYY-MM-DD" format only! Get highlights AFTER this date only. 
# If set to "" or None, the script will default to 'last successful script run' date from readwiseGET.log (if exists), or it will fetch all readwise resources
# e.g. "2020-01-01"

dateFormat = "%y%m%d %A" # Default is "%Y-%m-%d" a.k.a "YYYY-MM-DD"
# This is the date format to display "last updated" fields

splitCategoriesIntoFolders = False # This will split highlights into separate folders according to their source category e.g. book/tweet/article/podcast

includeCoverImage_note = True # This will add a "cover image" (if exists) below the title 

includeDateAsComment_note = True # This will add the note "last updated" field below the title in "%%" block

includeDateAsComment_highlight = False # This will add the highlight "last updated" field below the highlight in "%%" block

includeiFrameForPodcast_highlight = True # This will add an iFrame with the "podcast url" below the highlight

#########################################
### Data for fetching tags (optional) ###
#########################################

# Readwise API endpoints seem to exclude tags, so I've added functionality to fetch tags from new or updated highlights. 
# Note: this uses Selenium to web scrape data from your readwise profile. Please use with caution!
# If any of these variables are set to "" or None, no tags will be fetched. 

email = "" # ENTER YOUR EMAIL HERE
# e.g. "johnsmith@gmail.com"

pwd = "" # ENTER YOUR PASSWORD HERE 
# e.g. "J0HNSM1TH_312"

chromedriverDirectory = "" # ENTER VALID PATH TO CHROMEDRIVER 
# e.g. "/Users/johnsmith/Downloads/chromedriver.exe" on Mac or "\\Users\\johnsmith\\Downloads\\chromedriver.exe" on Windows
# Read more here https://chromedriver.chromium.org/
