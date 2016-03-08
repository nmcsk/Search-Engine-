import os, sys
from Stemmer import Stemmer
# Binary search
from bisect import bisect
import re
import math
import time

# Stopwords list
STOPWORDS = []
stem = Stemmer("english")
docParts = ["title", "body", "infobox", "references", "category", "external"]
sList = {}

# Total number of docs
noDocs = 0
COMMON = 20
# Inverse document frequency count
IDFC = 40
useALL = False
# Champion list cutoff
CL = 5000
# Top K docs
K = 10

# Total number of merged docs, per docPart
noMerged = []
docTitles = {}

def buildStopWords():
    global STOPWORDS
    with open("stopwords.txt", "r") as f:
        for line in f:
            word = line.strip("\n").strip()
            STOPWORDS.append(word)

def buildDocTitles():
    global docTitles
    with open("indexed/docTitles", "r") as f:
        for line in f:
            line = line.strip("\n").strip()
            did, dtitle = line.split("|")
            docTitles[did] = dtitle

def buildSecondaryList():
    global sList
    for part in docParts:
        sList[part] = []
        with open("indexed/" + part + "/secondary", "r") as f:
            for line in f:
                line = line.strip("\n").strip()
                sList[part].append(line)

def readDetails():
    global noMerged, noDocs
    with open("indexed/details", "r") as f:
        for line in f:
            line = line.strip("\n").strip()
            if ":" in line:
                # First line of details, split by ":"
                noMerged = line.split(":")
            else:
                # Number of docs
                noDocs = int(line)

def tokenize(string):
    # Keep stopwords in query ?
    global STOPWORDS
    regex = r'\d+|[A-Za-z]+'
    # Convert the string to lowercase
    string = string.lower()
    t = re.findall(regex, string)
    tokens = [stem.stemWord(word.strip()) for word in t \
                    if word != '' and word.strip() not in STOPWORDS]
    return tokens

def expand(f):
    for part in docParts:
        if part[0] == f:
            return part
    # Default
    return "body"

def pref(field, qType):
    #if qType == "field":
    #    return 1
    if True:
        # High Priority
        if field == "title":
            return 36
        elif field == "body":
            return 25
        elif field == "infobox":
            return 16
        elif field == "category":
            return 9
        elif field == "references":
            return 4
        # Lowest as page redirects to another page
        elif field == "external":
            return 1

def getDocCount(qword):

    field = "body"
    fIndex = bisect(sList[field], qword)
    # Better way?
    if fIndex == 0:
        if qword <= sList[field][0]:
            fIndex = 1
        else:
            fIndex = 2
    else:
        if sList[field][fIndex-1] == qword:
            fIndex = fIndex
        else:
            fIndex += 1

    # Now we have file Index, open File
    with open("indexed/" + field + "/merged" + str(fIndex)) as f:
        for line in f:
            eqS = line.strip("\n").split("=")
            if qword == eqS[0]:
                return int(eqS[1][:eqS[1].find("$")])

    # Not found in body    
    return 0

def runSearch(queryDict, qType, flag):

    documents = {}
    docSet = {}
    # Search for the words in queryDict
    for qword in queryDict:
        docSet[qword] = []
        # Search for qword
        for field in queryDict[qword]:
            # Search according to field
            # Find the query term in the file
            if qword > sList[field][-1]:
                # Will not find the word
                continue
            fIndex = bisect(sList[field], qword)
            # Better way?
            if fIndex == 0:
                if qword <= sList[field][0]:
                    fIndex = 1
                else:
                    fIndex = 2
            else:
                if sList[field][fIndex-1] == qword:
                    fIndex = fIndex
                else:
                    fIndex += 1

            # Now we have file Index, open File
            with open("indexed/" + field + "/merged" + str(fIndex)) as f:
                for line in f:
                    eqS = line.strip("\n").split("=")
                    if qword == eqS[0]:
                        # Doc count from current posting list
                        docCount = int(eqS[1][:eqS[1].find("$")])
                        # Doc count from body also
                        if useALL:
                            allDocCount = max(getDocCount(qword), docCount)
                            idf = noDocs/allDocCount
                        else:
                            idf = noDocs/docCount
                        if idf >= IDFC or flag:
                            # Consider the term, rare enough
                            # Find the TF-IDF Scores
                            # Our indexing is already sorted
                            # Take champion list, (set a certain threshold)
                            docs = eqS[1].split("$")[1:]
                            for doc_idx in xrange(0, min(CL, docCount)):
                                did, tf = docs[doc_idx].split(":")
                                docSet[qword].append(did)
                                # Score
                                # TF * IDF * Preference between different fields
                                score = (1 + math.log(int(tf))) * math.log(idf) * pref(field, qType)
                                #print docTitles[did], score
                                if did in documents:
                                    documents[did] += score
                                else:
                                    documents[did] = score

                        # We've found the word and we can break
                        break

    if len(queryDict.keys()) >= 2:
        # Find intersection, only for normal queries
        docSetList = []
        for qword in docSet:
            docSetList.append(set(docSet[qword]))

        if len(docSetList) >= 1:
            docList = list(set.intersection(*docSetList))
            for inter in docList:
                # Add a high score to the documents that appear in intersection
                documents[inter] += COMMON
    
    return documents

def search():

    print ">",
    # Take number of queries from user
    noQ = input()
    # All possible search fields
    allFields = docParts[:]

    for Q in xrange(0, noQ):

        print ">",
        query = raw_input()
        start = time.time()
        # Query word list
        wl = []
        # Query type
        qType = ""
        # Contains query words to search fields mapping
        queryDict = {}
        # Stores all the relevant docs with their scores
        documents = {}

        # Parse the query
        if ":" in query:
            qType = "field"
            # Field query
            # Field query's are split by ,
            temp = query.split(",")
            for qw in temp:
                field, qwords = qw.split(":")
                # For each qword
                qwords = tokenize(qwords)
                # QWords is now a list of query words
                for qword in qwords:
                    if qword not in queryDict:
                        queryDict[qword] = [expand(field)]
                    else:
                        queryDict[qword].append(expand(field))

        else:
            qType = "normal"
            # Normal query
            qwords = tokenize(query)
            for qword in qwords:
                # Search in all parts
                queryDict[qword] = allFields

        # Run search on the query dict        
        documents = runSearch(queryDict, qType, False)
        
        # Sort docs based on Document scores
        sortedDocs = sorted(documents.iterkeys(),
                            reverse=True,
                            key=lambda x: documents[x])

        print "Results "
        counter = 0
        # Print top 10 documents
        for docID in sortedDocs:
            print "- " + str(int(docID, 16)) + ": " + docTitles[docID]
            counter += 1
            # Top K docs
            if counter == K:
                break

        if counter == 0:
            documents = runSearch(queryDict, qType, True)
            sortedDocs = sorted(documents.iterkeys(),
                                reverse=True,
                                key=lambda x: documents[x])
            # Print top 10 documents
            for docID in sortedDocs:
                print "> " + str(int(docID, 16)) + ": " + docTitles[docID]
                counter += 1
                # Top K docs
                if counter == K:
                    break

        if counter == 0:
            print "No documents found"
        end = time.time()
        print "Time taken: ", end - start
        
def run():

    # Prepopulate stopwords
    buildStopWords()

    # fill in Doc Titles
    buildDocTitles()

    print "Loading doc titles"
    
    # fill in the secondary index values into a list
    buildSecondaryList()

    # Gives us number of total docs and number of 
    # merged files per docPart
    readDetails()

    # Search, take input
    search()

if __name__ == "__main__":
    run()
