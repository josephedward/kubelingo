# Main Menu 
- config/settings
- review (requires AI)
- generate (requires AI)
- import (requires AI) 

# Config Menu (already implemented) 
- api keys etc already done 

# Review Menu
- correct (runs a script to categorize, file into folders and provide an AI summary of what you appear to good at relative to the CKAD - requires AI prompt)  
- incorrect (runs a script to categorize, file into folders and provide an AI summary of what you appear to be BAD at relative to the CKAD - requires AI prompt) 
(Ideally these will be INTERACTIVE, and allow the user to have a dialogue with the AI about what they have worked on, where they need to improve, formatting questions - and these scripts should have the ability to reformat files, rename, combine, organize them into folders etc) 

# Generate Menu (all of these choices immediately move to the subject matter menu)
- trivia (simple question and answer; vocabulary/true-false/multiple choice) 
- command (user must enter an imperative bash command) 
- manifest (user must use vim to provide a manifest as an answer)

# Subject Matter Menu
- pods
- deployments
- services
- configmaps
- secrets
- ingress
- volumes
- rbac
- networking
- monitoring
- security
- troubleshooting

# Import Menu (all of these options require AI queries)
- uncategorized (user selects a file from questions/uncategorized/ and the AI uses it for inspiration; not hardcoded static values/checks)
- from url (requires scraping too)
- from file path (may provide difficult file types or strange parsing; definitely requires AI and may need to fail cleanly) 

# Question Menu (do not write this literally; it comes after every question is asked)
- vim - opens vim for manifest-based questions 
- backward - previous question 
- forward  - skip to next question  
- solution - shows solution and the post-answer menu 
- visit - source (opens browser at source) 
- quit - back to main menu 

# Post Answer Menu (always comes after a question is answered)
- again (try again - formerly ‘retry) 
- correct 
- missed 
- remove question 
