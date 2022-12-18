cd results
java -Xmx16G -Xms2G -Xss1G -jar %Robot%/robot.jar convert -i cpe23i.omn --format ttl -o cpe23.ttl
cd ..