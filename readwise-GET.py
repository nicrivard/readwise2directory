##############################
### Import python packages ###
##############################

import requests, os, io, sys, shutil, django, json, time
from datetime import datetime
from itertools import groupby 
from operator import itemgetter 
from unidecode import unidecode
from pathvalidate import ValidationError, validate_filepath
from pathlib import Path
from django.utils.text import slugify
from json import JSONEncoder
from json.decoder import JSONDecodeError
import pandas as pd
import numpy as np
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

##########################
### Log script outputs ###
##########################

old_stdout = sys.stdout

old_cwd = os.getcwd()

startTime = datetime.now()

def logDateTimeOutput(message):
    log_file = open('readwiseGET.log', 'a')
    sys.stdout = log_file
    now = datetime.now()
    print(now.strftime("%Y-%m-%dT%H:%M:%SZ") + " " + str(message))
    sys.stdout = old_stdout
    log_file.close()

logDateTimeOutput('Script started')

########################
### Create functions ###
########################

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
    if dateFrom == "" or dateFrom is None:
        lastScriptRunDateMatchingString = ' Script complete'
        try: 
            for line in reversed(list(open('readwiseGET.log', 'r').readlines())):
                if lastScriptRunDateMatchingString in line:
                    dateLastScriptRun = str(line.replace(lastScriptRunDateMatchingString, '')).rstrip("\n")
                    dateFrom = dateLastScriptRun
                    message = 'Last successful script run = "' + str(dateFrom) + '" used as dateFrom in query string'
                    logDateTimeOutput(message)
                    print(message)
                    return dateLastScriptRun
        except IOError:
            logDateTimeOutput('Failed to read readwiseGET.log file')
    elif dateFrom != "" or dateFrom is not None:
        try:
            dateFrom = datetime.strptime(dateFrom, '%Y-%m-%d')
            dateFrom = dateFrom.strftime("%Y-%m-%dT%H:%M:%SZ")
            message = 'Date from = "' + str(dateFrom) + '" from readwiseMetadata used in query string'
            logDateTimeOutput(message)
            print(message)
            return dateFrom
        except ValueError:
            logDateTimeOutput("Incorrect data format. It should be 'YYYY-MM-DD'")
    else:
        message = 'No dateFrom variable defined in readwiseMetadata or readwiseGET.log. Fetching all readwise highlights'
        logDateTimeOutput(message)
        print(message)

def replaceNoneInListOfDict(listOfDicts):
    for i in range(len(listOfDicts)):
        for k, v in iter(listOfDicts[i].items()):
            if k == 'location' and v is None:
                listOfDicts[i][k] = 0
            if k == 'location_type' and v == 'none':
                listOfDicts[i][k] = 'custom'

######################################################
### Manipulating book and highlight data with JSON ###
######################################################

# Load JSON file into list of categories objects
def loadBookDataFromJsonToObject():
    for i in range(len(categoriesObjectNames)):
        try: 
            with open(sourceDirectory + "/readwiseCategories/" + categoriesObjectNames[i] + ".json", 'r') as infile:
                try:
                    categoriesObject[i] = json.load(infile) # list of categories objects with up-to-date data loaded from JSON files
                    message = str(len(categoriesObject[i])) + ' books loaded from ' + str(categoriesObjectNames[i]) + '.json'
                    logDateTimeOutput(message)
                except JSONDecodeError:
                    categoriesObject[i] = []
        except FileNotFoundError:
            categoriesObject[i] = []

# Check if 'book_id' exists already. If no, append book data to the relevant category object
def appendBookDataToObject():
    newBooksCounter = 0
    updatedBooksCounter = 0
    totalNumberOfBooks = len(booksListResultsSort)
    for key, value in booksListResultsGroup: # key = 'category'
        old_newBooksCounter = newBooksCounter
        old_updatedBooksCounter = updatedBooksCounter
        for data in value: 
            book_id = str(data['id'])
            title = unidecode(data['title'])
            if(str(data['author']) == "None"):
                author = " "
            else: 
                author = unidecode(data['author'])
            source = data['category']
            num_highlights = data['num_highlights']
            updated = data['updated']
            cover_image_url = data['cover_image_url']
            url = data['highlights_url']
            source_url = data['source_url']
            highlights = []
            values = { "book_id" : book_id, "title" : title, "author" : author, "source" : source, "url" : url, "cover_image_url" : cover_image_url, "source_url" : source_url, "num_highlights" : num_highlights, "updated" : updated, "highlights" : highlights }
            indexCategory = categoriesObjectNames.index(source) # Identify which position the 'category' corresponds to within the list of category objects
            if not any(d["book_id"] == book_id for d in categoriesObject[indexCategory]):
                categoriesObject[indexCategory].append(values)
                newBooksCounter += 1
                print(str((newBooksCounter + updatedBooksCounter)) + '/' + str(len(booksListResultsSort)) + ' books added or updated')
            else:
                indexBook = list(map(itemgetter('book_id'), categoriesObject[indexCategory])).index(book_id)
                categoriesObject[indexCategory][indexBook]['book_id'] = book_id
                categoriesObject[indexCategory][indexBook]['title'] = title  
                categoriesObject[indexCategory][indexBook]['author'] = author
                categoriesObject[indexCategory][indexBook]['source'] = source
                categoriesObject[indexCategory][indexBook]['num_highlights'] = num_highlights
                categoriesObject[indexCategory][indexBook]['updated'] = updated
                categoriesObject[indexCategory][indexBook]['cover_image_url'] = cover_image_url
                categoriesObject[indexCategory][indexBook]['url'] = url
                categoriesObject[indexCategory][indexBook]['source_url'] = source_url
                updatedBooksCounter += 1
                print(str((newBooksCounter + updatedBooksCounter)) + '/' + str(len(booksListResultsSort)) + ' books added or updated')
        new_newBooksCounter = newBooksCounter
        new_updatedBooksCounter = updatedBooksCounter
        message = str(new_newBooksCounter - old_newBooksCounter) + ' new books added and ' + str(new_updatedBooksCounter - old_updatedBooksCounter) + ' updated in ' + str(categoriesObjectNames[indexCategory]) + ' object'
        logDateTimeOutput(message)

# Check if 'highlight_id' exists already. If no, append highlight data to the relevant 'book_id' within the category object
def appendHighlightDataToObject():
    newHighlightsCounter = 0
    updatedHighlightsCounter = 0
    for key, value in highlightsListResultsGroup: # key = 'book_id'
        listCategories = [item for category in categoriesObject for item in category]
        if any(d.get('book_id') == str(key) for d in listCategories): # Check if the 'book_id' from the grouped highlights exists. 
            index = list(map(itemgetter('book_id'), listCategories)).index(str(key))
            source = listCategories[index]['source'] # Get the 'category' of the corresponding 'book_id' from the grouped highlights
            indexCategory = categoriesObjectNames.index(source) # Identify which position the 'category' corresponds to within the list of category objects
            indexBook = list(map(itemgetter('book_id'), categoriesObject[indexCategory])).index(str(key)) # Identify which position the 'book_id' corresponds to within the category object
            for data in value: 
                id = str(data['id'])
                note = unidecode(data['note'])
                location = str(data['location'])
                location_type = data['location_type']
                book_id = str(data['book_id'])
                url = str(data['url'])
                highlighted_at = str(data['highlighted_at'])
                updated = str(data['updated'])
                text = unidecode(data['text'])
                tags = []
                # highlight = { "id" : id, "text" : text, "note" : note, "tags" : tags, "location" : location, "location_type" : location_type, "url" : url, "highlighted_at" : highlighted_at, "updated" : updated }
                if not any(d["id"] == id for d in categoriesObject[indexCategory][indexBook]['highlights']):
                    highlight = { "id" : id, "text" : text, "note" : note, "tags" : tags, "location" : location, "location_type" : location_type, "url" : url, "highlighted_at" : highlighted_at, "updated" : updated }
                    categoriesObject[indexCategory][indexBook]['highlights'].append(highlight)
                    sorted(categoriesObject[indexCategory][indexBook]['highlights'], key = itemgetter('location'))
                    newHighlightsCounter += 1
                    listOfBookIdsToUpdateMarkdownNotes.append([str(key), str(source)])
                    print(str((newHighlightsCounter + updatedHighlightsCounter)) + '/' + str(len(highlightsListResultsSort)) + ' highlights added or updated')
                else:
                    indexHighlight = list(map(itemgetter('id'), categoriesObject[indexCategory][indexBook]['highlights'])).index(id) # Should be the same as 'data'
                    tags = categoriesObject[indexCategory][indexBook]['highlights'][indexHighlight]['tags']
                    highlight = { "id" : id, "text" : text, "note" : note, "tags" : tags, "location" : location, "location_type" : location_type, "url" : url, "highlighted_at" : highlighted_at, "updated" : updated }
                    categoriesObject[indexCategory][indexBook]['highlights'][indexHighlight] = highlight
                    sorted(categoriesObject[indexCategory][indexBook]['highlights'], key = itemgetter('location'))
                    updatedHighlightsCounter += 1
                    listOfBookIdsToUpdateMarkdownNotes.append([str(key), str(source)])
                    print(str((newHighlightsCounter + updatedHighlightsCounter)) + '/' + str(len(highlightsListResultsSort)) + ' highlights added or updated')
    message = str(newHighlightsCounter) + ' new highlights added and ' + str(updatedHighlightsCounter) + ' updated (excl tags)' # '.json'
    logDateTimeOutput(message)

def appendTagsToHighlightObject(list_highlights):
    if fetchTagsBoolean is False:
        return
    else:
        if len(list_highlights) == 0:
            return
        else:
            # Open new Chrome window via Selenium
            print('Opening new Chrome browser window...')
            options = webdriver.ChromeOptions()
            options.add_argument('--ignore-certificate-errors')
            options.add_argument('--incognito')
            options.add_argument('--headless')
            options.add_argument('--log-level=3') # to stop logging
            options.add_argument("start-maximized")
            driver = webdriver.Chrome(chromedriverDirectory, options=options)
            # driver = webdriver.Chrome(chromedriverDirectory)
            driver.get('https://readwise.io/accounts/login')
            print('Logging into readwise using credentials provided in readwiseMetadata')
            # Input email as username from readwiseMetadata
            username = driver.find_element_by_xpath("//*[@id='id_login']")
            username.clear()
            username.send_keys(email) # from 'readwiseMetadata'
            # Input password from readwiseMetadata
            password = driver.find_element_by_xpath("//*[@id='id_password']")
            password.clear()
            password.send_keys(pwd) # from 'readwiseMetadata'
            # Click login button
            driver.find_element_by_xpath("/html/body/div[1]/div/div/div/div/div/div/form/div[3]/button").click()
            print('Log-in successful! Fetching tags...')
            # Loop through new highlights
            updatedTagsCounter = 0
            newOrUpdatedTagsProgressCounter = 0
            for i in range(len(list_highlights)): # key = 'book_id'
                listCategories = [item for category in categoriesObject for item in category]
                key = str(list_highlights[i]['book_id'])
                id = str(list_highlights[i]['id'])
                index = list(map(itemgetter('book_id'), listCategories)).index(key)
                source = listCategories[index]['source'] # Get the 'category' of the corresponding 'book_id' from the grouped highlights
                indexCategory = categoriesObjectNames.index(source) # Identify which position the 'category' corresponds to within the list of category objects
                indexBook = list(map(itemgetter('book_id'), categoriesObject[indexCategory])).index(str(key)) # Identify which position the 'book_id' corresponds to within the category object
                bookLastUpdated = categoriesObject[indexCategory][indexBook]['updated']
                indexHighlight = list(map(itemgetter('id'), categoriesObject[indexCategory][indexBook]['highlights'])).index(id)
                # highlights = categoriesObject[indexCategory][indexBook]['highlights']
                book_id = categoriesObject[indexCategory][indexBook]['book_id']
                bookReviewUrl = 'https://readwise.io/bookreview/' + book_id
                # Open new tab in Chrome window
                driver.find_element_by_tag_name('body').send_keys(Keys.COMMAND + 't') 
                # driver.find_element_by_tag_name('body').send_keys(Keys.CONTROL + 't') 
                driver.get(bookReviewUrl)
                # Loop through tags and append to highlight object within corresponding book object
                try: 
                    xPathHighlightId = "//*[@id=\'highlight" + id + "\']"
                    highlightIdBlock = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, xPathHighlightId))
                    )
                    tagLinks = highlightIdBlock.find_elements_by_class_name("tag-link") # Get tags within 'highlight id' block
                    # Load original tags (if they exist)
                    originalTags = categoriesObject[indexCategory][indexBook]['highlights'][indexHighlight]['tags']
                    originalTags = sorted(originalTags)
                    originalTagsCounter = len(originalTags)
                    # Ignore highlights with no tags
                    if tagLinks == []:
                        pass
                    newTags = []
                    for tag in tagLinks:
                        originalHref = tag.get_attribute("href") # e.g. https://readwise.io/tags/<tag_name>
                        trimHref = originalHref.replace('https://readwise.io/tags/', '') # e.g. <tag_name>
                        newTags.append(trimHref)
                    newTags = sorted(newTags)
                    newTagsCounter = len(newTags)
                    if originalTags == newTags:
                        pass
                    else:
                        categoriesObject[indexCategory][indexBook]['highlights'][indexHighlight]['tags'] = newTags
                        categoriesObject[indexCategory][indexBook]['highlights'][indexHighlight]['updated'] = bookLastUpdated
                        updatedTagsCounter += abs((newTagsCounter - originalTagsCounter))
                        newOrUpdatedTagsProgressCounter += 1
                        listOfBookIdsToUpdateMarkdownNotes.append([str(key), str(source)])
                        print(str(newOrUpdatedTagsProgressCounter) + '/' + str(len(list_highlights)) + ' highlights updated with tags')
                except: 
                    message = 'Error looping through tags in highlight id block "' + str(id) + '". Book id: "' + str(book_id) + '". Book URL: "' + str(bookReviewUrl) + '". File: "' \
                    + str(categoriesObjectNames[indexCategory]) + '.json". Book location: "' + str(indexBook) + '". Highlight location: "' + str(indexHighlight) + '".'
                    logDateTimeOutput(message)
                    pass
            driver.quit()
        try:
            message = str(updatedTagsCounter) + ' tags added or updated to ' + str(len(list_highlights)) + ' highlights in ' + str(categoriesObjectNames[indexCategory]) + ' object'
            logDateTimeOutput(message)
        except UnboundLocalError:
            message = 'No tags to add or update'
            logDateTimeOutput(message)

def appendUpdatedHighlightsToObject():
    listOfBookIdsFromBooksList = []
    listOfBookIdsFromHighlightsList = []
    listofBookIdsWithMissingHighlights = []
    for i in range(len(booksListResultsSort)):
        listOfBookIdsFromBooksList.append(str(booksListResultsSort[i]['id']))
    for i in range(len(highlightsListResultsSort)):
        listOfBookIdsFromHighlightsList.append(str(highlightsListResultsSort[i]['book_id']))
        listOfBookIdsFromHighlightsList = list(dict.fromkeys(listOfBookIdsFromHighlightsList)) # Remove duplicates
    for i in range(len(listOfBookIdsFromBooksList)):
        if listOfBookIdsFromBooksList[i] not in listOfBookIdsFromHighlightsList:
            listofBookIdsWithMissingHighlights.append(str(listOfBookIdsFromBooksList[i]))
        else: 
            pass
    for i in range(len(listofBookIdsWithMissingHighlights)):
        missingHighlightsListQueryString = {
            "page_size": 1000, # 1000 items per page - maximum
            "page": 1, # Page 1 >> build for loop to cycle through pages and stop when complete
            "book_id": listofBookIdsWithMissingHighlights[i], 
        }
        # Trigger GET request with missingHighlightsListQueryString
        missingHighlightsList = requests.get(
            url="https://readwise.io/api/v2/highlights/",
            headers={"Authorization": "Token " + token}, # token imported from readwiseAccessToken file
            params=missingHighlightsListQueryString # query string object
        )
        # Convert response into JSON object
        try:
            missingHighlightsListJson = missingHighlightsList.json() # type(missingHighlightsListJson) = 'dictionary'
        except ValueError:
            message = 'Response content from missingHighlightsList request is not valid JSON'
            logDateTimeOutput(message)
            print(message) # Originally from https://github.com/psf/requests/issues/4908#issuecomment-627486125
            break
            # JSONDecodeError: Expecting value: line 1 column 1 (char 0) specifically happens with an empty string (i.e. empty response content)
        try:
            # Create dictionary of missingHighlightsListJson['results']
            missingHighlightsListResults = missingHighlightsListJson['results'] # type(highlightsListResults) = 'list'
        except NameError:
            message = 'Cannot extract results from empty JSON for missingHighlightsList request'
            logDateTimeOutput(message)
            print(message)
            break
        # Loop through pagination using 'next' property from GET response
        try:
            additionalLoopCounter = 0
            while missingHighlightsListJson['next']:
                additionalLoopCounter += 1
                print('Fetching additional missing highlight data from readwise... (page ' + str(additionalLoopCounter) + ')')
                missingHighlightsList = requests.get(
                    url=missingHighlightsListJson['next'], # keep same query parameters from booksListQueryString object
                    headers={"Authorization": "Token " + token}, # token imported from readwiseAccessToken file
                )
                try:
                    print('Converting additional missing highlight data returned into JSON... (page ' + str(additionalLoopCounter) + ')')
                    missingHighlightsListJson = missingHighlightsList.json() # type(missingHighlightsListJson) = 'dictionary'
                except ValueError:
                    message = 'Response content from additional missingHighlightsList request is not valid JSON'
                    logDateTimeOutput(message)
                    print(message) # Originally from https://github.com/psf/requests/issues/4908#issuecomment-627486125
                    # JSONDecodeError: Expecting value: line 1 column 1 (char 0) specifically happens with an empty string (i.e. empty response content)
                    break
                try:
                    missingHighlightsListResults.extend(missingHighlightsListJson['results'])
                except NameError:
                    message = 'Cannot extract results from empty JSON for additional missingHighlightsList request'
                    logDateTimeOutput(message)
                    print(message)
                    break
        except NameError:
            message = 'Cannot loop through pagination from empty response'
            logDateTimeOutput(message)
            print(message)
            break
        # Replace 'location': None and 'location_type': 'none' values in list of dictionaries
        replaceNoneInListOfDict(missingHighlightsListResults)
        # Sort highlightsListResults data by 'book_id' key and 'location'
        missingHighlightsListResultsSort = sorted(missingHighlightsListResults, key = itemgetter('location'))
        newMissingHighlightsCounter = 0
        updatedMissingHighlightsCounter = 0
        if len(missingHighlightsListResults) == 0:
            break
        else:
            try:
                for j in range(len(missingHighlightsListResultsSort)):
                    listCategories = [item for category in categoriesObject for item in category]
                    book_id = str(missingHighlightsListResultsSort[j]['book_id'])
                    index = list(map(itemgetter('book_id'), listCategories)).index(book_id)
                    source = listCategories[index]['source'] # Get the 'category' of the corresponding 'book_id' from the grouped highlights
                    indexCategory = categoriesObjectNames.index(source) # Identify which position the 'category' corresponds to within the list of category objects
                    indexBook = list(map(itemgetter('book_id'), categoriesObject[indexCategory])).index(str(book_id)) # Identify which position the 'book_id' corresponds to within the category object
                    bookLastUpdated = categoriesObject[indexCategory][indexBook]['updated']
                    id = str(missingHighlightsListResultsSort[j]['id'])
                    note = unidecode(missingHighlightsListResultsSort[j]['note'])
                    location = str(missingHighlightsListResultsSort[j]['location'])
                    location_type = missingHighlightsListResultsSort[j]['location_type']
                    url = str(missingHighlightsListResultsSort[j]['url'])
                    highlighted_at = str(missingHighlightsListResultsSort[j]['highlighted_at'])
                    updated = str(missingHighlightsListResultsSort[j]['updated'])
                    text = unidecode(missingHighlightsListResultsSort[j]['text'])
                    tags = []
                    highlight = { "id" : id, "text" : text, "note" : note, "tags" : tags, "location" : location, "location_type" : location_type, "url" : url, "highlighted_at" : highlighted_at, "updated" : updated }
                    if not any(d["id"] == id for d in categoriesObject[indexCategory][indexBook]['highlights']):
                        categoriesObject[indexCategory][indexBook]['highlights'].append(highlight)
                        sorted(categoriesObject[indexCategory][indexBook]['highlights'], key = itemgetter('location'))
                        newMissingHighlightsCounter += 1
                        listOfBookIdsToUpdateMarkdownNotes.append([str(book_id), str(source)])
                        print(str((newMissingHighlightsCounter + updatedMissingHighlightsCounter)) + '/' + str(len(missingHighlightsListResultsSort)) + ' missing highlights added or updated')
                    else:
                        indexHighlight = list(map(itemgetter('id'), categoriesObject[indexCategory][indexBook]['highlights'])).index(id)
                        if categoriesObject[indexCategory][indexBook]['highlights'][indexHighlight]['text'] == text:
                            if categoriesObject[indexCategory][indexBook]['highlights'][indexHighlight]['note'] == note:
                                pass
                            else:
                                categoriesObject[indexCategory][indexBook]['highlights'][indexHighlight]['note'] = note
                                categoriesObject[indexCategory][indexBook]['highlights'][indexHighlight]['updated'] = bookLastUpdated
                        else:
                            categoriesObject[indexCategory][indexBook]['highlights'][indexHighlight]['text'] = text
                            categoriesObject[indexCategory][indexBook]['highlights'][indexHighlight]['updated'] = bookLastUpdated
                            if categoriesObject[indexCategory][indexBook]['highlights'][indexHighlight]['note'] == note:
                                pass
                            else:
                                categoriesObject[indexCategory][indexBook]['highlights'][indexHighlight]['note'] = note
                        sorted(categoriesObject[indexCategory][indexBook]['highlights'], key = itemgetter('location'))
                        updatedMissingHighlightsCounter += 1
                        listOfBookIdsToUpdateMarkdownNotes.append([str(book_id), str(source)])
                    print(str((newMissingHighlightsCounter + updatedMissingHighlightsCounter)) + '/' + str(len(missingHighlightsListResultsSort)) + ' missing highlights added or updated in ' \
                        + str(categoriesObjectNames[indexCategory]) + ' object')
            except ValueError:
                pass
    try:
        message = str(updatedMissingHighlightsCounter) + ' highlights updated (incl tags) in ' + str(categoriesObjectNames[indexCategory]) + ' object' # '.json'
        logDateTimeOutput(message)
        appendHighlightsToListForFetchingTags(missingHighlightsListToFetchTagsFor, missingHighlightsListResultsSort)
        appendHighlightsToListForFetchingTags(allHighlightsToFetchTagsFor, missingHighlightsListResultsSort)
        # appendTagsToHighlightObject(missingHighlightsListResultsSort)
    except UnboundLocalError:
        message = 'No missing highlights (incl tags) to update'
        logDateTimeOutput(message)

def appendBookAndHighlightObjectToJson():
    for i in range(len(categoriesObjectNames)):
        try:
            with open(os.path.join(sourceDirectory, "readwiseCategories", categoriesObjectNames[i] + ".json"), 'w') as outfile:
                json.dump(categoriesObject[i], outfile, indent=4)
        except FileNotFoundError:
            with open(os.path.join(sourceDirectory, "readwiseCategories", categoriesObjectNames[i] + ".json"), 'x') as outfile:
                json.dump(categoriesObject[i], outfile, indent=4)

def replaceNoneInListOfDict(listOfDicts):
    for i in range(len(listOfDicts)):
        for k, v in iter(listOfDicts[i].items()):
            if k == 'location' and v is None:
                listOfDicts[i][k] = 0
            if k == 'location_type' and v == 'none':
                listOfDicts[i][k] = 'custom'
            if k == 'highlighted_at' and v is None:
                listOfDicts[i][k] = str(v)

def removeHighlightsWithDiscardTag():
    listCategories = list(categoriesObject)
    highlightsWithDiscardTagCounter = 0
    for i in range(len(listCategories)):
        for k in range(len(listCategories[i])):
            book_id = str(listCategories[i][k]['book_id'])
            source = str(listCategories[i][k]['source'])
            originalNumberOfhighlights = listCategories[i][k]['num_highlights']
            indexCategory = categoriesObjectNames.index(source) # Identify which position the 'category' corresponds to within the list of category objects
            indexBook = list(map(itemgetter('book_id'), categoriesObject[indexCategory])).index(str(book_id)) # Identify which position the 'book_id' corresponds to within the category object
            originalListOfHighlights = listCategories[i][k]['highlights'].copy()
            newListOfHighlights = categoriesObject[indexCategory][indexBook]['highlights'].copy()
            for n in range(len(originalListOfHighlights)): 
                try:
                    if any('discard' in s for s in listCategories[i][k]['highlights'][n]['tags']):
                        id = listCategories[i][k]['highlights'][n]['id']
                        indexHighlight = list(map(itemgetter('id'), newListOfHighlights)).index(str(id))
                        newListOfHighlights.pop(indexHighlight)
                        # listCategories[i][k]['highlights'].pop(n) # Remove highlight with 'discard' tag from list
                        highlightsWithDiscardTagCounter += 1
                except IndexError:
                    continue
            categoriesObject[indexCategory][indexBook]['highlights'] = newListOfHighlights
            newNumberOfhighlights = len(newListOfHighlights)
            categoriesObject[indexCategory][indexBook]['num_highlights'] = newNumberOfhighlights
            if str(originalNumberOfhighlights - newNumberOfhighlights) == '0':
                pass
            else:
                print(str(originalNumberOfhighlights - newNumberOfhighlights) + ' highlights removed from ' + str(listCategories[i][k]['book_id']))
    message = str(highlightsWithDiscardTagCounter) + ' highlights discarded'
    logDateTimeOutput(message)
    print(message)

def appendHashtagToTags():
    listCategories = list(categoriesObject)
    tagsWithNoHashtag = 0
    for i in range(len(listCategories)):
        for k in range(len(listCategories[i])):
            book_id = str(listCategories[i][k]['book_id'])
            source = str(listCategories[i][k]['source'])
            indexCategory = categoriesObjectNames.index(source) # Identify which position the 'category' corresponds to within the list of category objects
            indexBook = list(map(itemgetter('book_id'), categoriesObject[indexCategory])).index(str(book_id)) # Identify which position the 'book_id' corresponds to within the category object
            for n in range(len(listCategories[i][k]['highlights'])):
                id = listCategories[i][k]['highlights'][n]['id']
                indexHighlight = list(map(itemgetter('id'), categoriesObject[indexCategory][indexBook]['highlights'])).index(str(id))
                for t in range(len(listCategories[i][k]['highlights'][n]['tags'])):
                    tag = str(listCategories[i][k]['highlights'][n]['tags'][t])
                    positionTag = listCategories[i][k]['highlights'][n]['tags'].index(tag) # Should be the same as 't'
                    if listCategories[i][k]['highlights'][n]['tags'][t].startswith('#'):
                        pass
                    else:
                        categoriesObject[indexCategory][indexBook]['highlights'][indexHighlight]['tags'][positionTag] = '#' + \
                        categoriesObject[indexCategory][indexBook]['highlights'][indexHighlight]['tags'][positionTag]
                        # listCategories[i][k]['highlights'][n]['tags'][t] = '#' + listCategories[i][k]['highlights'][n]['tags'][t]
                        tagsWithNoHashtag += 1
    message = str(tagsWithNoHashtag) + ' tags updated with hashtags'
    print(message)

# Set boolean value to determine if tags should be fetched (default = True)
# If any of the optional input variables in readwiseMetadata are blank or missing, set boolean to False
fetchTagsBoolean = True

def fetchTagsTrueOrFalse(fetchTagsBoolean, inputVariable):
    if fetchTagsBoolean is False:
        return False
    elif inputVariable == "" or inputVariable is None:
        return False
    else:
        return True

################################################
### Load CSV export into dataframe and lists ###
################################################

def latest_download_file():
      path = sourceDirectory
      files = sorted(os.listdir(os.getcwd()), key=os.path.getmtime)
      newest = files[-1]
      return newest

def download_wait():
    seconds = 0
    dl_wait = True
    while dl_wait and seconds < 20:
        time.sleep(1)
        dl_wait = False
        for fname in os.listdir(sourceDirectory):
            if fname.endswith('.crdownload'):
                dl_wait = True
        seconds += 1
    newest_file = latest_download_file()
    return newest_file

####### V2.0 #######

# Use Selenium to export CSV extract of highlight data, and save in sourceDirectory
def downloadCsvExport(latestDownloadedFileName): # with_ublock=False, chromedriverDirectory=None
    if fetchTagsBoolean is False:
        return
    else:
        # Open new Chrome window via Selenium
        print('Opening new Chrome browser window...')
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("window-size=1920,1080")
        options.add_argument("--log-level=3") # to stop logging
        options.add_argument("--silent")
        options.add_argument("--disable-logging")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option('prefs', {
        # "download.default_directory": downloadsDirectory, # Set own Download path
        "download.prompt_for_download": False, # Do not ask for download at runtime
        "download.directory_upgrade": True, # Also needed to suppress download prompt
        "w3c": False, # allows selenium to accept cookies with a non-int64 'expiry' value
        "excludeSwitches": ["enable-logging"], # removes the 'DevTools listening' log message
        "excludeSwitches": ["enable-automation"], # prevent Cloudflare from detecting ChromeDriver as bot
        "useAutomationExtension": False,
        })
        driver = webdriver.Chrome(
            executable_path=chromedriverDirectory,
            options=options,
        )
        driver.command_executor._commands["send_command"] = ("POST", '/session/$sessionId/chromium/send_command')
        params = {'behavior': 'allow', 'downloadPath': sourceDirectory}
        driver.execute_cdp_cmd('Page.setDownloadBehavior', params)
        driver.get('https://readwise.io/accounts/login')
        print('Logging into readwise using credentials provided in readwiseMetadata')
        # Input email as username from readwiseMetadata
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//*[@id='id_login']")))
        username = driver.find_element_by_xpath("//*[@id='id_login']")
        username.clear()
        username.send_keys(email) # from 'readwiseMetadata'
        # Input password from readwiseMetadata
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//*[@id='id_password']")))
        password = driver.find_element_by_xpath("//*[@id='id_password']")
        password.clear()
        password.send_keys(pwd) # from 'readwiseMetadata'
        # Click login button
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div/div/div/div/div/div/form/div[3]/button")))
        driver.find_element_by_xpath("/html/body/div[1]/div/div/div/div/div/div/form/div[3]/button").click()
        print('Log-in successful! Redirecting to export page...')
        driver.get('https://readwise.io/export')
        # Click export CSV button
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//*[@id='MiscApp']/div/div[3]/div/div[1]/div/div[2]/div/button")))
        driver.find_element_by_xpath("//*[@id='MiscApp']/div/div[3]/div/div[1]/div/div[2]/div/button").click()
        print('Redirect successful! Waiting for CSV export...')
        dlFilename = download_wait()
        # rename the downloaded file
        shutil.move(dlFilename, os.path.join(sourceDirectory, latestDownloadedFileName))
        message = str(latestDownloadedFileName) + ' successfully added to ' + str(sourceDirectory)
        logDateTimeOutput(message)
        print(message)
        print('Closing Chrome browser window...')
        driver.quit()

# Clean-up list values
def cleanUpListValues(listFromCsv, replacementCharacter):
    for i in range(len(listFromCsv)):
        if(str(listFromCsv[i]) == "nan"):
            listFromCsv[i] = str(replacementCharacter)
        else:
            listFromCsv[i] = unidecode(str(listFromCsv[i]))

# Make book titles valid filenames via Django
def convertTitleToValidFilename(listToConvert):
    for i in range(len(listToConvert)):
        listToConvert[i] = slugify(listToConvert[i])
        # listToConvert[i] = get_valid_filename_django(listToConvert[i])

# Convert all book titles to lowercase
def toLowercase(listToConvert):
    for i in range(len(listToConvert)):
        listToConvert[i] = listToConvert[i].lower()

# Replace empty CSV cells of 'Tags' with ""
def replaceEmptyTagCells(list_Tags):
    for i in range(len(list_Tags)):
        if(str(list_Tags[i]) == "nan"):
            list_Tags[i] = ""
        else:
            list_Tags[i] = list_Tags[i].replace(',', ' ')

# Normalise date strings e.g. 2020-01-01T12:59:59Z >> 2020-01-01 12:59:59
def dateStringNormaliser(dateString):
    for i in range(len(dateString)):
        dateString[i] = dateString[i].replace('T', ' ')[0 : 19]

# Create empty lists to fill data from CSV
list_Highlight = []
list_BookTitle = []
list_BookAuthor = []
list_AmazonBookId = []
list_Note = []
list_Color = []
list_Tags = []
list_LocationType = []
list_Location = []
list_HighlightedAt = []

# Create additional lists to supplement ones provided in the CSV export
list_ReadwiseBookId = [] # 'Readwise Book ID'
list_Source = [] # 'Source' # e.g. Articles
list_Url = [] # 'Url'
list_NumberOfHighlights = [] # 'Number of Highlights'
list_UpdatedAt = [] # 'Updated at'
list_HighlightId = [] # 'Highlight ID'

# Fill newly-created lists with empty values to aid with index matching
def fillListWithEmptyCharacters(listToGetRangeFrom, listToFill):
    for i in range(len(listToGetRangeFrom)):
        listToFill.append("")

# Create lists to add extracted highlight data from API calls
# Then we can compare these lists to to those from the CSV export to retrieve highlight id's, book id's, and highlight tags
list_extractedHighlightId = []
list_extractedHighlightText = []
list_extractedHighlightTags = []
list_extractedHighlightBookId = []
list_extractedHighlightBookTitle = []
list_extractedHighlightBookAuthor = []
list_extractedHighlightLocation = []
list_extractedHighlightedAt = []

# Create lists to collect fallouts e.g. no highlight id retrieved from highlight text, highlight text has duplicate values
list_noMatchingHighlightIdFromText = []
list_noMatchingBookIdFromTitle = []
list_duplicateHighlightTextValues = []

# Fill empty lists with values from highlights list of dictionaries
def fillListsWithHighlightData(listToFill):
    for j in range(len(listToFill)):
        for k, v in iter(listToFill[j].items()):
            if k == 'text':
                list_extractedHighlightText[j] = str(v)
            if k == 'id':
                list_extractedHighlightId[j] = str(v)
            if k == 'location':
                list_extractedHighlightLocation[j] = str(v)
            if k == 'highlighted_at':
                list_extractedHighlightedAt[j] = str(v)
            if k == 'book_id':
                list_extractedHighlightBookId[j] = str(v)

# Clean-up extracted list values
def cleanUpExtractedListValues(listFromJson):
    for i in range(len(listFromJson)):
        listFromJson[i] = unidecode(str(listFromJson[i]))

# Mark duplicate values e.g. AirrQuotes
def checkForDuplicates(listToGetRangeFrom, listToCheckDuplicateValues):
    for i in range(len(listToGetRangeFrom)):
        if listToCheckDuplicateValues.count(listToCheckDuplicateValues[i]) > 1:
            list_duplicateHighlightTextValues[i] = 'Duplicate value'

# Fetch highlight id, book id, and tags from 'highlight text' or 'highlighted at' (if there are duplicates)
def fetchTagsFromCsvData(list_Highlight, list_BookTitle, list_BookAuthor, list_AmazonBookId, list_Note, list_Color, list_Tags, list_LocationType, list_Location, list_HighlightedAt, \
    list_ReadwiseBookId, list_Source, list_Url, list_NumberOfHighlights, list_UpdatedAt, list_HighlightId, list_extractedHighlightTags, list_extractedHighlightText, list_extractedHighlightId, \
    list_extractedHighlightLocation, list_extractedHighlightedAt, list_extractedHighlightBookId, list_noMatchingHighlightIdFromText, list_duplicateHighlightTextValues):
    textMatch = 0
    noMatch = 0
    tagsFromTextMatch = 0
    totalNumberOfTags = sum(1 for x in list_Tags if x != '')
    for i in range(len(list_extractedHighlightText)):
        try:
            if list_duplicateHighlightTextValues[i] == 'Duplicate value':
                if list_extractedHighlightedAt[i] in list_HighlightedAt:
                    index1 = list_HighlightedAt.index(list_extractedHighlightedAt[i])
                    list_HighlightId[index1] = str(list_extractedHighlightId[i])
                    list_ReadwiseBookId[index1] = str(list_extractedHighlightBookId[i])
                    list_duplicateHighlightTextValues[i] = ""
                    if(str(list_Tags[index1]) == ""):
                        list_extractedHighlightTags[i] = ""
                    else:
                        list_extractedHighlightTags[i] = str(list_Tags[index1])
                        tagsFromTextMatch += 1
                    textMatch += 1
                    print(str(textMatch) + '/' + str(len(list_extractedHighlightText)) + ' highlights matched with ' \
                        + str(tagsFromTextMatch) + '/' + str(totalNumberOfTags) + ' tags')
                else:
                    noMatch += 1
                    message = str(list_extractedHighlightId[i]) + ' from ' + str(list_extractedHighlightBookId[i]) + ' not matched as it is a duplicate'
                    print(message)
                    pass
            else: 
                if list_extractedHighlightText[i] in list_Highlight:
                    index2 = list_Highlight.index(list_extractedHighlightText[i])
                    list_HighlightId[index2] = str(list_extractedHighlightId[i])
                    list_ReadwiseBookId[index2] = str(list_extractedHighlightBookId[i])
                    if(str(list_Tags[index2]) == ""):
                        list_extractedHighlightTags[i] = ""
                    else:
                        list_extractedHighlightTags[i] = str(list_Tags[index2])
                        tagsFromTextMatch += 1
                    textMatch += 1
                    print(str(textMatch) + '/' + str(len(list_extractedHighlightText)) + ' highlights matched with ' \
                        + str(tagsFromTextMatch) + '/' + str(totalNumberOfTags) + ' tags')
                else:
                    try:
                        list_noMatchingHighlightIdFromText[i] = 'No highlight text match'
                    except IndexError:
                        return
        except IndexError:
            return
    message = str(textMatch) + '/' + str(len(list_extractedHighlightText)) + ' highlights matched with ' \
                        + str(tagsFromTextMatch) + '/' + str(totalNumberOfTags) + ' tags'
    logDateTimeOutput(message)

def appendTagsFromCsvToCategoriesObject(list_highlights, list_ExtractedTags):
    tagsFromCsvCounter = 0
    totalNumberOfTags = sum(1 for x in list_ExtractedTags if x != '')
    for i in range(len(list_highlights)): # key = 'book_id'
        listCategories = [item for category in categoriesObject for item in category]
        key = str(list_highlights[i]['book_id'])
        id = str(list_highlights[i]['id'])
        index = list(map(itemgetter('book_id'), listCategories)).index(key)
        source = listCategories[index]['source'] # Get the 'category' of the corresponding 'book_id' from the grouped highlights
        indexCategory = categoriesObjectNames.index(source) # Identify which position the 'category' corresponds to within the list of category objects
        indexBook = list(map(itemgetter('book_id'), categoriesObject[indexCategory])).index(str(key)) # Identify which position the 'book_id' corresponds to within the category object
        bookLastUpdated = categoriesObject[indexCategory][indexBook]['updated']
        indexHighlight = list(map(itemgetter('id'), categoriesObject[indexCategory][indexBook]['highlights'])).index(id)
        # highlights = categoriesObject[indexCategory][indexBook]['highlights']
        book_id = categoriesObject[indexCategory][indexBook]['book_id']
        bookReviewUrl = 'https://readwise.io/bookreview/' + book_id
        indexTags = list_extractedHighlightId.index(id)
        if str(list_ExtractedTags[indexTags]) == '' or str(list_ExtractedTags[indexTags]) == 'nan':
            categoriesObject[indexCategory][indexBook]['highlights'][indexHighlight]['tags'] = []
        else:
            tagsArray = str(list_ExtractedTags[indexTags]).split()
            categoriesObject[indexCategory][indexBook]['highlights'][indexHighlight]['tags'] = tagsArray
            categoriesObject[indexCategory][indexBook]['highlights'][indexHighlight]['updated'] = bookLastUpdated
            tagsFromCsvCounter += 1
            print(str(tagsFromCsvCounter) + '/' + str(totalNumberOfTags) + ' tags added or updated from the CSV export')
    message = str(tagsFromCsvCounter) + '/' + str(totalNumberOfTags) + ' tags added or updated from the CSV export'
    logDateTimeOutput(message)

def runFetchCsvData():
    readwiseCsvExportFileName = 'readwise-data.csv'
    downloadCsvExport(readwiseCsvExportFileName)
    readwiseCsvExportPath = os.path.join(sourceDirectory, readwiseCsvExportFileName)
    df = pd.read_csv(readwiseCsvExportPath)
    # Insert complete path to the excel file and optional variables 
    # https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.read_csv.html
    df.sort_values(by=['Highlighted at'], ascending=True)
    # Insert the name of the column as a string in brackets
    list_Highlight = list(df['Highlight'])
    list_BookTitle = list(df['Book Title'])
    list_BookAuthor = list(df['Book Author'])
    list_AmazonBookId = list(df['Amazon Book ID'])
    list_Note = list(df['Note'])
    list_Color = list(df['Color'])
    list_Tags = list(df['Tags'])
    list_LocationType = list(df['Location Type'])
    list_Location = list(df['Location'])
    list_HighlightedAt = list(df['Highlighted at'])
    cleanUpListValues(list_Highlight, " ")
    cleanUpListValues(list_BookAuthor, " ")
    cleanUpListValues(list_Note, " ")
    cleanUpListValues(list_Location, "0")
    convertTitleToValidFilename(list_BookTitle)
    toLowercase(list_BookTitle)
    replaceEmptyTagCells(list_Tags)
    dateStringNormaliser(list_HighlightedAt)
    fillListWithEmptyCharacters(list_HighlightedAt, list_ReadwiseBookId)
    fillListWithEmptyCharacters(list_HighlightedAt, list_Source)
    fillListWithEmptyCharacters(list_HighlightedAt, list_Url)
    fillListWithEmptyCharacters(list_HighlightedAt, list_NumberOfHighlights)
    fillListWithEmptyCharacters(list_HighlightedAt, list_UpdatedAt)
    fillListWithEmptyCharacters(list_HighlightedAt, list_HighlightId)
    return list_Highlight, list_BookTitle, list_BookAuthor, list_AmazonBookId, list_Note, list_Color, list_Tags, list_LocationType, list_Location, list_HighlightedAt, \
    list_ReadwiseBookId, list_Source, list_Url, list_NumberOfHighlights, list_UpdatedAt, list_HighlightId

def runExtractDataFromApi(list_Highlight, list_BookTitle, list_BookAuthor, list_AmazonBookId, list_Note, list_Color, list_Tags, list_LocationType, list_Location, list_HighlightedAt, \
    list_ReadwiseBookId, list_Source, list_Url, list_NumberOfHighlights, list_UpdatedAt, list_HighlightId):
    allHighlightsToFetchTagsForSortByDate = sorted(allHighlightsToFetchTagsFor, key = itemgetter('highlighted_at'))
    fillListWithEmptyCharacters(allHighlightsToFetchTagsForSortByDate, list_extractedHighlightTags)
    fillListWithEmptyCharacters(allHighlightsToFetchTagsForSortByDate, list_extractedHighlightText)
    fillListWithEmptyCharacters(allHighlightsToFetchTagsForSortByDate, list_extractedHighlightId)
    fillListWithEmptyCharacters(allHighlightsToFetchTagsForSortByDate, list_extractedHighlightLocation)
    fillListWithEmptyCharacters(allHighlightsToFetchTagsForSortByDate, list_extractedHighlightedAt)
    fillListWithEmptyCharacters(allHighlightsToFetchTagsForSortByDate, list_extractedHighlightBookId)
    fillListWithEmptyCharacters(allHighlightsToFetchTagsForSortByDate, list_noMatchingHighlightIdFromText)
    fillListWithEmptyCharacters(allHighlightsToFetchTagsForSortByDate, list_duplicateHighlightTextValues)
    fillListsWithHighlightData(allHighlightsToFetchTagsForSortByDate)
    cleanUpExtractedListValues(list_extractedHighlightText)
    cleanUpExtractedListValues(list_extractedHighlightId)
    cleanUpExtractedListValues(list_extractedHighlightLocation)
    cleanUpExtractedListValues(list_extractedHighlightedAt)
    cleanUpExtractedListValues(list_extractedHighlightBookId)
    dateStringNormaliser(list_extractedHighlightedAt)
    checkForDuplicates(list_extractedHighlightText, list_extractedHighlightText)
    return allHighlightsToFetchTagsForSortByDate, list_extractedHighlightTags, list_extractedHighlightText, list_extractedHighlightId, list_extractedHighlightLocation, \
        list_extractedHighlightedAt, list_extractedHighlightBookId, list_noMatchingHighlightIdFromText, list_duplicateHighlightTextValues

def runFetchTagsFromCsvData(list_Highlight, list_BookTitle, list_BookAuthor, list_AmazonBookId, list_Note, list_Color, list_Tags, list_LocationType, list_Location, list_HighlightedAt, \
    list_ReadwiseBookId, list_Source, list_Url, list_NumberOfHighlights, list_UpdatedAt, list_HighlightId, list_extractedHighlightTags, list_extractedHighlightText, list_extractedHighlightId, \
    list_extractedHighlightLocation, list_extractedHighlightedAt, list_extractedHighlightBookId, list_noMatchingHighlightIdFromText, list_duplicateHighlightTextValues):
    fetchTagsFromCsvData(list_Highlight, list_BookTitle, list_BookAuthor, list_AmazonBookId, list_Note, list_Color, list_Tags, list_LocationType, list_Location, list_HighlightedAt, \
    list_ReadwiseBookId, list_Source, list_Url, list_NumberOfHighlights, list_UpdatedAt, list_HighlightId, list_extractedHighlightTags, list_extractedHighlightText, list_extractedHighlightId, \
    list_extractedHighlightLocation, list_extractedHighlightedAt, list_extractedHighlightBookId, list_noMatchingHighlightIdFromText, list_duplicateHighlightTextValues)
    appendTagsFromCsvToCategoriesObject(allHighlightsToFetchTagsFor, list_extractedHighlightTags)

###############################################################
### Create markdown notes with updated books and highlights ###
###############################################################

# Create function for generating new markdown notes
# Change working directory to desired path set in the readwiseMetadata file
# Append book metadata at the top of the note e.g. title, author, source, readwise url
# Append all highlights separated by "---" beneath the book metadata

def createMarkdownNote(listOfBookIdsToUpdateMarkdownNotes): 
    booksWithNoHighlights = 0
    booksWithHeadings = 0
    if os.path.exists(targetDirectory):
        os.chdir(targetDirectory)
    else:
        print('Error! The target directory does not exist or is incorrect')
    # Match the 'book_id' to the correct category dictionary e.g. books, articles
    # Retrieve 'book_id' metadata from the dictionary
    listCategories = list(categoriesObject)
    # listCategories = [item for category in categoriesObject for item in category]
    listOfBookIdsToUpdateMarkdownNotes.sort()
    listOfBookIdsToUpdateMarkdownNotes = list(listOfBookIdsToUpdateMarkdownNotes for listOfBookIdsToUpdateMarkdownNotes,_ in groupby(listOfBookIdsToUpdateMarkdownNotes))
    if len(listOfBookIdsToUpdateMarkdownNotes) != 0:
        for bookData in range(len(listOfBookIdsToUpdateMarkdownNotes)):  # type(listOfBookIdsToUpdateMarkdownNotes[bookData]) = list
            key = str(listOfBookIdsToUpdateMarkdownNotes[bookData][0])
            source = str(listOfBookIdsToUpdateMarkdownNotes[bookData][1])
            indexCategory = categoriesObjectNames.index(source) # Identify which position the 'category' corresponds to within the list of category objects
            indexBook = list(map(itemgetter('book_id'), categoriesObject[indexCategory])).index(str(key)) # Identify which position the 'book_id' corresponds to within the category object
            yamlData = []
            titleBlock = []
            yamlData.append("---" + "\n")
            # Add title to yamlData and titleBlock
            title = unidecode(categoriesObject[indexCategory][indexBook]['title']).replace('"', '\'')
            yamlData.append("Title: " + "\"" + str(title) + "\"" + "\n")
            titleBlock.append("# " + str(title) + "\n")
            if(str(categoriesObject[indexCategory][indexBook]['author']) == "None"):
                author = " "
                yamlData.append("Author: " + str(author) + "\n")
            else: 
                author = unidecode(categoriesObject[indexCategory][indexBook]['author']).replace('"', '\'')
                yamlData.append("Author: " + "\"" + str(author) + "\"" + "\n")
            source = categoriesObject[indexCategory][indexBook]['source']
            yamlData.append("Tags: " + "[" + "readwise" + ", " + str(source) + "]" + "\n")
            num_highlights = categoriesObject[indexCategory][indexBook]['num_highlights']
            yamlData.append("Highlights: " + str(num_highlights) + "\n")
            lastUpdated = datetime.strptime(categoriesObject[indexCategory][indexBook]['updated'][0:10], '%Y-%m-%d').strftime("%y%m%d %A")
            yamlData.append("Updated: " + "[[" + str(lastUpdated) + "]]" + "\n")
            # Add readwise url to yamlData and titleBlock
            url = str(categoriesObject[indexCategory][indexBook]['url'])
            yamlData.append("Readwise URL: " + str(url) + "\n")
            titleBlock.append("[Readwise URL](" + str(url) + ")")
            book_id = str(categoriesObject[indexCategory][indexBook]['book_id'])
            yamlData.append("Readwise ID: " + str(book_id) + "\n")
            # Add source URL (if exists) to yamlData and titleBlock
            try: 
                source_url = str(categoriesObject[indexCategory][indexBook]['source_url'])
                if source_url.lower() == "none" or source_url.lower() == "null" or source_url == "":
                    continue
                else:
                    yamlData.append("Source URL: " + str(source_url) + "\n")
                    titleBlock.append(" | " + "[Source URL](" + str(source_url) + ")"+ "\n\n")
            except NameError:
                continue
            yamlData.append("---" + "\n\n")
            titleBlock.append("---" + "\n\n")
            # Add cover image URL if exists
            try:
                cover_image_url = str(categoriesObject[indexCategory][indexBook]['cover_image_url'])
                titleBlock.append("![](" + cover_image_url + ")" + "\n\n")
                titleBlock.append("---" + "\n")
            except NameError:
                continue 
            fileName = slugify(title)
            # fileName = get_valid_filename_django(title)
            yamlData = "".join(yamlData)
            titleBlock = "".join(titleBlock)
            # Ignore books with no highlights
            if str(num_highlights) == '0':
                booksWithNoHighlights += 1
                pass
            else:
                with open(fileName + ".md", 'w') as newFile: # Warning: this will overwrite all content within the readwise note. 
                    print(yamlData, file=newFile)
                    print(titleBlock, file=newFile)
                    # Append highlights to the file beneath the 'book_id' metadata
                    for n in range(len(categoriesObject[indexCategory][indexBook]['highlights'])): 
                        highlightData = []
                        id = str(categoriesObject[indexCategory][indexBook]['highlights'][n]['id'])
                        note = unidecode(categoriesObject[indexCategory][indexBook]['highlights'][n]['note'])
                        location = str(categoriesObject[indexCategory][indexBook]['highlights'][n]['location'])
                        location_type = categoriesObject[indexCategory][indexBook]['highlights'][n]['location_type']
                        tagsArray = categoriesObject[indexCategory][indexBook]['highlights'][n]['tags']
                        text = unidecode(categoriesObject[indexCategory][indexBook]['highlights'][n]['text'])
                        if "__" in text:
                            text = text.replace("__", "==")
                        # Add # for h1-h5 headings
                        listOfHeadings = ['#h1', '#h2', '#h3', '#h4', '#h5']
                        if any(item in tagsArray for item in listOfHeadings):
                            if any('#h1' in s for s in tagsArray):
                                highlightData.append("## " + text + "\n" + " ^" + id + "\n\n")
                                booksWithHeadings += 1
                            elif any('#h2' in s for s in tagsArray):
                                highlightData.append("### " + text + "\n" + " ^" + id + "\n\n")
                                booksWithHeadings += 1
                            elif any('#h3' in s for s in tagsArray):
                                highlightData.append("#### " + text + "\n" + " ^" + id + "\n\n")
                                booksWithHeadings += 1
                            elif any('#h4' in s for s in tagsArray):
                                highlightData.append("##### " + text + "\n" + " ^" + id + "\n\n")
                                booksWithHeadings += 1
                            elif any('#h5' in s for s in tagsArray):
                                highlightData.append("###### " + text + "\n" + " ^" + id + "\n\n")
                                booksWithHeadings += 1
                        else:
                            # Pre-pend a "> " character to any text with line breaks
                            # Or pre-pend a "> \" if line is empty
                            # This is to fix the issue where the block-reference doesn't pick-up parent items
                            if "\n" in text:
                                textNew = []
                                textSplit = text.split("\n") # type(highlight['text']) = 'list'
                                for s in range(len(textSplit)):
                                    if textSplit[s] == '':
                                        x = ("> \\" + textSplit[s])
                                    else:
                                        x = ("> " + textSplit[s])    
                                    textNew.append(x)
                                textNew = "\n".join(textNew)
                                highlightData.append(textNew + "\n\n" + "^" + id + "\n\n")
                            else: 
                                highlightData.append(text + " ^" + id + "\n\n")
                        if note == [] or note == "":
                            pass
                        else:
                            highlightData.append("**Note:** " + str(note) + "\n")
                        if tagsArray == [] or tagsArray == "":
                            pass
                        else:
                            tags = " ".join(str(v) for v in tagsArray)
                            highlightData.append("**Tags:** " + str(tags) + "\n")                    
                        if str(categoriesObject[indexCategory][indexBook]['highlights'][n]['url']) == "None":
                            pass
                        else:
                            url = str(categoriesObject[indexCategory][indexBook]['highlights'][n]['url'])
                            highlightData.append("**References:** " + str(url) + "\n")
                        if source == "podcasts" and str(url) != "None":
                            # Append 'embed/' after the 'airr.io/' string and before the '/quote/' string
                            airrQuoteMatchingPattern = 'airr.io/'
                            airrQuoteEmbedText = 'embed/'
                            if any(airrQuoteMatchingPattern in url for string in url): # Check if url is an AirrQuote
                                i = url.find(airrQuoteMatchingPattern) # Find index of matching pattern
                                podcastUrl = url[:i + len(airrQuoteMatchingPattern)] + airrQuoteEmbedText + url[i + len(airrQuoteMatchingPattern):]
                            else:
                                podcastUrl = url
                            iFrameWithPodcastUrl = '<iframe src="' + podcastUrl + '" frameborder="0" style="width:100%; height:100%;"></iframe>'
                            highlightData.append(iFrameWithPodcastUrl + "\n")
                        """
                        highlighted_at = datetime.strptime(categoriesObject[indexCategory][indexBook]['highlights'][n]['highlighted_at'][0:10], '%Y-%m-%d').strftime("%y%m%d %A") # Trim the UTC date field and re-format
                        updated = datetime.strptime(categoriesObject[indexCategory][indexBook]['highlights'][n]['updated'][0:10], '%Y-%m-%d').strftime("%y%m%d %A") # Trim the UTC date field and re-format
                        if highlighted_at == updated:
                            date = updated
                            highlightData.append("**Date:** " + "[[" + str(date) + "]]" + "\n")
                        else:
                            date = highlighted_at
                            highlightData.append("**Date:** " + "[[" + str(date) + "]]" + "\n")
                        """
                        highlightData.append("\n" + "---" + "\n")
                        highlightData = "".join(highlightData)
                        print(highlightData, file=newFile)
                print(' - "' + str(title) + '"')
    os.chdir(sourceDirectory) # Revert to original directory with script
    if str(booksWithHeadings) == '0':
        pass
    else:
        print(str(booksWithHeadings) + ' highlights converted into headings')
    if str(booksWithNoHighlights) == '0':
        pass
    else:
        print(str(booksWithNoHighlights) + ' books ignored as they contained no highlights')
    differenceMarkdownNoteAmount = newMarkdownNoteAmount - originalMarkdownNoteAmount
    message = str(differenceMarkdownNoteAmount) + ' new markdown notes created and ' + str(len(listOfBookIdsToUpdateMarkdownNotes) - differenceMarkdownNoteAmount) + ' markdown notes updated'
    # message = str(len(listOfBookIdsToUpdateMarkdownNotes)) + ' new markdown notes created'
    logDateTimeOutput(message)
    print(message)

##########################################################
### Calculate the number of new markdown notes created ###
##########################################################

def numberOfMarkdownNotes():
    counter = 0
    listCategories = list(categoriesObject)
    for i in range(len(listCategories)):
        counter += len(listCategories[i])
    return counter

#######################################################
### Import variables from file in another directory ###
#######################################################

# Import all variables from readwiseMetadata file
print('Importing variables from readwiseMetadata...')
from readwiseMetadata import token, targetDirectory, dateFrom, email, pwd, chromedriverDirectory, highlightLimitToFetchTags
# from readwiseMetadata import *

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

# Function to check if any of the optional input variables in readwiseMetadata are blank or missing
# If blank or missing, set boolean value to False and no tags will be fetched
fetchTagsBoolean = fetchTagsTrueOrFalse(fetchTagsBoolean, email)
fetchTagsBoolean = fetchTagsTrueOrFalse(fetchTagsBoolean, pwd)
fetchTagsBoolean = fetchTagsTrueOrFalse(fetchTagsBoolean, chromedriverDirectory)
fetchTagsBoolean = fetchTagsTrueOrFalse(fetchTagsBoolean, highlightLimitToFetchTags)

######################################
### Load book data from JSON files ###
######################################

articles = {}
books = {}
podcasts = {}
supplementals = {}
tweets = {}

categoriesObject = [articles, books, podcasts, supplementals, tweets] # type(categoriesObject[0]) = 'dictionary'

categoriesObjectNames = ["articles", "books", "podcasts", "supplementals", "tweets"] # type(categoriesObjectNames[0]) = 'string'

# Load existing readwise data from JSON files into categoriesObject
print('Loading data from JSON files in readwiseCategories to categoriesObject...')
loadBookDataFromJsonToObject()

originalMarkdownNoteAmount = numberOfMarkdownNotes() # Sum the original number of books in each dictionary

##################
### Books LIST ###
##################

# Readwise REST API information = 'https://readwise.io/api_deets'
# Readwise endpoint = 'https://readwise.io/api/v2/books/'

booksListQueryString = {
    "page_size": 1000, # 1000 items per page - maximum
    "page": 1, # Page 1 >> build for loop to cycle through pages and stop when complete
    "updated__gt": dateFrom, # if no date provided, it will default to dateLastScriptRun
}

# Trigger GET request with booksListQueryString
print('Fetching book data from readwise...')
booksList = requests.get(
    url="https://readwise.io/api/v2/books/", # endpoint provided by https://readwise.io/api_deets
    headers={"Authorization": "Token " + token}, # token imported from readwiseAccessToken file
    params=booksListQueryString # query string object
)

# Convert response into JSON object
try:
    print('Converting readwise book data returned into JSON...')
    booksListJson = booksList.json() # type(booksListJson) >> 'dict' https://docs.python.org/3/tutorial/datastructures.html#dictionaries
except ValueError:
    message = 'Response content from booksList request is not valid JSON'
    logDateTimeOutput(message)
    print(message) # Originally from https://github.com/psf/requests/issues/4908#issuecomment-627486125
    # JSONDecodeError: Expecting value: line 1 column 1 (char 0) specifically happens with an empty string (i.e. empty response content)

try:
    # Create new object of booksListJson['results']
    booksListResults = booksListJson['results'] # type(booksListResults) = 'list'
except NameError:
    message = 'Cannot extract results from empty JSON for booksList request'
    logDateTimeOutput(message)
    print(message)

# Loop through pagination using 'next' property from GET response
try: 
    additionalLoopCounter = 0
    while booksListJson['next']:
        additionalLoopCounter += 1
        print('Fetching additional book data from readwise... (page ' + str(additionalLoopCounter) + ')')
        booksList = requests.get(
            url=booksListJson['next'], # keep same query parameters from booksListQueryString object
            headers={"Authorization": "Token " + token}, # token imported from readwiseAccessToken file
        )
        try:
            print('Converting additional readwise book data returned into JSON... (page ' + str(additionalLoopCounter) + ')')
            booksListJson = booksList.json() # type(booksListJson) = 'dictionary'
        except ValueError:
            message = 'Response content from additional booksList request is not valid JSON'
            logDateTimeOutput(message)
            print(message) # Originally from https://github.com/psf/requests/issues/4908#issuecomment-627486125
            # JSONDecodeError: Expecting value: line 1 column 1 (char 0) specifically happens with an empty string (i.e. empty response content)
            break
        try:
            # Create dictionary of highlightsListJson['results']
            booksListResults.extend(booksListJson['results']) # type(booksListJson) = 'list'
        except NameError:
            message = 'Cannot extract results from empty JSON for additional booksList request'
            logDateTimeOutput(message)
            print(message)
            break
except NameError:
    message = 'Cannot loop through pagination from empty response'
    logDateTimeOutput(message)
    print(message)

# Sort booksListResults data by 'category' key
print('Sorting readwise book data by category...')
booksListResultsSort = sorted(booksListResults, key = itemgetter('category')) # e.g. 'category' = 'books'

# Group booksListResults data by 'category' key
print('Grouping readwise book data by category...')
booksListResultsGroup = groupby(booksListResultsSort, key = itemgetter('category'))

# Append new books to categoriesObject, or update existing book data
print('Appending readwise book data returned to categoriesObject...')
appendBookDataToObject()

#######################
### Highlights LIST ###
#######################

# Readwise REST API information = 'https://readwise.io/api_deets'
# Readwise endpoint = 'https://readwise.io/api/v2/highlights/'

# Create highlightsList query string:
highlightsListQueryString = {
    "page_size": 1000, # 1000 items per page - maximum
    "page": 1, # Page 1 >> build for loop to cycle through pages and stop when complete
    "highlighted_at__gt": dateFrom, 
}

# Trigger GET request with highlightsListQueryString
print('Fetching highlight data from readwise...')
highlightsList = requests.get(
    url="https://readwise.io/api/v2/highlights/",
    headers={"Authorization": "Token " + token}, # token imported from readwiseAccessToken file
    params=highlightsListQueryString # query string object
)

# Convert response into JSON object
try:
    print('Converting readwise highlight data returned into JSON...')
    highlightsListJson = highlightsList.json() # type(highlightsListJson) = 'dictionary'
except ValueError:
    message = 'Response content is not valid JSON'
    logDateTimeOutput(message)
    print(message) # Originally from https://github.com/psf/requests/issues/4908#issuecomment-627486125
    # JSONDecodeError: Expecting value: line 1 column 1 (char 0) specifically happens with an empty string (i.e. empty response content)

try:
    # Create dictionary of highlightsListJson['results']
    highlightsListResults = highlightsListJson['results'] # type(highlightsListResults) = 'list'
except NameError:
    message = 'Cannot extract results from empty JSON'
    logDateTimeOutput(message)
    print(message)

try:
    # Loop through pagination using 'next' property from GET response
    additionalLoopCounter = 0
    while highlightsListJson['next']:
        additionalLoopCounter += 1
        print('Fetching additional highlight data from readwise... (page ' + str(additionalLoopCounter) + ')')
        highlightsList = requests.get(
            url=highlightsListJson['next'], # keep same query parameters from booksListQueryString object
            headers={"Authorization": "Token " + token}, # token imported from readwiseAccessToken file
        )
        # Convert response into JSON object
        try:
            print('Converting additional readwise highlight data returned into JSON... (page ' + str(additionalLoopCounter) + ')')
            highlightsListJson = highlightsList.json() # type(highlightsListJson) = 'dictionary'
        except ValueError:
            message = 'Response content is not valid JSON'
            logDateTimeOutput(message)
            print(message) # Originally from https://github.com/psf/requests/issues/4908#issuecomment-627486125
            # JSONDecodeError: Expecting value: line 1 column 1 (char 0) specifically happens with an empty string (i.e. empty response content)
            break
        try:
            # Create dictionary of highlightsListJson['results']
            highlightsListResults.extend(highlightsListJson['results']) # type(highlightsListResults) = 'list'
        except NameError:
            message = 'Cannot extract results from empty JSON'
            logDateTimeOutput(message)
            print(message)
            break
except NameError:
    message = 'Cannot loop through pagination from empty response'
    logDateTimeOutput(message)
    print(message)

# Replace "location" and "location_type" fields with no values as this will otherwise block highlight data sorting and grouping
replaceNoneInListOfDict(highlightsListResults)

# Sort highlightsListResults data by 'book_id' key and 'location'
print('Sorting readwise highlight data by category...')
highlightsListResultsSort = sorted(highlightsListResults, key = itemgetter('book_id', 'location'))

# Group highlightsListResultsSort data by 'category' key
print('Grouping readwise highlight data by category...')
highlightsListResultsGroup = groupby(highlightsListResultsSort, key = itemgetter('book_id'))

listOfBookIdsToUpdateMarkdownNotes = [] # Append 'book ids' to loop through when creating new or updating existing markdown notes

# Append new highlights to categoriesObject, or update existing highlight data
print('Appending readwise highlight data returned to categoriesObject...')
appendHighlightDataToObject()

allHighlightsToFetchTagsFor = [] # Append values from 'highlightsListResultsSort' and 'missingHighlightsListResultsSort' into this list
missingHighlightsListToFetchTagsFor = [] # Append values from 'missingHighlightsListResultsSort' into this list
allHighlightsToFetchTagsForSortByDate = []

def appendHighlightsToListForFetchingTags(originalList, highlightsListToAppend):
    # allHighlightsToFetchTagsFor = [allHighlightsToFetchTagsFor.append(highlightsListToAppend)
    for i in range(len(highlightsListToAppend)):
        originalList.append(highlightsListToAppend[i])

appendHighlightsToListForFetchingTags(allHighlightsToFetchTagsFor, highlightsListResultsSort)

print('Appending updated highlight data to categoriesObject...')
appendUpdatedHighlightsToObject()

#########################################################
### Fetch tags individually or in bulk via CSV export ###
#########################################################

# appendTagsToHighlightObject(highlightsListResultsSort)

# If num of highlights in 'highlightsListResultsSort' is greater than limit specified in 'highlightLimitToFetchTags', fetch tags via CSV export
# Otherwise web scrape tags individually via Selenium
def fetchTagsIndividuallyOrInBulk():
    if fetchTagsBoolean is True:
        try:
            if len(allHighlightsToFetchTagsFor) > highlightLimitToFetchTags:
                message = 'Fetching tags for ' + str(len(allHighlightsToFetchTagsFor)) + ' highlights in bulk via CSV export...'
                logDateTimeOutput(message)
                print(message)
                list_Highlight, list_BookTitle, list_BookAuthor, list_AmazonBookId, list_Note, list_Color, list_Tags, list_LocationType, list_Location, \
                list_HighlightedAt, list_ReadwiseBookId, list_Source, list_Url, list_NumberOfHighlights, list_UpdatedAt, list_HighlightId = runFetchCsvData()
                # runFetchCsvData()
                allHighlightsToFetchTagsForSortByDate, list_extractedHighlightTags, list_extractedHighlightText, list_extractedHighlightId, list_extractedHighlightLocation, \
                list_extractedHighlightedAt, list_extractedHighlightBookId, list_noMatchingHighlightIdFromText, list_duplicateHighlightTextValues = \
                runExtractDataFromApi(list_Highlight, list_BookTitle, list_BookAuthor, list_AmazonBookId, list_Note, list_Color, list_Tags, list_LocationType, \
                list_Location, list_HighlightedAt, list_ReadwiseBookId, list_Source, list_Url, list_NumberOfHighlights, list_UpdatedAt, list_HighlightId)
                # runFetchTagsFromCsvData()
                runFetchTagsFromCsvData(list_Highlight, list_BookTitle, list_BookAuthor, list_AmazonBookId, list_Note, list_Color, list_Tags, list_LocationType, \
                    list_Location, list_HighlightedAt, list_ReadwiseBookId, list_Source, list_Url, list_NumberOfHighlights, list_UpdatedAt, list_HighlightId, \
                    list_extractedHighlightTags, list_extractedHighlightText, list_extractedHighlightId, list_extractedHighlightLocation, list_extractedHighlightedAt, \
                    list_extractedHighlightBookId, list_noMatchingHighlightIdFromText, list_duplicateHighlightTextValues)
            elif len(allHighlightsToFetchTagsFor) <= highlightLimitToFetchTags:
                message = 'Fetching tags for ' + str(len(allHighlightsToFetchTagsFor)) + ' highlights individually...'
                logDateTimeOutput(message)
                print(message)
                appendTagsToHighlightObject(highlightsListResultsSort)
                appendTagsToHighlightObject(missingHighlightsListToFetchTagsFor)
            else:
                message = 'Error trying to determine whether to fetch tags individually or in bulk'
                logDateTimeOutput(message)
                print(message)
        except (OSError, ValueError):
            return
    else:
        return

if fetchTagsBoolean is True:
    fetchTagsIndividuallyOrInBulk() # Function to determine whether to fetch tags individually or in bulk
    removeHighlightsWithDiscardTag() # Function to remove highlights from categoriesObject which contain 'discard' tag
    appendHashtagToTags() # Function to append a hashtag to the start of every tag (if they are missing)
else:
    message = 'No tags fetched as one of the input variables required in readwiseMetadata is blank or invalid'
    logDateTimeOutput(message)
    print(message)

# Export books with updated highlights to JSON files
appendBookAndHighlightObjectToJson()

############################
### Create markdown note ###
############################

newMarkdownNoteAmount = numberOfMarkdownNotes() # Sum the new number of books in each dictionary

print('Creating or updating markdown notes...')

createMarkdownNote(listOfBookIdsToUpdateMarkdownNotes)

###############################################
### Print script completion time to console ###
###############################################

os.chdir(sourceDirectory)

message = 'Script complete'
logDateTimeOutput(message)
print(message)
