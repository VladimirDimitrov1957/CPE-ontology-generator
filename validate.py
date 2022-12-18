from pyshacl import validate
import rdflib
data_graph = "results/cpe23.ttl"
shape_graph = "cpe23shapes.ttl"
rfc5646_regex = "rfc5646.txt"
with open(data_graph, mode='r', encoding='utf-8') as dg, open(shape_graph, mode='r', encoding='utf-8') as sg, open(rfc5646_regex, mode='r', encoding='utf-8') as rg:
    data = dg.read();
    shapes = sg.read()
    rfc5646 = rg.read()
rfc5646 = rfc5646.replace("\n", "")
rfc5646 = rfc5646.replace("\t", "")
rfc5646 = rfc5646.replace(" ", "")
shapes = shapes.replace("RFC5646", rfc5646)
r = validate(data, shacl_graph=shapes, inference='both', data_graph_format="ttl", shacl_graph_format="ttl", meta_shacl=True, advanced=True, iterate_rules=True)
print(r[0])
print(r[1])
print(r[2])
