import sys
import os
keywords = set()
behaviors = set()

for path, directories, files in os.walk(sys.argv[1]):
    for file in files:
        with open(os.path.join(path, file), "r", encoding="Latin-1") as f:
            lines = f.read().splitlines()

            for line in lines:
                if "=" not in line:
                    continue

                stuff = line.split("=")[0].strip()
                if any(x in stuff for x in [";", "//", "~", " "]) or stuff.isdigit():
                    continue 

                if stuff == "Behavior":
                    behavior = line.split()[2].strip()
                    behaviors.add(behavior)

                elif stuff == "Draw":
                    behavior = line.split()[2].strip()
                    behaviors.add(behavior)

                elif stuff == "Body":
                    behavior = line.split()[2].strip()
                    behaviors.add(behavior)
                else:
                    keywords.add(stuff)


# print(list(keywords))
# print(len(keywords))

print(list(behaviors))
print(len(behaviors))