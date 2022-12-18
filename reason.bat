cd results
java -Xmx16G -Xms2G -Xss1G -jar %Robot%/robot.jar reason -i cpe23.owl --reasoner whelk -o cpe23c.omn --axiom-generators "SubClass EquivalentClass DisjointClasses"
java -Xmx16G -Xms2G -Xss1G -jar %Robot%/robot.jar reason -i cpe23c.omn --reasoner whelk -o cpe23d.omn --axiom-generators "DataPropertyCharacteristic EquivalentDataProperties SubDataProperty"
java -Xmx16G -Xms2G -Xss1G -jar %Robot%/robot.jar reason -i cpe23d.omn --reasoner whelk -o cpe23i.omn --axiom-generators "ClassAssertion PropertyAssertion"
java -Xmx16G -Xms2G -Xss1G -jar %Robot%/robot.jar reason -i cpe23i.omn --reasoner whelk -o cpe23.omn --axiom-generators "EquivalentObjectProperty InverseObjectProperties ObjectPropertyCharacteristic SubObjectProperty ObjectPropertyRange ObjectPropertyDomain"
cd ..
