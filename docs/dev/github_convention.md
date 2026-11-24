# Guide to do github collaboration
## Define categories 
### Based on project development
Following are categories in project development:
- ETL
- EDA
- HP_TEST: for hypothesis testing.
- STL: for statistical learning.
In each they have their own sub categories:
- ETL: has ingest(more intuitive than extract), transform, and load.
- EDA: univariate, bivariate, multivairate, profile, and other stuff.
- HP_TEST: H2, H4, H6
- STL: TBD.
**Note**: that they are matched to how the directories and files are structured. It is intuitive to work with. I spent hours to figure that simple things out, I won't list everything, but you get the idea.
### Based on Labels
There are these 11 labels:
- BUG: fix bugs, do cleanup on stuff like old files or dependencies fix.
- FEAT: create new features.
- DOC: wrote new documentation. This is when you commit changes with not new code writing only. if you build new features and also documented it then commit, then use other labels.

## Create new branch
Format: `author/category-specific parts`
Example1: `layhok/etl-cleaning`
Example2: `Hong/HP_TEST-H1`
Example3: 
## Writing commit message 
Format: `[label-sub-category]: short description of changes specifying sub categories worked on.`
**NOTE:** Sub category should be in lowercase.
Example 1: `[FEAT-tranform]: cleaned missing values in licit db.` 
Example 2: `[FEAT-univariate]: visualized fan-in&out of licit wallets.` 
Example 3: `[BUG-univariate]: Fixed plot type and color combination.` 
Example 4: `[DOC-load]:  Documented flow of modular exporting data`
**Special case**: sometimes, it doesn't fit any of the sub category then you can utilize `general`. This is for special case like commit this document, not for exploit for bad practices. Bad practice in local change should suffer manual adding for remote push.
## There is a pattern and scope constraint to this:
- You now may realize that this will encourage creating new branches for specific sub-folders. This means you have to work on a specific small scope of the project, aka sub folders then commit to comply with this rule.
- You should not let ai run off modify many folders and files. Else you will have to select some files for different branches.
- In each branch, you will be limited to small amount of commits you can have. There will not be more than 100 commits in one branch since the design of rules will make you run out of things to do on that branch after you are done, and new independent tasks will require new branch creation.
- A lot of branches will be created, and that is good.

**ADVICE**: To do the above correctly and effectively, you should try to explore the whole repo and read documentation first.

