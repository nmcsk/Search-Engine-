# Import the stemmer
from Stemmer import Stemmer
# Import the parser, using SAX Parser
import xml.sax
import sys, re, os
from heapq import heappush, heappop

# Global stem object, instantiate object
stem = Stemmer("english")
STOPWORDS = []
noFiles = 0
noDocs = 0
docParts = ["title", "body", "infobox", "references", "category", "external"]
noMerged = [0] * len(docParts)
# Make sure it is not there before
docTitleF = open("indexed/docTitles", "a")
docTitleString = ""

class WikipediaContentHandler(xml.sax.ContentHandler):

    def __init__(self):

        global docParts

        # Stores the content found inside the tags
        self.text = ""
        # Stores tag name
        self.tag = ""
        # Stores the order in which tags appear
        # <parent>
        #   <subparent>
        #     <element>
        # self.tagOrder = [parent, subparent, element]
        # Used to find the parent of the given element
        self.tags = []
    
        # Parts of a page or doc, like body, infobox, references
        self.doc = {}

        if not os.path.isdir("indexed/"):
            os.system("mkdir indexed/")
        
        # Words of all pages or docs organized as different parts
        self.parts = docParts
        self.docs = {}
        for part in self.parts:
            self.docs[part] = {}
            if not os.path.isdir("indexed/" + part):
                os.system("mkdir indexed/" + part)

        # Documents threshold, number of docs to stop saving in dict
        self.MAX = 5000
        # Total number of documents
        self.total_docs = 0
        # Count of documents read
        self.doc_count = 0
        # File Number, used to name split files
        self.fileNo = 1

    # Called when the text between XML tags are read
    def characters(self, line):
        # Take care of encoding
        #try:
        line = line.encode("utf-8")
        line = line.strip()
        if line:
            self.text += line + "\n"
        #except:
        #    print "MAJOR ERROR ALERT"
            # Can't save character, ignore it
        #    pass

    def startElement(self, name, attrs):
        self.tag = name
        self.tags.append(name)

    def endElement(self, name):
        # Tag got over

        global docTitleString, docTitleF

        if name == "title":
            title = self.text.strip().strip("\n")
            title = title.replace("\n", " ")
            self.doc["title"] = title

        if name == "id":

            # Find parent of tag
            if len(self.tags) > 1:
                parent = self.tags[-2]
            else:
                # Root element
                parent = ""

            # ID is present in revisions and contributors as well
            if parent == "page":
                self.doc["id"] = self.text.strip().strip("\n")
                try:
                    self.doc["hexid"] = hex(int(self.doc["id"]))
                except ValueError:
                    self.doc["id"] = self.doc["id"].replace("\n", "")
                    self.doc["hexid"] = hex(int(self.doc["id"]))
                docTitleString += self.doc["hexid"] + "|" + self.doc["title"] + "\n"

        if name == "page":
            # Document got over
            self.total_docs += 1
            self.doc_count += 1
            if self.doc_count == self.MAX:
                docTitleF.write(docTitleString)
                docTitleString = ""
                self.storeInFiles()
            # Clear document
            # self.doc.clear()
            # Auto clear as overwritten in every parse

        if name == "mediawiki":

            global noFiles, noDocs

            # XML Dump is over
            # However some docs may still be left over
            if self.docs["title"]:
                docTitleF.write(docTitleString)
                docTitleString = ""
                self.storeInFiles()

            # Set global variables
            noFiles = self.fileNo - 1
            noDocs = self.total_docs
            
        if name == "text":
            # Document content has ended, parse the contents
            self.doc["content"] = self.text
            self.parseDocContent()
            self.saveDocParts()

        # Remove element from self.tags
        self.tags.pop()
        # Cleanup
        self.text = ""

    ###########################################################################
    # Functions not called by sax parser, (not callbacks)
    # Helper functions
    def parseDocContent(self):

        lines = self.doc["content"].split("\n")
        infobox = ""
        body = ""
        references = ""
        external = ""
        category = ""
        inside = "None"
        no_lines = len(lines)
        infoFlag = False

        for line in lines:

            # Check if infobox has started
            if len(re.findall("{{\ ?[iI]nfobox.*", line)) >= 1:
                # Infobox has started !
                inside = "Infobox"
            # Check if References has started
            elif len(re.findall("==\ ?[rR]eference.*", line)) >= 1:
                inside = "References"
            # Check if External has started
            elif line.find("== External") != -1 or \
                 line.find("==External") != -1:
                inside = "External"
            # Check if category has started
            elif line.find("[[Category") != -1:
                inside = "Category"
            # Others
            elif line.find("==") != -1:
                inside = "None"
 
            if inside == "Infobox":
                infobox += line + "\n"
                if "}}" in line:
                    inside = "None"
            elif inside == "References":
                references += line + "\n"
            elif inside == "External":
                external += line + "\n"
            elif inside == "Category":
                c = line.split(":")
                try:
                    category += c[1][:-2].strip() + "\n"
                except:
                    # ignore
                    pass
                # Categories end within one line
                inside = "None"
            else:
                body += line + "\n"

        # Title
        self.doc["title"] = self.tokenize(self.doc["title"])
        # Infobox
        self.doc["infobox"] = self.tokenize(infobox)
        # Body
        self.doc["body"] = self.tokenize(body)
        # References
        self.doc["references"] = self.tokenize(references)
        # Categories
        self.doc["category"] = self.tokenize(category)
        # External links
        self.doc["external"] = self.tokenize(external)
        
    def tokenize(self, string):
        global STOPWORDS
        regex = r'\d+|[A-Za-z]+'
        # Convert the string to lowercase
        string = string.lower()
        t = re.findall(regex, string)
        tokens = [stem.stemWord(word.strip()) for word in t \
                                if word != '' and word.strip() not in STOPWORDS]
        return tokens

    def saveDocParts(self):
        add = self.addDocPart
        for part in self.parts:
            add(part)

    def addDocPart(self, part):
        tokens = set(self.doc.get(part, []))
        for token in tokens:
            if token not in self.docs[part]:
                self.docs[part][token] = "1$" + self.doc["hexid"] + ":" + str(self.doc[part].count(token))
            else:
                docCountLoc = self.docs[part][token].find("$")
                docCount = self.docs[part][token][:docCountLoc]
                newCount = str(int(docCount) + 1)
                self.docs[part][token] = newCount + self.docs[part][token][docCountLoc:] + \
                                            "$" + self.doc["hexid"] + ":" + str(self.doc[part].count(token))

    def storeInFiles(self):
        files = {}
        # Document count has reached maximum threshold value
        # Store in files
        for part in self.parts:
            files[part] = open("indexed/" + part + "/" + "file" + str(self.fileNo), "w")

        for part in self.parts:
            for word in sorted(self.docs[part].keys()):
                files[part].write(word + "=" + self.docs[part][word] + "\n")
            files[part].close()
            self.docs[part].clear()

        # Increment file no
        self.fileNo += 1
        # Reset doc count
        self.doc_count = 0

def buildStopWords():
    global STOPWORDS
    with open("stopwords.txt", "r") as f:
        for line in f:
            word = line.strip("\n").strip()
            STOPWORDS.append(word)

def splitIntoTuples(temp):
    j = temp.split(":")
    return (int(j[1]), j[0])

def mergeFiles():

    global docParts, noFiles, noDocs

    # Make sure no secondary files are there from before
    # As we are appending
    for part in docParts:
        os.system("rm indexed/" + part + "/secondary")

    MAXTokens = 2000
    tempParts = docParts[:]
    # End is added to take care of last edge case
    tempParts.append("END")
    tokenCount = 0
    
    
    for part in tempParts:

        noFiles_ = noFiles + 1
 
        # From previous parts, edge case
        if tokenCount != 0:

            mergedNo += 1
            mergedPtr = open(dir_ + "merged" + str(mergedNo), "w")
            mergedPtr.write(saveString)
            noMerged[midx] = mergedNo
            saveString = ""
            tokenCount = 0
            mergedPtr.close()

            secPtr = open(dir_ + "secondary", "a")
            secPtr.write(saveWord + "\n")
            secPtr.close()
            
        if part == "END":
            # Done with all parts
            break

        midx = tempParts.index(part)
        # MergedFileNo
        mergedNo = 0
        # Create filepointers for each file of each part
        # 1 indexed
        filePointers = [None] * noFiles_
        # Line taken from each part
        line = [None] * noFiles_
        # Directory path
        dir_ = "indexed/" + part + "/"
        # Get a line from each file

        for file_no in xrange(1, noFiles_):
            file_name = dir_ + "file" + str(file_no)
            filePointers[file_no] = open(file_name, "r")
            # Read a single line
            line[file_no] = filePointers[file_no].readline().split("\n")[0]
        
        # Once we have a line from each part
        # Sort the lines
        # All those File Numbers whose words are the same
        fNos = []
        fOver = [False] * noFiles_
        saveString = ""
        tokenCount = 0
        fOverCount = 0

        # Use a heap, maintains words per file
        myheap = []

        for file_no in xrange(1, noFiles_):
            if not fOver[file_no]:
                heappush(myheap, (line[file_no].split("=")[0], file_no))

        # Till all the files are not over
        while myheap:

            ele = heappop(myheap)
            saveWord = ele[0]
            fNos = [ele[1]]

            # Add all those file nos that also have the same word
            while myheap:
                ele = heappop(myheap)
                if ele[0] != saveWord:
                    heappush(myheap, ele)
                    break
                else:
                    fNos.append(ele[1])
                
            union = ""
            # Concat all postings from different files
            totalDocCount = 0
            for fno in fNos:
                postings = line[fno].split("=")[1]
                docCountLoc = postings.find("$")
                totalDocCount += int(postings[:docCountLoc])
                union += "$" + postings[docCountLoc+1:]

            # Sort the union
            docs = union[1:].split("$")
            docPair = map(splitIntoTuples, docs)
            docPair.sort(reverse=True)
            mainString = ""
            for fq, did in docPair:
                mainString += "$" + did + ":" + str(fq)

            union = saveWord + "=" + str(totalDocCount) + mainString
            saveString += union + "\n"
            tokenCount += 1

            if tokenCount == MAXTokens:
                mergedNo += 1
                mergedPtr = open(dir_ + "merged" + str(mergedNo), "w")
                mergedPtr.write(saveString)
                noMerged[midx] = mergedNo
                saveString = ""
                tokenCount = 0
                mergedPtr.close()
                
                secPtr = open(dir_ + "secondary", "a")
                secPtr.write(saveWord + "\n")
                secPtr.close()

            for file_no in fNos:
                if not fOver[file_no]:
                    line[file_no] = filePointers[file_no].readline().split("\n")[0]
                    if line[file_no] == "":
                        # File has become empty
                        fOverCount += 1
                        fOver[file_no] = True
                        filePointers[file_no].close()
                        filePointers[file_no] = None
                    else:
                        heappush(myheap, (line[file_no].split("=")[0], file_no))


    # Write number of merged files to each detail part
    mString = str(noMerged[0])
    for i in xrange(1, len(noMerged)):
        mString += ":" + str(noMerged[i])
    mString += "\n"
    mString += str(noDocs) + "\n"

    dptr = open("indexed/details", "w")
    dptr.write(mString)
    dptr.close()


def cleanup():

    for part in docParts:
        os.system("rm indexed/" + part + "/file*")
    docTitleF.close()

def run():
    try:
        xml_file_name = sys.argv[1]
    except IndexError:
        print "XML file not passed as argument"
        sys.exit()

    # Populate Stop words list
    buildStopWords()

    # Start parsing the xml file
    parser = xml.sax.make_parser()
    parser.setContentHandler(WikipediaContentHandler())
    parser.parse(open(xml_file_name, "r"))
    mergeFiles()    
    cleanup()
    # Report size of index constructed
    os.system("du -sh indexed/")

if __name__ == "__main__":
    run()
