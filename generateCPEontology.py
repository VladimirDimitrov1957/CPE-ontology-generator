"""CPE ontology generator.

The generator downloads the current version of CPE Dictionary from NIST site and then generates OWL Turtle syntax ontology.
The dictionary is downloaded as .zip file and then it is unzipped.
The ontology is generated with the file name "cpe23.ttl".
All operations and files are placed in the current directory.
"""

import urllib.request, re, sys, zipfile, argparse
import xml.etree.ElementTree as etree
import xmlschema
from datetime import datetime
from multiprocessing import Process, Queue, Manager, cpu_count, freeze_support, Lock
from pathlib import Path

def codeString(s):
        temp = s.replace("\\", "\\\\")
        return temp.replace('"', '\\"')

def downloadCPE23():
        url = "https://nvd.nist.gov/feeds/xml/cpe/dictionary/official-cpe-dictionary_v2.3.xml.zip"
        fileName = "data/official-cpe-dictionary_v2.3.xml.zip"
        try:
                with urllib.request.urlopen(url) as response:
                        contents = response.read()
                        with open(fileName, mode='wb') as out_file:
                                out_file.write(contents)
                with zipfile.ZipFile(fileName, 'r') as zip_ref:
                    zip_ref.extractall(path="data")
        except Exception as err:
                print(f"Unexpected {err=}, {type(err)=}")
                exit

def parseXML():
        xml_fn = "data/official-cpe-dictionary_v2.3.xml"
        tree = etree.parse(xml_fn)
        return tree.getroot()

def getCPE23Names(root):
        CPE23Names = Manager().dict()
        CPE23Names = dict()
        for item in root.findall(dict_string + "cpe-item"):
                cpe23_item = item.find(ext_string + "cpe23-item")
                CPE23Names[cpe23_item.attrib["name"]] = item.attrib["name"]
        return CPE23Names

def makeRE(avstring):
        x = re.escape(avstring)
        x = x.replace(r"\*", "(.)*")
        x = x.replace(r"\?", "(.){0, 1}")
        return x

def getByWildCards(CPE23Names, wildCard):
        CPE22Names = set()
        name_parts = wildCard.replace("\\:", "\r").split(":")
        for i in range(len(name_parts)):
                name_parts[i] = name_parts[i].replace("\r", "\\:")
        cpe, cpe_ver, part, vendor, product, version, update, edition, language, SW_edition, target_SW, target_HW, other = name_parts
        match = ":".join([cpe, cpe_ver] + list(map(makeRE, (part, vendor, product, version, update, edition, language, SW_edition, target_SW, target_HW, other))))
        for key in CPE23Names.keys():
                if re.search(match, key) is not None: CPE22Names.add(CPE23Names[key])
        return CPE22Names

def escape(s):
        return (s.replace("\\", "\\\\")).replace('"', '\\"')

def clear(s):
        return s.replace("\\\\", "\n").replace("\\", "").replace('"', '\\"').replace("\n", "\\\\")

def generateIndividual(CPE23Names, inQueue, outQueue, separate, readLock):
        not_def = {"-", "*"}
        item = inQueue.get()
        
        while item != "DONE":
                if item == "NEXT_PART":
                        outQueue.put(item)
                        readLock.acquire()
                        item = inQueue.get()
                        readLock.release()
                        continue
                
                cpe22name = item.attrib["name"]

                print("Processing: " + cpe22name)
                        
                result = "\n###  " + cpe22name + "\n<" + cpe22name + ">\n\trdf:type owl:NamedIndividual"
                cpe23_item = item.find(ext_string + "cpe23-item")
                name_parts = cpe23_item.attrib["name"].replace("\\:", "\n").split(":")
                for i in range(len(name_parts)):
                        name_parts[i] = name_parts[i].replace("\n", ":")
                        if name_parts[i] and name_parts[i] != "*" and i != 3:
                                if name_parts[i] == "-": name_parts[i] = ""
                cpe, cpe_ver, part, vendor, product, version, update, edition, language, SW_edition, target_SW, target_HW, other = name_parts
                if "deprecated" in item.attrib:
                        result += " ;\n\trdf:type :Deprecated"
                else:
                        result += " ;\n\trdf:type :CPE"
                if part != "*":
                        if part == "a":
                                result += " ;\n\trdf:type :Application"
                        elif part == "o":
                                result += " ;\n\trdf:type :OS"
                        elif part == "h":
                                result += " ;\n\trdf:type :Hardware"
                        elif part == "":
                                result += " ;\n\trdf:type :NotAHO"
                        else:
                                raise ValueError(cpe23name + "=>" + part)
                for title in item.findall(dict_string + "title"):
                        result += " ;\n\t:title \"" + codeString(title.text) + "\""
                        lang = title.attrib[lang_string]
                        if lang is not None: result += "@" + lang
                for notes in item.findall(dict_string + "notes"):
                        lang = notes.attrib[lang_string]
                        for note in notes.findall(dict_string + "note"):
                                result += ' ;\n\t:note "' + codeString(note.text) + '"'
                                if lang is not None: result += "@" + lang
                references = item.find(dict_string + "references")
                if references is not None:
                        for reference in references.findall(dict_string + "reference"):
                                result += ' ;\n\t:reference """' + codeString(reference.text)
                                href = reference.attrib["href"]
                                if href is not None:
                                        result += "\nHREF: " + codeString(href)
                                result += '"""'
                for check in item.findall(dict_string + "check"):
                        result += ' ;\n\t:check """' + codeString(check.text)
                        result += codeString(check.text) + "\nSystem: " + codeString(check.attrib["system"])
                        if "href" in check.attrib: result += "\nHREF: " + codeString(check.attrib["href"])
                        result += '"""'
                for provenance_record in item.findall(dict_string + "provenance-record"):
                        result += ' ;\n\t:provenance-record """'
                        submitter = provenance_record.find(dict_string + "submitter")
                        result += "\nSubmitter:\n\t" + codeString(submitter.text)
                        result += "\n\tName: " + codeString(submitter.attrib["name"])
                        result += "\n\tSystem-ID: " + codeString(submitter.attrib["system-id"])
                        result += "\n\tDate: " + codeString(submitter.attrib["date"])
                        for authority in provenance_record.findall(dict_string + "authority"):
                                result += "\nAuthority:\n\t" + codeString(authority.text)
                                result += "\n\tName: " + codeString(authority.attrib["name"])
                                result += "\n\tSystem-ID: " + codeString(authority.attrib["system-id"])
                                result += "\n\tDate: " + codeString(authority.attrib["date"])
                        for change_description in provenance_record.findall(dict_string + "change-description"):
                                result += "\nChange description:\n\tType " + codeString(change_description.attrib["change-type"])
                                if "date" in change_description.attrib: result += "\n\tDate: " + codeString(change_description.attrib["date"])
                                evidence_reference = change_description.find(dict_string + "evidence-reference")
                                if evidence_reference is not None:
                                        result += "\n\tEvidence: " + codeString(evidence_reference.text)
                                        result += "\n\tEvidence type: " + codeString(evidence_reference.attrib["evidence"])
                                comments = change_description.find(dict_string + "comments")
                                if comments is not None:
                                        result += "\n\tComments: " + codeString(comments.text)
                        result += '"""'
                if vendor != "*": result += ' ;\n\t:vendor "' + clear(vendor) + '"'
                if product != "*": result += ' ;\n\t:product "' + clear(product) + '"'
                if version != "*": result += ' ;\n\t:version "' + clear(version) + '"'
                if update != "*": result += ' ;\n\t:update "' + clear(update) + '"'
                if edition != "*": result += ' ;\n\t:edition "' + clear(edition) + '"'
                if language != "*": result += ' ;\n\t:language "' + clear(language) + '"'
                if SW_edition != "*": result += ' ;\n\t:SW_edition "' + clear(SW_edition) + '"'
                if target_SW != "*": result += ' ;\n\t:target_SW "' + clear(target_SW) + '"'
                if target_HW != "*": result += ' ;\n\t:target_HW "' + clear(target_HW) + '"'
                if other != "*": result += ' ;\n\t:other "' + clear(other) + '"'
                if "deprecation_date" in item.attrib: result += ' ;\n\t:deprecation_date "' + item.attrib["deprecation_date"] + '"^^xsd:dateTime'

                deprecated_by = item.attrib.get("deprecated_by")
                if deprecated_by is not None: result += " ;\n\t:deprecated_by <" + deprecated_by + ">"

                no = 1
                for deprecation in cpe23_item.findall(ext_string + "deprecation"):
                       dname = cpe22name + "DEPREC" + str(no)
                       for deprecatedBy in deprecation.findall(ext_string + "deprecated-by"):
                               result += " ;\n\t:deprecation <" + dname + ">"
                               no += 1

                no = 1
                for deprecation in cpe23_item.findall(ext_string + "deprecation"):
                        dname = cpe22name + "DEPREC" + str(no)
                        for deprecatedBy in deprecation.findall(ext_string + "deprecated-by"):
                                result += " ;\n\trdf:type owl:Thing .\n###  " + dname + "\n<" + dname + ">\n\trdf:type owl:NamedIndividual"
                                deprecation_type = deprecatedBy.attrib.get("type")
                                if deprecation_type == "NAME_CORRECTION":
                                        result += " ;\n\trdf:type :NameCorrection"
                                elif deprecation_type == "NAME_REMOVAL":
                                        result += " ;\n\trdf:type :NameRemoval"
                                elif deprecation_type == "ADDITIONAL_INFORMATION":
                                        result += " ;\n\trdf:type :AdditionalInformation"
                                for cpe22 in getByWildCards(CPE23Names, deprecatedBy.attrib["name"]):
                                        if cpe22 != cpe22name:
                                                result += " ;\n\trdf:deprecated-by <" + cpe22 + ">"

                outQueue.put(result + " ;\n\trdf:type owl:Thing .\n")
                item = inQueue.get()

def writeResults(q, separate, np, lock, generator):

        def generateShell(out_file):

                with open("shell.ttl", mode='r', encoding='utf-8') as in_file:
                        shell = in_file.read()
                        if generator is not None:
                                product_name = generator.find(dict_string + "product_name")
                                product_name = "" if product_name is None else product_name.text
                                shell = shell.replace("PRODUCT_NAME", product_name)
                                product_version = generator.find(dict_string + "product_version")
                                product_version = "" if product_version is None else product_version.text
                                shell = shell.replace("PRODUCT_VERSION", product_version)
                                schema_version = generator.find(dict_string + "schema_version").text
                                shell = shell.replace("SCHEMA_VERSION", schema_version)
                                timestamp = generator.find(dict_string + "timestamp").text
                                shell = shell.replace("TIMESTAMP", timestamp)
                                out_file.write(shell)
                
        p = Path("results")
        try:
                p.mkdir()
        except FileExistsError as exc:
                print(exc)
                
        if separate:
                count = 1
                fn = "results/cpe23-" + str(count) + ".ttl"
                p = np
                lock.acquire()
        else:
                fn = "results/cpe23.ttl"
        out_file = open(fn, mode='w', encoding='utf-8')
        generateShell(out_file)
                
        msg = q.get()
        while msg != "DONE":
                if separate and msg == "NEXT_PART":
                        p -= 1
                        if p == 0:
                                out_file.close()
                                count += 1
                                fn = "results/cpe23-" + str(count) + ".ttl"
                                out_file = open(fn, mode='w', encoding='utf-8')
                                generateShell(out_file)
                                p = np
                                lock.release()
                                lock.acquire()
                else:
                        out_file.write(msg)
                msg = q.get()
        out_file.close()

def generateIndividuals(root, separate):

        def followChain(item):
                cpe23_item = item.find(ext_string + "cpe23-item")
                for deprecation in cpe23_item.findall(ext_string + "deprecation"):
                        for deprecatedBy in deprecation.findall(ext_string + "deprecated-by"):
                                for s in getByWildCards(CPE23Names, deprecatedBy.attrib["name"]):
                                        if s not in currentCPEnames:
                                                sItem = root.find(dict_string + "cpe-item[@name='" + s + "']")
                                                if sItem == None:
                                                        print("Not found: " + s)
                                                        continue
                                                inQueue.put(sItem)
                                                currentCPEnames.add(s)
                                                print("Deprecated by: " + s)
                                                if sItem.get("deprecated", default = False): followChain(sItem)
        #End followChain()
                
        CPE23Names = getCPE23Names(root)
        outQueue = Queue()
        inQueue = Queue()
        
        np = cpu_count()
        if separate:
                lock = Lock()
                readLocks = []
                currentCPEnames =  set()
        else:
                lock = None
                readLock = None

        print("Processing started")
        generator = root.find(dict_string + "generator")
        writer = Process(name="Writer", target=writeResults, args=(outQueue, separate, np, lock, generator))
        writer.start()
        
        print("Generate individuals")
        
        processes = []
        for i in range(np):
                if separate:
                        l = Lock()
                        readLocks.append(l)
                else:
                        l = None
                p = Process(name="Process " + str(i), target=generateIndividual, args=(CPE23Names, inQueue, outQueue, separate, l))
                processes.append(p)
                p.start()
                
        count = 0
        for item in root.findall(dict_string + "cpe-item"):
                if not writer.is_alive(): exit
                inQueue.put(item)
                if separate:
                        count += 1
                        currentCPEnames.add(item.attrib["name"])
                        if item.get("deprecated", default = False): followChain(item)
                        if count > 10000:
                                for i in range(np):
                                        readLocks[i].acquire()
                                for i in range(np):
                                        inQueue.put("NEXT_PART")
                                lock.acquire()
                                lock.release()
                                for i in range(np):
                                        readLocks[i].release()
                                count = 0
                                currentCPEnames = set()

        for i in range(np):
                inQueue.put("DONE")
        for i in range(np):
                processes[i].join()

        outQueue.put("DONE")
        writer.join()
        print("Processing finished")

def main(download, separate):
        print("CPE 2.3 Ontology Generator, Version 8.6")
        start = datetime.now()
        print(start)
        if download:
                print("Download CPE Dictionary")
                downloadCPE23()
        xs = xmlschema.XMLSchema("data/cpe-dictionary_2.3.xsd")
        if not xs.is_valid("data/official-cpe-dictionary_v2.3.xml"):
                print("CPE Dictionary contents is not valid!")
                xs.validate("data/official-cpe-dictionary_v2.3.xml")
                return
        root = parseXML()
        generateIndividuals(root, separate)
        print("Generation end")
        end = datetime.now()
        print(end)
        print(f"Elapsed: {end - start}")

dict_string = "{http://cpe.mitre.org/dictionary/2.0}"
ext_string = "{http://scap.nist.gov/schema/cpe-extension/2.3}"
lang_string = "{http://www.w3.org/XML/1998/namespace}lang"

if __name__ == "__main__":
        freeze_support()
        parser = argparse.ArgumentParser()
        parser.add_argument('-d', '--download', action="store_true", help='download input from the Web')
        parser.add_argument('-s', '--separate', action="store_true", help='separate CPE ontology in several parts')
        args = parser.parse_args()
        main(args.download, args.separate)
