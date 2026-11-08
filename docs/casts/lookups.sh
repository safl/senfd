# Ask senfd's data model of the 2026 documents; it answers at once, citing the figure
senfd-ask "What is the opcode of the Sanitize Namespace command?"
senfd-ask "Which bit of CDW12 of the Write command is STC?"
senfd-ask "What are the fields of the controller status register?"
senfd-ask "Which feature is Power Limit?"
senfd-ask "log page 1Fh"
senfd-ask CRIME
# What the data model does not have, it says it does not know
senfd-ask "Which bit of CDW12 of Write enables the hyperdrive?"
# And what the documents may have wrong, with where it is
senfd-query errata
