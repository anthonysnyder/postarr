# This is a page for known issues with this app. 

- The script has a hard time parsing folder where there is a difference in punctuation. 
    - Example: Locally, I have */movies/Batman v Superman - Dawn of Justice (2016)*, but when the script searches TMDB, it will come back as *Batman v Superman: Dawn of Justice (2016)* and thus try and save it at */movies/Batman v Superman: Dawn of Justice (2016)/* 

I have not figured out how to fix this yet. 
