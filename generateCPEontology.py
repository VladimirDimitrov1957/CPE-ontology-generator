"""CPE ontology generator.

The generator downloads the current version of CPE Dictionary from NIST site and then generates OWL Manchester syntax ontology.
The dictionary is downloaded as .zip file and then it is unzipped.
The ontology is generated with the file name "cwe23.owl".
All operations and files are placed in the current directory.
"""

import urllib.request, re, sys, zipfile, argparse
import xml.etree.ElementTree as etree
from datetime import datetime
from multiprocessing import Process, Queue, Manager, cpu_count, freeze_support

def downloadCPE23():
        url = "https://nvd.nist.gov/feeds/xml/cpe/dictionary/official-cpe-dictionary_v2.3.xml.zip"
        fileName = "official-cpe-dictionary_v2.3.xml.zip"
        with urllib.request.urlopen(url) as response:
                contents = response.read()
                with open(fileName, mode='wb') as out_file:
                        out_file.write(contents)
        with zipfile.ZipFile(fileName, 'r') as zip_ref:
            zip_ref.extractall()

def parseXML():
        xml_fn = "official-cpe-dictionary_v2.3.xml"
        tree = etree.parse(xml_fn)
        return tree.getroot()

def generateShell(root):
        shell_fn = "shell.owl"
        
        with open(shell_fn, mode='r', encoding='utf-8') as in_file, open(owl_fn, mode='w', encoding='utf-8') as out_file:
                shell = in_file.read()
                generator = root.find(dict_string + "generator")
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

def getCPE23Names(root):
        CPE23Names = Manager().dict()
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
        for p in name_parts:
                p.replace("\r", ":")
        cpe, cpe_ver, part, vendor, product, version, update, edition, SW_edition, target_SW, target_HW, language, other = name_parts
        match = ":".join([cpe, cpe_ver] + list(map(makeRE, (part, vendor, product, version, update, edition, SW_edition, target_SW, target_HW, language, other))))
        for key in CPE23Names.keys():
                if re.search(match, key) is not None: CPE22Names.add(CPE23Names[key])
        return CPE22Names

def escape(s):
        r = s.replace("\\\\", "\r")
        r = r.replace("\\\"", "\n")
        r = r.replace("\\", "")
        r = r.replace("\r", "\\\\")
        return r.replace("\n", "\\\"")

def generateIndividual(CPE23Names, inQueue, outQueue):
        dp1 = "\t\t"
        dp2 = ",\r" + dp1
        not_def = {"-", "*"}
        item = inQueue.get()
        while item != "DONE":
                cpe22name = item.attrib["name"]
                result = "Individual: <" + cpe22name + ">\r\n"

                title = item.find(dict_string + "title")
                notes = item.find(dict_string + "notes")
                references = item.find(dict_string + "references")
                check = item.find(dict_string + "check")
                cpe23_item = item.find(ext_string + "cpe23-item")
                provenance_record = cpe23_item.find(ext_string + "provenance-record")
                if title is not None or notes is not None or references is not None or check is not None or provenance_record is not None:
                        result = result + "\tAnnotations:"       

                first = True
                for title in item.findall(dict_string + "title"):
                        if first:
                                first = False
                                result = result + "\r\t\ttitle \""
                        else:
                                result = result + ",\r\t\ttitle \""
                        result = result + title.text.replace("\"", "\\\"") + "\""
                        lang = title.attrib[lang_string]
                        if lang is not None: result = result + "@" + lang
                                
                for notes in item.findall(dict_string + "notes"):
                        lang = notes.attrib[lang_string]
                        for note in notes.findall(dict_string + "note"):
                                if first:
                                        first = False
                                        result = result + "\r\t\tnote \""
                                else:
                                        result = result + ",\r\t\tnote \""
                                result = result + note.text.replace("\"", "\\\"") + "\""
                                if lang is not None: result = result + "@" + lang
                                
                if references is not None:
                        for reference in references.findall(dict_string + "reference"):
                                if first:
                                        first = False
                                        result = result + "\r\t\treference \""
                                else:
                                        result = result + ",\r\t\treference \""
                                result = result + reference.text.replace("\"", "\\\"")
                                href = reference.attrib["href"]
                                if href is not None:
                                        result = result + "\rHREF: " + href
                                result = result + "\""

                for check in item.findall(dict_string + "check"):
                        if first:
                                first = False
                                result = result + "\r\t\tcheck \""
                        else:
                                result = result + ",\r\t\tcheck \""
                        result = result + check.text.replace("\"", "\\\"") + "\rSystem: " + check.attrib["system"]
                        if "href" in check.attrib: result = result + "\rHREF: " + check.attrib["href"]
                        result = result + "\""

                for provenance_record in item.findall(dict_string + "provenance-record"):
                        if first:
                                first = False
                                result = result + "\r\t\tprovenance-record \""
                        else:
                                result = result + ",\r\t\tprovenance-record \""
                        submitter = provenance_record.find(dict_string + "submitter")
                        result = result + "\rSubmitter:\r\t" + submitter.text.replace("\"", "\\\"")
                        result = result + "\r\tName: " + submitter.attrib["name"]
                        result = result + "\r\tSystem-ID: " + submitter.attrib["system-id"]
                        result = result + "\r\tDate: " + submitter.attrib["date"]
                        for authority in provenance_record.findall(dict_string + "authority"):
                                result = result + "\rAuthority:\r\t" + authority.text.replace("\"", "\\\"")
                                result = result + "\r\tName: " + authority.attrib["name"]
                                result = result + "\r\tSystem-ID: " + authority.attrib["system-id"]
                                result = result + "\r\tDate: " + authority.attrib["date"]
                        for change_description in provenance_record.findall(dict_string + "change-description"):
                                result = result + "\rChange description:\r\tType" + change_description.attrib["change-type"]
                                if "date" in change_description.attrib: result = result + "\r\tDate: " + change_description.attrib["date"]
                                evidence_reference = change_description.find(dict_string + "evidence-reference")
                                if evidence_reference is not None:
                                        result = result + "\r\tEvidence: " + evidence_reference.text.replace("\"", "\\\"")
                                        result = result + "\r\tEvidence type: " + evidence_reference.attrib["evidence"]
                                comments = change_description.find(dict_string + "comments")
                                if comments is not None:
                                        result = result + "\r\tComments: " + comments.text.replace("\"", "\\\"")
                        result = result + "\""

                name_parts = cpe23_item.attrib["name"].replace("\\:", "\r").split(":")
                for p in name_parts:
                        p.replace("\r", ":")
                cpe, cpe_ver, part, vendor, product, version, update, edition, SW_edition, target_SW, target_HW, language, other = name_parts

                result = result + "\r\n\tTypes:\r\t\t"
                if part == "a":
                        result = result + "Application"
                elif part == "o":
                        result = result + "OS"
                elif part == "h":
                        result = result + "Hardware"
                else:
                        raise ValueError(cpe23name + "=>" + part)
                        
                if "deprecated" in item.attrib:
                        result = result + "\r\t\tand Deprecated\r\n"
                else:
                        result = result + "\r\n"

                result = result + "\tFacts:\r"
                result = result + dp1 + "vendor \"" + escape(vendor) + "\",\r"
                result = result + dp1 + "product \"" + escape(product) + "\",\r"                                
                result = result + dp1 + "version \"" + escape(version) + "\""                                
                if update in not_def:
                        if update == "-": result = result + dp2 + "update \"\""
                else:
                        result = result + dp2 + "update \"" + escape(update) + "\""
                if edition in not_def:
                        if edition == "-": result = result + dp2 + "edition \"\""
                else:
                        result = result + dp2 + "edition \"" + escape(edition) + "\""                                
                if SW_edition in not_def:
                        if SW_edition == "-": result = result + dp2 + "edition \"\""
                else:
                        result = result + dp2 + "SW_edition \"" + escape(SW_edition) + "\""                                
                if target_SW in not_def:
                        if target_SW == "-": result = result + dp2 + "target_SW \"\""
                else:
                        result = result + dp2 + "target_SW \"" + escape(target_SW) + "\""                                
                if target_HW in not_def:
                        if target_HW == "-": result = result + dp2 + "target_HW \"\""
                else:
                        result = result + dp2 + "target_HW \"" + escape(target_HW) + "\""                                
                if language in not_def:
                        if language == "-": result = result + dp2 + "language \"\""
                else:
                        result = result + dp2 + "language \"" + language + "\""                                
                if other in not_def:
                        if other == "-": result = result + dp2 + "other \"\""
                else:
                        result = result + dp2 + "other \"" + escape(other) + "\""                    

                if "deprecation_date" in item.attrib: result = result + dp2 + "deprecation_date \"" + item.attrib["deprecation_date"] + "\"^^xsd:dateTime"
                
                deprecated_by = item.attrib.get("deprecated_by")
                if deprecated_by is not None: result = result + ",\r\t\tdeprecated_by <" + deprecated_by + ">"

                no = 1
                for deprecation in cpe23_item.findall(ext_string + "deprecation"):
                       dname = cpe22name + str(no)
                       for deprecatedBy in deprecation.findall(ext_string + "deprecated-by"):
                               result = result + ",\r\t\tdeprecation <" + dname + ">"
                               no += 1

                no = 1
                for deprecation in cpe23_item.findall(ext_string + "deprecation"):
                        dname = cpe22name + str(no)
                        for deprecatedBy in deprecation.findall(ext_string + "deprecated-by"):
                                result = result + "\r\nIndividual: <" + dname + ">\r\n\tTypes:\r\t\t"
                                deprecation_type = deprecatedBy.attrib.get("type")
                                if deprecation_type == "NAME_CORRECTION":
                                        result = result + "NameCorrection"
                                elif deprecation_type == "NAME_REMOVAL":
                                        result = result + "NameRemoval"
                                elif deprecation_type == "ADDITIONAL_INFORMATION":
                                        result = result + "AdditionalInformation"
                                result = result + "\r\n\tFacts:\r"
                                first = True
                                for cpe22 in getByWildCards(CPE23Names, deprecatedBy.attrib["name"]):
                                        if cpe22 != cpe22name:
                                                if first:
                                                        result = result + dp1 + "deprecated-by <" + cpe22 + ">"
                                                        first = False
                                                else:
                                                        result = result + ",\r\t\tdeprecated-by <" + cpe22 + ">"
                        
                outQueue.put(result + "\r\n")
                item = inQueue.get()

def writeResults(q):
        with open(owl_fn, mode='a', encoding='utf-8') as out_file:
                msg = q.get()
                while msg != "DONE":
                        out_file.write(msg)
                        msg = q.get()

def generateIndividuals(root):
        CPE23Names = getCPE23Names(root)
        outQueue = Queue()
        inQueue = Queue()

        print("Processing started")
        writer = Process(name="Writer", target=writeResults, args=(outQueue,))
        writer.start()

        processes = []
        np = cpu_count()
        for i in range(np):
                p = Process(name="Process " + str(i), target=generateIndividual, args=(CPE23Names, inQueue, outQueue))
                processes.append(p)
                p.start()
                
        for item in root.findall(dict_string + "cpe-item"):
                print(item.attrib["name"])
                inQueue.put(item)
        print("Processing finished")
        for i in range(np):
                inQueue.put("DONE")
        for i in range(np):
                processes[i].join()

        outQueue.put("DONE")
        writer.join()

def main(download):
        print("CPE 2.3 Ontology Generator, Version 2.0")
        start = datetime.now()
        print(start)
        if download:
                print("Download CPE Dictionary")
                downloadCPE23()
        root = parseXML()
        print("Generate the shell")
        generateShell(root)
        print("Generate individuals")
        generateIndividuals(root)
        print("Generation end")
        end = datetime.now()
        print(end)
        print(f"Elapsed: {end - start}")

owl_fn = "cpe23.owl" # CPE ontology file name
dict_string = "{http://cpe.mitre.org/dictionary/2.0}"
ext_string = "{http://scap.nist.gov/schema/cpe-extension/2.3}"
lang_string = "{http://www.w3.org/XML/1998/namespace}lang"

if __name__ == "__main__":
        freeze_support()
        parser = argparse.ArgumentParser()
        parser.add_argument('-d', '--download', action="store_true", help='download input from the Web')
        args = parser.parse_args()
        main(args.download)
