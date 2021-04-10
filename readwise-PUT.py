##############################
### Import python packages ###
##############################

import requests, os, io, sys, shutil, django, json, time, re
from json import JSONEncoder
from json.decoder import JSONDecodeError
from dateutil.relativedelta import relativedelta
from dateutil.parser import parse
from datetime import date, datetime, timedelta
from itertools import groupby
from operator import itemgetter

##########################
### Log script outputs ###
##########################

old_stdout = sys.stdout

old_cwd = os.getcwd()

startTime = datetime.now()

def logDateTimeOutput(message):
    log_file = open('readwise-directory.log', 'a')
    sys.stdout = log_file
    now = datetime.now()
    print(now.strftime("%Y-%m-%dT%H:%M:%SZ") + " " + str(message))
    sys.stdout = old_stdout
    log_file.close()

logDateTimeOutput("'readwise-PUT.py' script started")

#######################################################
### Import variables from file in another directory ###
#######################################################

# Import all variables from readwiseMetadata file
print('Importing variables from readwiseMetadata...')
from readwiseMetadata import token, targetDirectory, dateFrom, dateFormat
# from readwiseMetadata import *

#############################
### Create core functions ###
#############################

# Check if a directory variable is defined and formatted correctly
# If TRUE, add a new system path for that. If FALSE, do nothing.
def insertPath(directory):
    if directory == "" or directory is None:
        return
    else:
        try:
            sys.path.insert(1, directory)
        except ValidationError as e:
            logDateTimeOutput(e)

# Check if a 'dateFrom' variable is defined and formatted correctly
# If TRUE, convert to UTC format. If FALSE, default to dateLastScriptRun
def convertDateFromToUtcFormat(dateFrom):
    if str(dateFrom) == "" or str(dateFrom) == "None":
        lastScriptRunDateMatchingString = "'readwise-PUT.py' script complete"
        try: 
            for line in reversed(list(open('readwise-directory.log', 'r').readlines())):
                if lastScriptRunDateMatchingString in line:
                    dateLastScriptRun = str(line.replace(lastScriptRunDateMatchingString, '')).rstrip("\n")
                    dateLastScriptRun = dateLastScriptRun.rstrip()
                    dateFrom = dateLastScriptRun
                    message = 'Last successful script run = "' + str(dateFrom) + '" used as dateFrom in query string'
                    # logDateTimeOutput(message)
                    print(message)
                    return dateFrom
                elif lastScriptRunDateMatchingString not in line:
                    continue
                else:
                    dateFrom = "1970-01-01T00:00:00Z"
                    message = "'readwise-PUT.py' not yet run. Default to check all files in targetDirectory"
                    # logDateTimeOutput(message)
                    print(message)
                    return dateFrom
        except IOError:
            dateFrom = "1970-01-01T00:00:00Z"
            message = 'Failed to read readwise-directory.log file. Default to check all files in targetDirectory'
            logDateTimeOutput('Failed to read readwise-directory.log file. Default to check all files in targetDirectory')
            print(message)
            return dateFrom
    elif str(dateFrom) != "" or str(dateFrom) != "None":
        try:
            parse(dateFrom, fuzzy = False)
            dateFrom = datetime.strptime(dateFrom, '%Y-%m-%d')
            dateFrom = dateFrom.strftime("%Y-%m-%dT%H:%M:%SZ")
            message = 'Date from = "' + str(dateFrom) + '" from readwiseMetadata used in query string'
            logDateTimeOutput(message)
            print(message)
            return dateFrom
        except ValueError:
            message = "Incorrect date format. It should be '%Y-%m-%d' a.k.a 'YYYY-MM-DD'"
            logDateTimeOutput(message)
            print(message)
    else:
        dateFrom = "1970-01-01T00:00:00Z"
        message = 'No dateFrom variable defined in readwiseMetadata or readwise-directory.log. Default to check all files in targetDirectory'
        logDateTimeOutput(message)
        print(message)
        return dateFrom

# Check dateFrom variable
print('Checking if a valid dateFrom variable is defined in readwiseMetadata...')
dateFrom = convertDateFromToUtcFormat(dateFrom)

# Check targetDirectory variable is valid
print('Checking if a valid targetDirectory variable is defined in readwiseMetadata...')
insertPath(targetDirectory)

abspath = os.path.realpath(__file__) # Create absolute path for this file 

# Create sourceDirectory variable from absolute path for this file
print('Creating sourceDirectory variable from absolute path for this file...')
sourceDirectory = os.path.dirname(abspath) # Create variable defining the directory name
# sourceDirectory = os.getcwd()
print(str(sourceDirectory) + ' directory variable defined')

##############################
### Create other functions ###
##############################

# Clean-up book metadata fields to split keys and values e.g. Title: Lord of the Rings
def metadataSplitKeyValue(field):
    keyValueList = field.split(": ") # Split into keys and values
    keyValueList = [x for x in keyValueList if x != ""] # Remove blank spaces
    fieldValue = keyValueList[1]
    return fieldValue

# Determine if block of text is a highlight block or not
def isHighlightBlockWithMultipleNewLinesFunction(field): 
    if field.startswith("\n\n> ") and "\n\n^" in field:
        return True
    else:
        return False

# Determine if cover_image_url defined or not
def isCoverImageUrlDefinedFunction():
    if str(cover_image_url) == "None" or str(cover_image_url) == "":
        return False
    else:
        return True

print('Extracting highlight data from markdown files in ' + str(targetDirectory))

# Function to extract raw highlight into usable fields for manipulating as JSON
def extractHighlight(field):
    # Create empty fields for elements within highlight JSON object
    highlight = {}
    highlight["id"] = ""
    highlight["text"] = ""
    highlight["note"] = ""
    highlight["tags"] = []
    highlight["location"] = ""
    highlight["location_type"] = ""
    highlight["url"] = "None"
    highlight["highlighted_at"] = ""
    highlight["updated"] = ""
    highlight["comments"] = ""
    highlight["references"] = ""
    highlightKeywords = ["**Note:** ", "**Tags:** ", "**References:** ", "<iframe", "%% "]
    highlightKeywordsOrder = []
    highlightKeywordsOrderSorted = []
    highlightKeywordsToSplit = []
    highlightKeywordsToSplitSorted = []
    listOfHeadings = ['# ', '## ', '### ', '#### ', '##### ', '###### ']
    note = ""
    isHighlightBlockWithMultipleNewLines = True
    isHighlightBlockWithMultipleNewLines = isHighlightBlockWithMultipleNewLinesFunction(field)
    try:
        if isHighlightBlockWithMultipleNewLines == True: # Highlight text in quote blocks with highlight_id separated by new line
            highlightRawSplit = field.split("\n\n")
            # Remove blank of invalid fields from list
            highlightRawSplit = [x for x in highlightRawSplit if x != ""]
            highlightRawSplit = [x for x in highlightRawSplit if x != "\n"]
            # If highlight block contains more than just "> text\n> " and "^ id"
            if len(highlightRawSplit) > 2: 
                # Check if there are any keywords in the block of text
                for n in range(len(highlightKeywords)):
                    if highlightKeywords[n] in field:
                        highlightKeywordsOrder.append(field.find(highlightKeywords[n]))
                        highlightKeywordsOrderSorted = highlightKeywordsOrder.copy()
                        highlightKeywordsOrderSorted.sort()
                        highlightKeywordsToSplit.append(highlightKeywords[n])
                # If no keywords are present in the block of text, then there are multiple "\n\n" in the highlight block
                if len(highlightKeywordsToSplit) == 0:
                    id = highlightRawSplit[-1].replace("^", "") # Remove Obsidian block ref quote character
                    highlight["id"] = id # Append highlight id to JSON object
                    text = "\n\n".join(highlightRawSplit[0:-1])
                    text = text.replace("> ", "") # Remove quote marks from strings with characters
                    text = text.replace("\n\\\n", "\n\n") # Remove quote marks from empty strings in the block of text
                    text = text.replace("\n\\", "\n") # Remove quote marks from empty strings at the end of the block of text
                    text = text.lstrip() # Remove special characers from start of string
                    text = text.rstrip() # Remove special characers from end of string
                    # Replace Obsidian's highlight separators with Readwise's format
                    if "==" in text:
                        text = text.replace("==", "__")
                    # Remove # character for h1-h6 headings
                    for h in range(len(listOfHeadings)):
                        if text.startswith(listOfHeadings[h]):
                            text = text[len(listOfHeadings[h]):]
                            # v2.0 - if h1-h6 tag not specified, pre-pend to "note" field
                    highlight["text"] = text # Append highlight text to JSON object
                    highlights.append(highlight)
                # If there are keywords present in the block of text, then use string operations to extract the substrings between the words
                # e.g. if 'note', 'tags' and 'references' are present (in that order), extract substring between 'note' and 'tags', then 'tags' and 'references', etc.
                else:
                    # First, extract the "> text\n> " and "^ id" components
                    for c in range(len(highlightKeywordsOrderSorted)):
                        pos = highlightKeywordsOrder.index(highlightKeywordsOrderSorted[c])
                        highlightKeywordsToSplitSorted.append(highlightKeywordsToSplit[pos])
                    startWord = highlightKeywordsToSplitSorted[0] # First matching keyword, e.g. "**Tags:** "
                    startIndex = 1 # By default, assume that the keyword is one item after the main block of text
                    # Find the index where the first matching keyword is returned from the list, e.g. "**Tags:** " at index position 4
                    for t in range(len(highlightRawSplit)):
                        if highlightKeywordsToSplitSorted[0] in str(highlightRawSplit[t]):
                            startIndex = t                  
                    id = highlightRawSplit[startIndex-1].replace("^", "") # Remove Obsidian block ref quote character
                    highlight["id"] = id # Append highlight id to JSON object
                    text = "\n\n".join(highlightRawSplit[0:startIndex-1])
                    text = text.replace("> ", "") # Remove quote marks from strings with characters
                    text = text.replace("\n\\\n", "\n\n") # Remove quote marks from empty strings in the block of text
                    text = text.replace("\n\\", "\n") # Remove quote marks from empty strings at the end of the block of text
                    text = text.lstrip() # Remove special characers from start of string
                    text = text.rstrip() # Remove special characers from end of string
                    # Replace Obsidian's highlight separators with Readwise's format
                    if "==" in text:
                        text = text.replace("==", "__")
                    # Remove # character for h1-h6 headings
                    for h in range(len(listOfHeadings)):
                        if text.startswith(listOfHeadings[h]):
                            text = text[len(listOfHeadings[h]):]
                            # v2.0 - if h1-h6 tag not specified, pre-pend to "note" field
                    highlight["text"] = text # Append highlight text to JSON object
                    # Now, extract the substrings between keywords in the block of text
                    highlightRawSplit_extra = "\n\n".join(highlightRawSplit[startIndex:])
                    for w in range(len(highlightKeywordsToSplitSorted)):
                        startWord = highlightKeywordsToSplitSorted[w]
                        startIndex = highlightKeywords.index(highlightKeywordsToSplitSorted[w])
                        try:
                            endWord = highlightKeywordsToSplitSorted[w+1]
                            stringBetweenWords = highlightRawSplit_extra[highlightRawSplit_extra.find(startWord)+len(startWord):highlightRawSplit_extra.find(endWord)]
                            stringBetweenWords = stringBetweenWords.rstrip()
                            if startIndex == 0:
                                highlight["note"] = stringBetweenWords
                            elif startIndex == 1:
                                tagsSplit = stringBetweenWords.split(" ")
                                for t in range(len(tagsSplit)):
                                    highlight["tags"].append(tagsSplit[t])
                                # v2.0 - DONE - append .tag1 .tag2 to top of note
                            elif startIndex == 2:
                                # If multiple urls, extract first url into highlight "url"
                                # If multiple references, append to 'references' field to be stored in JSON but not sent to readwise
                                referencesSplit = stringBetweenWords.split(" ") # Split words in 'references' field by spaces
                                referencesSplitUrls = []
                                if len(referencesSplit) > 1:
                                    for r in range(len(referencesSplit)):
                                        try:
                                            if "http" in str(referencesSplit[r]):
                                                referencesSplitUrls.append(str(referencesSplit[r]))
                                            else:
                                                pass
                                        except IndexError:
                                            pass
                                    if len(referencesSplitUrls) == 0:
                                        highlight["url"] = "None" # No URLs found in 'references' block
                                        highlight["references"] = str(stringBetweenWords)
                                    else:
                                        highlight["url"] = str(referencesSplitUrls[0]) # Get the first url from list in 'references'
                                        del referencesSplit[referencesSplit.index(referencesSplitUrls[0])] # Remove first url from list
                                        highlight["references"] = " ".join(referencesSplit) # Append remaining elements from 'references' list to highlight object
                                else: # If there is only one word in the 'references' field, check if it's a "url" otherwise just store it in JSON
                                    if "http" in stringBetweenWords: # If "url" defined, in 'references' field, append to highlight object
                                        highlight["url"] = str(stringBetweenWords) 
                                    else: # If no "url" defined, store in JSON but don't send to readwise
                                        highlight["url"] = "None"
                                        highlight["references"] = str(stringBetweenWords)
                            # Ignore iframe lines
                            elif startIndex == 3:
                                pass
                            # If 'comments', append to highlight object
                            elif startIndex == 4:
                                stringBetweenWords = stringBetweenWords.replace("%%", "")
                                stringBetweenWords = stringBetweenWords.rstrip()
                                highlight["comments"] = stringBetweenWords
                        except IndexError:
                            stringBetweenWords = highlightRawSplit_extra.rsplit(startWord, 1)[-1]
                            stringBetweenWords = stringBetweenWords.replace("%%", "")
                            stringBetweenWords = stringBetweenWords.rstrip()
                            if startIndex == 0:
                                highlight["note"] = stringBetweenWords
                            elif startIndex == 1:
                                tagsSplit = stringBetweenWords.split(" ")
                                for t in range(len(tagsSplit)):
                                    highlight["tags"].append(tagsSplit[t])
                                # Append .tag1 .tag2 to top of note
                            elif startIndex == 2:
                                # If multiple urls, extract first url into highlight "url"
                                # If multiple references, append to 'references' field to be stored in JSON but not sent to readwise
                                referencesSplit = stringBetweenWords.split(" ") # Split words in 'references' field by spaces
                                referencesSplitUrls = []
                                if len(referencesSplit) > 1:
                                    for r in range(len(referencesSplit)):
                                        try:
                                            if "http" in str(referencesSplit[r]):
                                                referencesSplitUrls.append(str(referencesSplit[r]))
                                            else:
                                                pass
                                        except IndexError:
                                            pass
                                    if len(referencesSplitUrls) == 0:
                                        highlight["url"] = "None" # No URLs found in 'references' block
                                        highlight["references"] = str(stringBetweenWords)
                                    else:
                                        highlight["url"] = str(referencesSplitUrls[0]) # Get the first url from list in 'references'
                                        del referencesSplit[referencesSplit.index(referencesSplitUrls[0])] # Remove first url from list
                                        highlight["references"] = " ".join(referencesSplit) # Append remaining elements from 'references' list to highlight object
                                else: # If there is only one word in the 'references' field, check if it's a "url" otherwise just store it in JSON
                                    if "http" in stringBetweenWords: # If "url" defined, in 'references' field, append to highlight object
                                        highlight["url"] = str(stringBetweenWords) 
                                    else: # If no "url" defined, store in JSON but don't send to readwise
                                        highlight["url"] = "None"
                                        highlight["references"] = str(stringBetweenWords)                                
                            # Ignore iframe lines
                            elif startIndex == 3:
                                pass
                            # If 'comments', append to highlight object
                            elif startIndex == 4:
                                stringBetweenWords = stringBetweenWords.replace("%%", "")
                                stringBetweenWords = stringBetweenWords.rstrip()
                                highlight["comments"] = stringBetweenWords
                    highlights.append(highlight)
            else:
                id = highlightRawSplit[1].replace("^", "") # Remove Obsidian block ref quote character
                highlight["id"] = id # Append highlight id to JSON object
                text = highlightRawSplit[0]
                text = text.replace("> ", "") # Remove quote marks from strings with characters
                text = text.replace("\n\\\n", "\n\n") # Remove quote marks from empty strings in the block of text
                text = text.replace("\n\\", "\n") # Remove quote marks from empty strings at the end of the block of text
                text = text.lstrip() # Remove special characers from start of string
                text = text.rstrip() # Remove special characers from end of string
                # Replace Obsidian's highlight separators with Readwise's format
                if "==" in text:
                    text = text.replace("==", "__")
                # Remove # character for h1-h6 headings
                for h in range(len(listOfHeadings)):
                    if text.startswith(listOfHeadings[h]):
                        text = text[len(listOfHeadings[h]):]
                        # v2.0 - if h1-h6 tag not specified, pre-pend to "note" field
                highlight["text"] = text # Append highlight text to JSON object
                highlights.append(highlight)
        else:
            # If block of text is not multiline, the 'text' and 'id' block reference will be on the same line
            try:
                highlightRawSplit = field.split("\n\n")
                # Remove blank entries from list using filter
                highlightRawSplit = [x for x in highlightRawSplit if x != ""]
                # Get id from text by extracting characters from the end of the string until "^" 
                # See https://stackoverflow.com/a/48852705/14351071
                text = ""
                delimiter = ""
                id = ""
                text, delimiter, id = highlightRawSplit[0].rpartition(' ^') # e.g. "...some text ^1234" >> "...some text" "^" "1234"
                highlight["id"] = id # Append highlight id to JSON object
                if "==" in text:
                    text = text.replace("==", "__")
                # Remove # for h1-h6 headings
                for h in range(len(listOfHeadings)):
                    if text.startswith(listOfHeadings[h]):
                        text = text[len(listOfHeadings[h]):]
                        # v2.0 - if h1-h6 tag not specified, pre-pend to "note" field
                text = text.lstrip() # Remove special characers from start of string
                text = text.rstrip() # Remove special characers from end of string                
                highlight["text"] = text # Append highlight text to JSON object
                # Get note / tags / references if defined, otherwise pass
                if len(highlightRawSplit) > 2: # If there were "\n\n" characters in the note fields
                    del highlightRawSplit[0]
                    highlightRawSplit_extra = "\n\n".join(highlightRawSplit)
                else:
                    highlightRawSplit_extra = highlightRawSplit[1]
                # Extract highlightKeywordsToSplit from string
                for n in range(len(highlightKeywords)):
                    if highlightKeywords[n] in field:
                        highlightKeywordsOrder.append(highlightRawSplit_extra.find(highlightKeywords[n]))
                        highlightKeywordsOrderSorted = highlightKeywordsOrder.copy()
                        highlightKeywordsOrderSorted.sort()
                        highlightKeywordsToSplit.append(highlightKeywords[n])
                if len(highlightKeywordsToSplit) == 0:
                    pass
                else:
                    # Extract strings between keywords, and append to highlights object
                    for w in range(len(highlightKeywordsToSplitSorted)):
                        startWord = highlightKeywordsToSplitSorted[w]
                        startIndex = highlightKeywords.index(highlightKeywordsToSplitSorted[w])
                        try:
                            endWord = highlightKeywordsToSplitSorted[w+1]
                            stringBetweenWords = highlightRawSplit_extra[highlightRawSplit_extra.find(startWord)+len(startWord):highlightRawSplit_extra.find(endWord)]
                            stringBetweenWords = stringBetweenWords.rstrip()
                            if startIndex == 0:
                                highlight["note"] = stringBetweenWords
                            elif startIndex == 1:
                                tagsSplit = stringBetweenWords.split(" ")
                                for t in range(len(tagsSplit)):
                                    highlight["tags"].append(tagsSplit[t])
                                # Append .tag1 .tag2 to top of note
                            elif startIndex == 2:
                                # If multiple urls, extract first url into highlight "url"
                                # If multiple references, append to 'references' field to be stored in JSON but not sent to readwise
                                referencesSplit = stringBetweenWords.split(" ") # Split words in 'references' field by spaces
                                referencesSplitUrls = []
                                if len(referencesSplit) > 1:
                                    for r in range(len(referencesSplit)):
                                        try:
                                            if "http" in str(referencesSplit[r]):
                                                referencesSplitUrls.append(str(referencesSplit[r]))
                                            else:
                                                pass
                                        except IndexError:
                                            pass
                                    if len(referencesSplitUrls) == 0:
                                        highlight["url"] = "None" # No URLs found in 'references' block
                                        highlight["references"] = str(stringBetweenWords)
                                    else:
                                        highlight["url"] = str(referencesSplitUrls[0]) # Get the first url from list in 'references'
                                        del referencesSplit[referencesSplit.index(referencesSplitUrls[0])] # Remove first url from list
                                        highlight["references"] = " ".join(referencesSplit) # Append remaining elements from 'references' list to highlight object
                                else: # If there is only one word in the 'references' field, check if it's a "url" otherwise just store it in JSON
                                    if "http" in stringBetweenWords: # If "url" defined, in 'references' field, append to highlight object
                                        highlight["url"] = str(stringBetweenWords) 
                                    else: # If no "url" defined, store in JSON but don't send to readwise
                                        highlight["url"] = "None"
                                        highlight["references"] = str(stringBetweenWords)
                            elif startIndex == 3:
                                pass
                            elif startIndex == 4:
                                # If comment, append new key:value to highlights object
                                stringBetweenWords = stringBetweenWords.replace("%%", "")
                                stringBetweenWords = stringBetweenWords.rstrip()
                                highlight["comments"] = stringBetweenWords
                            """
                            else:
                                ... # e.g. if accidentally the "---" characters were missed and two highlights appear as one
                            """
                        except IndexError:
                            stringBetweenWords = highlightRawSplit_extra.rsplit(startWord, 1)[-1]
                            stringBetweenWords = stringBetweenWords.replace("%%", "")
                            stringBetweenWords = stringBetweenWords.rstrip()
                            if startIndex == 0:
                                highlight["note"] = stringBetweenWords
                            elif startIndex == 1:
                                tagsSplit = stringBetweenWords.split(" ")
                                for t in range(len(tagsSplit)):
                                    highlight["tags"].append(tagsSplit[t])
                                # Append .tag1 .tag2 to top of note
                            elif startIndex == 2:
                                # If multiple urls, extract first url into highlight "url"
                                # If multiple references, append to 'references' field to be stored in JSON but not sent to readwise
                                referencesSplit = stringBetweenWords.split(" ") # Split words in 'references' field by spaces
                                referencesSplitUrls = []
                                if len(referencesSplit) > 1:
                                    for r in range(len(referencesSplit)):
                                        try:
                                            if "http" in str(referencesSplit[r]):
                                                referencesSplitUrls.append(str(referencesSplit[r]))
                                            else:
                                                pass
                                        except IndexError:
                                            pass
                                    if len(referencesSplitUrls) == 0:
                                        highlight["url"] = "None" # No URLs found in 'references' block
                                        highlight["references"] = str(stringBetweenWords)
                                    else:
                                        highlight["url"] = str(referencesSplitUrls[0]) # Get the first url from list in 'references'
                                        del referencesSplit[referencesSplit.index(referencesSplitUrls[0])] # Remove first url from list
                                        highlight["references"] = " ".join(referencesSplit) # Append remaining elements from 'references' list to highlight object
                                else: # If there is only one word in the 'references' field, check if it's a "url" otherwise just store it in JSON
                                    if "http" in stringBetweenWords: # If "url" defined, in 'references' field, append to highlight object
                                        highlight["url"] = str(stringBetweenWords) 
                                    else: # If no "url" defined, store in JSON but don't send to readwise
                                        highlight["url"] = "None"
                                        highlight["references"] = str(stringBetweenWords)
                            elif startIndex == 3:
                                pass
                            # If comment, append new key:value to highlights object
                            elif startIndex == 4:
                                stringBetweenWords = stringBetweenWords.replace("%%", "")
                                stringBetweenWords = stringBetweenWords.rstrip()
                                highlight["comments"] = stringBetweenWords
                highlights.append(highlight)
            except IndexError:
                return
    except IndexError:
        return

def metadataDateFormatCheck(inputVariable, default):
    if inputVariable == "" or inputVariable is None:
        return default
    else: 
        try:
            today = datetime.today().strftime(inputVariable) # Check format is valid when applied to today's date field
            parse(today, fuzzy = False)
            return inputVariable
        except ValueError:
            message = "Incorrect date format. Default format will be used = '%Y-%m-%d' a.k.a 'YYYY-MM-DD'"
            logDateTimeOutput(message)
            print(message)
            return default

dateFormat = metadataDateFormatCheck(dateFormat, "%Y-%m-%d")

######################################################
### Manipulating book and highlight data with JSON ###
######################################################

new_articles = []
new_books = []
new_podcasts = []
new_supplementals = []
new_tweets = []

new_categoriesObject = [new_articles, new_books, new_podcasts, new_supplementals, new_tweets] # type(old_categoriesObject[0]) = 'dictionary'

categoriesObjectNames = ["articles", "books", "podcasts", "supplementals", "tweets"] # type(categoriesObjectNames[0]) = 'string'

# Loop through markdown files in a directory and append full path names to list
full_listOfMarkdownFiles = []
for file in os.listdir(targetDirectory):
    filename = os.fsdecode(file)
    if filename.endswith(".md"): 
        full_listOfMarkdownFiles.append(os.path.join(targetDirectory, filename))
        continue
    else:
        continue

print('Extracting list of files modified after ' + str(dateFrom))

# Extract only files which were modified after a specified date
subset_listOfMarkdownFiles = []
for f in range(len(full_listOfMarkdownFiles)):
    lastModifiedTime = os.path.getmtime(full_listOfMarkdownFiles[f])
    lastModifiedDate = datetime.fromtimestamp(lastModifiedTime).strftime("%Y-%m-%dT%H:%M:%SZ")
    if dateFrom < lastModifiedDate:
        subset_listOfMarkdownFiles.append(full_listOfMarkdownFiles[f])

full_old_articles = {}
full_old_books = {}
full_old_podcasts = {}
full_old_supplementals = {}
full_old_tweets = {}

full_old_categoriesObject = [full_old_articles, full_old_books, full_old_podcasts, full_old_supplementals, full_old_tweets] # type(old_categoriesObject[0]) = 'dictionary'

subset_old_articles = []
subset_old_books = []
subset_old_podcasts = []
subset_old_supplementals = []
subset_old_tweets = []

subset_old_categoriesObject = [subset_old_articles, subset_old_books, subset_old_podcasts, subset_old_supplementals, subset_old_tweets] # type(old_categoriesObject[0]) = 'dictionary'

# Load original JSON files into list of 'old_categoriesObjects'
def loadBookDataFromJsonToObject():
    for i in range(len(categoriesObjectNames)):
        try: 
            with open(sourceDirectory + "/readwiseCategories/" + categoriesObjectNames[i] + ".json", 'r') as infile:
                try:
                    full_old_categoriesObject[i] = json.load(infile) # list of categories objects with up-to-date data loaded from JSON files
                    message = str(len(full_old_categoriesObject[i])) + ' books loaded from ' + str(categoriesObjectNames[i]) + '.json'
                    logDateTimeOutput(message)
                except JSONDecodeError:
                    full_old_categoriesObject[i] = []
        except FileNotFoundError:
            full_old_categoriesObject[i] = []

# Load existing readwise data from JSON files into old_categoriesObject
loadBookDataFromJsonToObject()

###########################################################################################
### Loop through modified files and extract book and highlight data to new JSON objects ###
###########################################################################################

for m in range(len(subset_listOfMarkdownFiles)):
    text = ""
    try:
        with open(subset_listOfMarkdownFiles[m], "r") as input_file:
            text = input_file.read()
            textNew = []
            textSplit = text.split("---")
            # Remove blank or invalid entries from list using filter
            textSplit = [x for x in textSplit if x != ""]
            textSplit = [x for x in textSplit if x != "\n"]
            textSplit = [x for x in textSplit if x != "\n\n"]
            # Get book metadata list from YAML
            bookMetadataFromYaml = textSplit[0].split("\n")
            # Remove blank entries from list using filter
            bookMetadataFromYaml = [x for x in bookMetadataFromYaml if x != ""]
            # Split book metadata fields from bookMetadataFromYaml list
            # Enhancement: Check that string contains field key (e.g. "title" in string), otherwise there might be incorrect mappings
            title = bookMetadataFromYaml[0]
            author = bookMetadataFromYaml[1]
            source = bookMetadataFromYaml[2]
            num_highlights = bookMetadataFromYaml[3]
            lastUpdated = bookMetadataFromYaml[4]
            book_url = bookMetadataFromYaml[5]
            book_id = bookMetadataFromYaml[6]
            # Get source_url if defined in bookMetadataFromYaml, otherwise pass
            try: 
                source_url = bookMetadataFromYaml[7]
            except:
                source_url = ""
                pass
            # Get cover_image_url if defined in text, otherwise pass
            try:
                cover_image_url = bookMetadataFromYaml[8]
            except:
                cover_image_url = ""
                pass
            # Extract book metadata fields into defined variables
            book_id = metadataSplitKeyValue(book_id)
            title = metadataSplitKeyValue(title)
            author = metadataSplitKeyValue(author)
            num_highlights = metadataSplitKeyValue(num_highlights)
            book_url = metadataSplitKeyValue(book_url)
            # Get source_url if defined, otherwise pass
            try:
                source_url = metadataSplitKeyValue(source_url)
            except:
                source_url = ""
                pass
            # Get cover_image_url if defined, otherwise pass
            try:
                cover_image_url = metadataSplitKeyValue(cover_image_url)
            except:
                cover_image_url = ""
                pass
            # Extract source category from string
            source = metadataSplitKeyValue(source) # e.g. [readwise, tweets]
            for n in range(len(categoriesObjectNames)):
                if categoriesObjectNames[n] in source:
                    source = categoriesObjectNames[n]
            # Convert 'lastUpdated' into UTC date string
            lastUpdated = metadataSplitKeyValue(lastUpdated) # e.g. [[210101 Monday]]
            lastUpdated = lastUpdated.replace("[", "") # e.g. 210101 Monday]]
            lastUpdated = lastUpdated.replace("]", "") # .g. 210101 Monday
            lastUpdated = datetime.strptime(lastUpdated, dateFormat).strftime("%Y-%m-%dT%H:%M:%SZ")
            # Temporarily update the 'lastUpdated' field to the last modified date/time of the file
            # This will be used at the end to update the 'updated' field of modified highlights
            lastModifiedTime = os.path.getmtime(subset_listOfMarkdownFiles[m])
            lastModifiedDate = datetime.fromtimestamp(lastModifiedTime).strftime("%Y-%m-%dT%H:%M:%SZ")
            lastUpdated = lastModifiedDate
            # Add book metadata fields to JSON object
            bookMetadataValues = { "book_id" : book_id, "title" : title, "author" : author, "source" : source, "url" : book_url, "num_highlights" : num_highlights, "updated" : lastUpdated }
            # Append source_url if defined, otherwise pass
            try:
                if str(cover_image_url) == "":
                    pass
                else:
                    bookMetadataValues["cover_image_url"] = cover_image_url
            except:
                pass
            # Append cover_image_url if defined, otherwise pass
            try:
                if str(source_url) == "":
                    pass
                else:
                    bookMetadataValues["source_url"] = source_url
            except:
                pass
            # Create boolean to check if markdown file contains a cover_image_url. Default = True.
            isCoverImageUrlDefined = True
            # Change boolean if cover_image_url is not defined, otherwise pass
            isCoverImageUrlDefined = isCoverImageUrlDefinedFunction()
            # Create list to append highlights from markdown file into
            highlights = []
            # Extract highlights from index = 2 (if no cover_image_url defined), otherwise from index = 3
            if isCoverImageUrlDefined == True:
                for i in range(3, len(textSplit)):
                    extractHighlight(textSplit[i])
            else:
                for k in range(2, len(textSplit)):
                    extractHighlight(textSplit[k])
            # Add highlights list to 'bookMetadataValues'
            try:
                bookMetadataValues["highlights"] = highlights
            except:
                pass
            # Append book and highlight data to the relevant category object
            indexCategory = categoriesObjectNames.index(source) # Identify which position the 'category' corresponds to within the list of category objects
            new_categoriesObject[indexCategory].append(bookMetadataValues)
    except IndexError:
        break

###########################################
### Compare new and original JSON files ###
###########################################

# Use 'book_id' from list of modified files to fetch the index of the book in 'old_categoriesObject'
# Compare the highlights, and track the changes to "text" and "note"
# If there are new tags, pre-pend them to the "note" field
listCategories = [item for category in new_categoriesObject for item in category]

listOfModifiedHighlights = []

for l in range(len(listCategories)):
    index = list(map(itemgetter('book_id'), listCategories)).index(str(listCategories[l]['book_id']))
    source = listCategories[index]['source'] # Get the 'category' of the corresponding 'book_id' from the grouped highlights
    indexCategory = categoriesObjectNames.index(source) # Identify which position the 'category' corresponds to within the list of category objects
    indexBook = list(map(itemgetter('book_id'), full_old_categoriesObject[indexCategory])).index(str(listCategories[l]['book_id'])) # Identify which position the 'book_id' corresponds to within the category object
    book_id = full_old_categoriesObject[indexCategory][indexBook]['book_id']
    title = full_old_categoriesObject[indexCategory][indexBook]['title']
    author = full_old_categoriesObject[indexCategory][indexBook]['author']
    source = full_old_categoriesObject[indexCategory][indexBook]['source']
    num_highlights = full_old_categoriesObject[indexCategory][indexBook]['num_highlights']
    updated = full_old_categoriesObject[indexCategory][indexBook]['updated']
    cover_image_url = full_old_categoriesObject[indexCategory][indexBook]['cover_image_url']
    url = full_old_categoriesObject[indexCategory][indexBook]['url']
    source_url = full_old_categoriesObject[indexCategory][indexBook]['source_url']
    highlights = full_old_categoriesObject[indexCategory][indexBook]['highlights']
    bookValues = { "book_id" : book_id, "title" : title, "author" : author, "source" : source, "url" : book_url, "source_url": source_url, "cover_image_url": cover_image_url, "num_highlights" : num_highlights, "updated" : lastUpdated, "highlights": highlights }
    subset_old_categoriesObject[indexCategory].append(bookValues)

try:
    try:
        for l in range(len(new_categoriesObject)):
            for b in range(len(new_categoriesObject[l])):
                # Treat every highlight as if it was modified on the 'lastUpdated' date, but this will only take effect for modified highlights
                # Convert lastUpdated into UTC date string
                try:
                    for h in range(len(new_categoriesObject[l][b]['highlights'])):
                        payload = {}
                        modifiedHighlightIdAndpayload = []
                        if new_categoriesObject[l][b]['highlights'][h]['text'] != subset_old_categoriesObject[l][b]['highlights'][h]['text']:
                            subset_old_categoriesObject[l][b]['highlights'][h]['text'] = new_categoriesObject[l][b]['highlights'][h]['text']
                            payload['text'] = str(subset_old_categoriesObject[l][b]['highlights'][h]['text'])
                        if new_categoriesObject[l][b]['highlights'][h]['note'] != subset_old_categoriesObject[l][b]['highlights'][h]['note']:
                            subset_old_categoriesObject[l][b]['highlights'][h]['note'] = new_categoriesObject[l][b]['highlights'][h]['note']
                            payload['note'] = str(subset_old_categoriesObject[l][b]['highlights'][h]['note'])
                        if sorted(new_categoriesObject[l][b]['highlights'][h]['tags']) != sorted(subset_old_categoriesObject[l][b]['highlights'][h]['tags']):
                            tagsFromSet = set(new_categoriesObject[l][b]['highlights'][h]['tags']).union(set(subset_old_categoriesObject[l][b]['highlights'][h]['tags'])) - \
                            set(new_categoriesObject[l][b]['highlights'][h]['tags']).intersection(set(subset_old_categoriesObject[l][b]['highlights'][h]['tags']))
                            tagsFromSetSplit = [str(t).replace("#", ".") for t in tagsFromSet]
                            tagsFromSetSplit_join = " ".join(tagsFromSetSplit)
                            tagsFromSetMerged = set(new_categoriesObject[l][b]['highlights'][h]['tags']).union(set(subset_old_categoriesObject[l][b]['highlights'][h]['tags']))
                            tagsFromSetMerged = [str(t) for t in tagsFromSetMerged]
                            subset_old_categoriesObject[l][b]['highlights'][h]['tags'] = tagsFromSetMerged
                            if tagsFromSetSplit_join == "":
                                pass
                            else:
                                if str(new_categoriesObject[l][b]['highlights'][h]['note']) == "":
                                    noteWithTags = tagsFromSetSplit_join
                                    payload['note'] = str(noteWithTags)
                                else:
                                    noteWithTags = str(tagsFromSetSplit_join) + "\n\n" + str(new_categoriesObject[l][b]['highlights'][h]['note'])
                                    payload['note'] = str(noteWithTags)
                        try:
                            if new_categoriesObject[l][b]['highlights'][h]['comments'] != subset_old_categoriesObject[l][b]['highlights'][h]['comments']:
                                subset_old_categoriesObject[l][b]['highlights'][h]['comments'] = new_categoriesObject[l][b]['highlights'][h]['comments']
                        except KeyError:
                                subset_old_categoriesObject[l][b]['highlights'][h]['comments'] = new_categoriesObject[l][b]['highlights'][h]['comments']
                        try:
                            if new_categoriesObject[l][b]['highlights'][h]['references'] != subset_old_categoriesObject[l][b]['highlights'][h]['references']:
                                subset_old_categoriesObject[l][b]['highlights'][h]['references'] = new_categoriesObject[l][b]['highlights'][h]['references']
                        except KeyError:
                                subset_old_categoriesObject[l][b]['highlights'][h]['references'] = new_categoriesObject[l][b]['highlights'][h]['references']  
                        if payload == {}:
                            pass
                        elif payload != {}:
                            highlight_id = str(new_categoriesObject[l][b]['highlights'][h]['id'])
                            book_id = str(new_categoriesObject[l][b]['book_id'])
                            source = str(new_categoriesObject[l][b]['source'])
                            indexCategory = categoriesObjectNames.index(source)
                            indexBook = list(map(itemgetter('book_id'), full_old_categoriesObject[indexCategory])).index(book_id)
                            bookPosition = list(map(itemgetter('book_id'), listCategories)).index(str(new_categoriesObject[l][b]['book_id'])) # Identify position of 'highlights' block
                            highlightPosition = list(map(itemgetter('id'), listCategories[bookPosition]['highlights'])).index(highlight_id)
                            subset_old_categoriesObject[l][b]['highlights'][h]['updated'] = new_categoriesObject[l][b]['updated']
                            modifiedHighlightIdAndpayload.append(highlight_id)
                            modifiedHighlightIdAndpayload.append(payload)
                            modifiedHighlightIdAndpayload.append(indexCategory)
                            modifiedHighlightIdAndpayload.append(indexBook)
                            modifiedHighlightIdAndpayload.append(bookPosition)
                            modifiedHighlightIdAndpayload.append(highlightPosition)
                            listOfModifiedHighlights.append(modifiedHighlightIdAndpayload)
                        else:
                            pass
                except:
                    pass
    except IndexError:
        pass
except KeyError:
    pass

# Log the number of highlights to update
message = str(len(listOfModifiedHighlights)) + " modified highlights identified"
logDateTimeOutput(message)
print(message)

# If no highlights to update, end script and log result
if len(listOfModifiedHighlights) == 0:
    message = "'readwise-PUT.py' script complete"
    logDateTimeOutput(message)
    print(message)
    sys.exit()

########################
### Highlight UPDATE ###
########################

# Readwise REST API information = 'https://readwise.io/api_deets'
# Readwise endpoint = 'https://readwise.io/api/v2/highlights/<highlight id>/'

print("Patching highlight data to readwise...")

# Loop through "listOfModifiedHighlights" and trigger PATCH request with "payload" as parameter
counter = 0

try:
    for p in range(len(listOfModifiedHighlights)):
        id = str(listOfModifiedHighlights[p][0])
        payload = listOfModifiedHighlights[p][1]
        response = requests.patch(
            url="https://readwise.io/api/v2/highlights/" + id, # endpoint provided by https://readwise.io/api_deets
            headers={"Authorization": "Token " + token}, # token imported from readwiseAccessToken file
            data=payload # query string object
        )
        counter += 1
        print(str(counter) + '/' + str(len(listOfModifiedHighlights)) + ' highlights updated')
    message = str(counter) + " highlights updated in readwise."
    logDateTimeOutput(message)
    print(message)
except:
    message = "Error patching highlight data to readwise."
    logDateTimeOutput(message)
    print(message)

###################################################
### Append book and highlight data to JSON file ###
###################################################

message = "Storing updated highlight data in the origina JSON file"
logDateTimeOutput(message)
print(message)

listCategories = [item for category in subset_old_categoriesObject for item in category]

counter = 0
counter_articles = 0
counter_books = 0
counter_podcasts = 0
counter_supplementals = 0
counter_tweets = 0

counterIndexCategoryList = []

# Store modified highlights - with original metadata - to 'full_old_categoriesObject' object
for l in range(len(listOfModifiedHighlights)):
    indexCategory = listOfModifiedHighlights[l][2] # Identify which position the 'category' corresponds to within the list of category objects
    # Update the counter cooresponding to the highlight source e.g. article
    if indexCategory == 0:
        counter_articles += 1
    elif indexCategory == 1:
        counter_books += 1
    elif indexCategory == 2:
        counter_podcasts += 1
    elif indexCategory == 3:
        counter_supplementals += 1
    elif indexCategory == 4:
        counter_tweets += 1
    indexBook = listOfModifiedHighlights[l][3] # Identify which position the 'book_id' corresponds to within the category object
    bookPosition = listOfModifiedHighlights[l][4]
    highlightPosition = listOfModifiedHighlights[l][5]
    highlightValues = listCategories[bookPosition]['highlights'][highlightPosition]
    full_old_categoriesObject[indexCategory][indexBook]['highlights'][highlightPosition] = highlightValues
    counter += 1
    print(str(counter) + '/' + str(len(listOfModifiedHighlights)) + ' highlights stored in JSON object')

counterIndexCategoryList.append(counter_articles)
counterIndexCategoryList.append(counter_books)
counterIndexCategoryList.append(counter_podcasts)
counterIndexCategoryList.append(counter_supplementals)
counterIndexCategoryList.append(counter_tweets)

# Print updated 'full_old_categoriesObject' object to JSON files
for i in range(len(categoriesObjectNames)):
    try:
        with open(os.path.join(sourceDirectory, "readwiseCategories", categoriesObjectNames[i] + ".json"), 'w') as outfile:
            json.dump(full_old_categoriesObject[i], outfile, indent=4)
    except FileNotFoundError:
        with open(os.path.join(sourceDirectory, "readwiseCategories", categoriesObjectNames[i] + ".json"), 'x') as outfile:
            json.dump(full_old_categoriesObject[i], outfile, indent=4)

for c in range(len(counterIndexCategoryList)):
    if counterIndexCategoryList[c] == 0:
        pass
    else:
        message = str(counterIndexCategoryList[c]) + " highlights updated in " + categoriesObjectNames[c] + ".json"
        logDateTimeOutput(message)
        print(message)

###############################################
### Print script completion time to console ###
###############################################

message = "'readwise-PUT.py' script complete"
logDateTimeOutput(message)
print(message)
time.sleep(3) # Time to check the outputs of the script
sys.exit()
