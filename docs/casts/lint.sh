# The eleven specifications NVM Express publishes, downloaded as PDF, read into one data model
senfd ~/specs/*.pdf --output ~/.cache/senfd
# What reading them found, for the authors first: candidate errata, then what the documents get wrong
senfd lint
